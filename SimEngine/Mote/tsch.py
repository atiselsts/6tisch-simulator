"""
"""

# =========================== imports =========================================

import random
import threading
import copy

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('tsch')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Tsch(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # admin
        self.dataLock                       = threading.RLock()

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.propagation                    = SimEngine.Propagation.Propagation()

        # local variables
        self.schedule                       = {}      # indexed by ts, contains cell
        self.txQueue                        = []
        self.pktToSend                      = None
        self.waitingFor                     = None
        self.asnLastSync                    = None
        self.isSync                         = False
        self._resetBroadcastBackoff()
        self.backoffPerNeigh                = {}
        self.backoffExponentPerNeigh        = {}

    #======================== public ==========================================

    # getters/setters
    
    def getSchedule(self):
        return self.schedule
    
    def getTxQueue(self):
        return self.txQueue
    
    def getIsSync(self):
        return self.isSync
    def setIsSync(self,val):
        self.isSync = val
    
    def getTxCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TX]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_TX and c['neighbor'] == neighbor]

    def getRxCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_RX]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_RX and c['neighbor'] == neighbor]

    def getSharedCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TXRX_SHARED]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_TXRX_SHARED and c['neighbor'] == neighbor]
    
    # admin
    
    def activate(self):
        
        # start sending EBs
        self._tsch_schedule_sendEB()
        
        # if not join, set the neighbor variables when initializing stack.
        # with join this is done when the nodes become synced. If root, initialize here anyway
        if (not self.settings.secjoin_enabled) or self.mote.dagRoot:
            for m in self.mote._myNeighbors():
                self._resetBackoffPerNeigh(m)
    
    # listening for EBs
    
    def listenEBs(self):
        
        self.engine.scheduleAtAsn(
            asn         = self.engine.getAsn() + 1,
            cb          = self._action_listenEBs,
            uniqueTag   = (self.mote.id, '_action_listenEBs'),
            priority    = 3,
        )
    
    # minimal
    
    def add_minimal_cell(self):
        
        self.addCells(
            self.mote._myNeighbors(),
            [
                (0, 0, d.DIR_TXRX_SHARED)
            ],
        )
    
    # schedule interface
    
    def addCells(self, neighbor, cellList):
        """ Adds cell(s) to the schedule

        :param Mote || list neighbor:
        :param list cellList:
        :return:
        """

        with self.dataLock:
            for cell in cellList:
                assert cell[0] not in self.schedule.keys()
                self.schedule[cell[0]] = {
                    'ch':                        cell[1],
                    'dir':                       cell[2],
                    'neighbor':                  neighbor,
                    'numTx':                     0,
                    'numTxAck':                  0,
                    'numRx':                     0,
                }
                # log
                self.engine.log(
                    SimEngine.SimLog.LOG_TSCH_ADD_CELL,
                    {"ts": cell[0],
                     "channel": cell[1],
                     "direction": cell[2],
                     "source_id": self.mote.id,
                     "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS
                    }
                )
            self._tsch_schedule_activeCell()

    def removeCells(self, neighbor, tsList):
        """ removes cell(s) from the schedule """

        with self.dataLock:
            for cell in tsList:
                assert type(cell) == int
                # log
                self.mote._log(
                    d.INFO,
                    "[tsch] remove cell=({0}) with {1}",
                    (cell, neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS),
                )
                self.engine.log(SimEngine.SimLog.LOG_TSCH_REMOVE_CELL,
                                {"ts": cell[0],
                                 "channel": cell[1],
                                 "direction": cell[2],
                                 "source_id": self.mote.id,
                                 "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS})

                assert cell in self.schedule.keys()
                assert self.schedule[cell]['neighbor'] == neighbor
                self.schedule.pop(cell)

            self._tsch_schedule_activeCell()

    # data interface with upper layers
    
    def enqueue(self, packet):

        if not self.mote.rpl.findNextHop(packet):
            # I don't have a route

            # increment mote state
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_RPL_DROP_NO_ROUTE['type'])

            return False

        elif not (self.getTxCells() or self.getSharedCells()):
            # I don't have any transmit cells

            # increment mote state
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_NO_TX_CELLS['type'])

            return False

        elif len(self.txQueue) >= d.TSCH_QUEUE_SIZE:
            # my TX queue is full

            # However, I will allow to add an additional packet in some specific ocasions
            # This is because if the queues of the nodes are filled with DATA packets, new nodes won't be able to enter properly in the network. So there are exceptions.

            # if join is enabled, all nodes will wait until all nodes have at least 1 Tx cell. So it is allowed to enqueue 1 aditional DAO, JOIN or 6P packet
            if packet['type'] == d.APP_TYPE_JOIN or packet['type'] == d.RPL_TYPE_DAO or packet['type'] == d.IANA_6TOP_TYPE_REQUEST or packet['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                for p in self.txQueue:
                    if packet['type'] == p['type']:
                        #There is already a DAO, JOIN or 6P in que queue, don't add more
                        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type'])
                        return False
                self.txQueue    += [packet]
                return True

            # update mote stats
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type'])

            return False

        else:
            # all is good

            # enqueue packet
            self.txQueue    += [packet]

            return True
    
    # interface with radio
    
    def txDone(self, isACKed, isNACKed):
        """end of tx slot"""
        
        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        with self.dataLock:

            assert ts in self.getSchedule()
            assert self.getSchedule()[ts]['dir'] == d.DIR_TX or self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED
            assert self.waitingFor == d.DIR_TX

            if isACKed:

                # update schedule stats
                self.getSchedule()[ts]['numTxAck'] += 1

                # update queue stats
                self.mote._stats_logQueueDelay(asn-self.pktToSend['asn'])

                # time correction
                if self.getSchedule()[ts]['neighbor'] == self.mote.rpl.getPreferredParent():
                    self.asnLastSync = asn

                # received an ACK for the request, change state and increase the sequence number
                if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                    if self.pktToSend['code'] == d.IANA_6TOP_CMD_ADD:
                        assert self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDRESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (
                                    float(self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self.mote.sixp.timer_fired,
                            uniqueTag=(self.mote.id, uniqueTag),
                            priority=5,
                        )
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.mote.id, uniqueTag)
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                        self.mote._log(
                            d.DEBUG,
                            "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}",
                            (self.mote.id, self.pktToSend['dstIp'].id, fireASN, str((self.mote.id, uniqueTag))),
                        )
                    elif self.pktToSend['code'] == d.IANA_6TOP_CMD_DELETE:
                        assert self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETERESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (float(self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self.mote.sixp.timer_fired,
                            uniqueTag=(self.mote.id, uniqueTag),
                            priority=5,
                        )
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.mote.id, uniqueTag)
                        self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                        self.mote._log(
                            d.DEBUG,
                            "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}",
                            (self.mote.id, self.pktToSend['dstIp'].id, fireASN, str((self.mote.id, uniqueTag))),
                        )
                    else:
                        assert False

                # save it in a tmp variable
                # because it is possible that self.getSchedule()[ts] does not exist anymore after receiving an ACK for a DELETE RESPONSE
                tmpNeighbor = self.getSchedule()[ts]['neighbor']
                tmpDir = self.getSchedule()[ts]['dir']

                if self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE: # received an ACK for the response, handle the schedule
                    self.mote.sixp.receive_RESPONSE_ACK(self.pktToSend)

                # remove packet from queue
                self.getTxQueue().remove(self.pktToSend)
                # reset backoff in case of shared slot or in case of a tx slot when the queue is empty
                if tmpDir == d.DIR_TXRX_SHARED or (tmpDir == d.DIR_TX and not self.txQueue):
                    if tmpDir == d.DIR_TXRX_SHARED and tmpNeighbor != self.mote._myNeighbors():
                        self._resetBackoffPerNeigh(tmpNeighbor)
                    else:
                        self._resetBroadcastBackoff()

            elif isNACKed:

                # update schedule stats as if it were successfully transmitted
                self.getSchedule()[ts]['numTxAck'] += 1

                # time correction
                if self.getSchedule()[ts]['neighbor'] == self.mote.rpl.getPreferredParent():
                    self.asnLastSync = asn

                # decrement 'retriesLeft' counter associated with that packet
                i = self.getTxQueue().index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:

                    if len(self.txQueue) == d.TSCH_QUEUE_SIZE:

                        # only count drops of DATA packets that are part of the experiment
                        if self.pktToSend['type'] == d.APP_TYPE_DATA:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_DATA_MAX_RETRIES['type'])

                        # update mote stats
                        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_MAX_RETRIES['type'])

                        # remove packet from queue
                        self.getTxQueue().remove(self.pktToSend)

                        # reset state for this neighbor
                        # go back to IDLE, i.e. remove the neighbor form the states
                        # but, in the case of a response msg, if the node received another, already new request, from the same node (because its timer fired), do not go to IDLE
                        if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:
                            # update mote stats
                            self.mote._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.getTxQueue().remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []

                # reset backoff in case of shared slot or in case of a tx slot when the queue is empty
                if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED or (self.getSchedule()[ts]['dir'] == d.DIR_TX and not self.txQueue):
                    if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED and self.getSchedule()[ts]['neighbor'] != self.mote._myNeighbors():
                        self._resetBackoffPerNeigh(self.getSchedule()[ts]['neighbor'])
                    else:
                        self._resetBroadcastBackoff()
            
            elif self.pktToSend['dstIp'] == d.BROADCAST_ADDRESS:
                
                self.getTxQueue().remove(self.pktToSend)
                
                self._resetBroadcastBackoff()

            else:
                
                # increment backoffExponent and get new backoff value
                if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED:
                    if self.getSchedule()[ts]['neighbor'] == self.mote._myNeighbors():
                        if self.backoffBroadcastExponent < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffBroadcastExponent += 1
                        self.backoffBroadcast = random.randint(0, 2 ** self.backoffBroadcastExponent - 1)
                    else:
                        if self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] += 1
                        self.backoffPerNeigh[self.getSchedule()[ts]['neighbor']] = random.randint(0, 2 ** self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] - 1)

                # decrement 'retriesLeft' counter associated with that packet
                i = self.getTxQueue().index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:

                    if  len(self.txQueue) == d.TSCH_QUEUE_SIZE:

                        # counts drops of DATA packets
                        if self.pktToSend['type'] == d.APP_TYPE_DATA:
                            self.mote._stats_incrementMoteStats('droppedDataMacRetries')

                        # update mote stats
                        self.mote._stats_incrementMoteStats('droppedMacRetries')

                        # remove packet from queue
                        self.getTxQueue().remove(self.pktToSend)

                        # reset state for this neighbor
                        # go back to IDLE, i.e. remove the neighbor form the states
                        if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:

                            # update mote stats
                            self.mote._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.getTxQueue().remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
            # end of radio activity, not waiting for anything
            self.waitingFor = None
    
    def rxDone(self, type=None, code=None, smac=None, dmac=None, srcIp=None, dstIp=None, srcRoute=None, payload=None):
        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        with self.dataLock:
            if self.isSync:
                assert ts in self.getSchedule()
                assert self.getSchedule()[ts]['dir'] == d.DIR_RX or self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED
                assert self.waitingFor == d.DIR_RX
            
            if smac and (self.mote in dmac):  # layer 2 addressing
                # I received a packet

                if self.isSync:
                    self.mote.sf.signal_cell_used(
                        self.mote,
                        self.getSchedule()[ts]['neighbor'],
                        self.getSchedule()[ts]['dir'],
                        d.DIR_RX,
                        type,
                    )
                
                if self.isSync:
                    # update schedule stats
                    self.getSchedule()[ts]['numRx'] += 1
                
                # time correction
                if smac == self.mote.rpl.getPreferredParent():
                    self.asnLastSync = asn
                
                if type == d.APP_TYPE_FRAG:
                    frag = {
                        'type':        type,
                        'code':        code,
                        'retriesLeft': d.TSCH_MAXTXRETRIES,
                        'smac':        smac,
                        'srcIp':       srcIp,
                        'dstIp':       dstIp,
                        'payload':     copy.deepcopy(payload),
                        'sourceRoute': copy.deepcopy(srcRoute)
                    }
                    self.waitingFor = None
                    if self.settings.frag_ff_enable:
                        if self.mote.app.frag_ff_forward_fragment(frag) is True:
                            if self.enqueue(frag):
                                # ACK when succeeded to enqueue
                                return True, False
                            else:
                                # ACK anyway
                                self.mote._radio_drop_packet(frag, SimEngine.SimLog.LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE['type'])
                                return True, False
                        elif dstIp == self.mote:
                            if self.mote.app.frag_reassemble_packet(smac, payload) is True:
                                del payload['datagram_size']
                                del payload['datagram_offset']
                                del payload['datagram_tag']
                                type = d.APP_TYPE_DATA
                            else:
                                # not fully reassembled yet
                                return True, False
                        else:
                            # frag is out-of-order; ACK anyway since it's received successfully
                            return True, False
                    else:
                        if self.mote.app.frag_reassemble_packet(smac, payload) is True:
                            # remove fragment information from the payload
                            del payload['datagram_size']
                            del payload['datagram_offset']
                            del payload['datagram_tag']
                            type = d.APP_TYPE_DATA
                        else:
                            # ACK here
                            return True, False

                if dstIp == d.BROADCAST_ADDRESS:
                    if type == d.RPL_TYPE_DIO:
                        # got a DIO
                        self.mote.rpl.action_receiveDIO(type, smac, payload)

                        (isACKed, isNACKed) = (False, False)

                        self.waitingFor = None

                        return isACKed, isNACKed
                    elif type == d.TSCH_TYPE_EB:
                        self._tsch_action_receiveEB(type, smac, payload)

                        (isACKed, isNACKed) = (False, False)

                        self.waitingFor = None

                        return isACKed, isNACKed
                elif dstIp == self.mote:
                    # receiving packet
                    if type == d.RPL_TYPE_DAO:
                        self.mote.rpl.action_receiveDAO(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_ADD:  # received an 6P ADD request
                        self.mote.sixp.receive_ADD_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_DELETE:  # received an 6P DELETE request
                        self.mote.sixp.receive_DELETE_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_RESPONSE:  # received an 6P response
                        if self.mote.sixp.receive_RESPONSE(type, code, smac, payload):
                            (isACKed, isNACKed) = (True, False)
                        else:
                            (isACKed, isNACKed) = (False, False)
                    elif type == d.APP_TYPE_DATA:  # application packet
                        self.mote.app._action_dagroot_receivePacketFromMote(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_ACK:
                        self.mote.app.action_mote_receiveE2EAck(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_JOIN:
                        self.mote.secjoin.receiveJoinPacket(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_FRAG:
                        # never comes here; but just in case
                        (isACKed, isNACKed) = (True, False)
                    else:
                        assert False
                elif type == d.APP_TYPE_FRAG:
                    # do nothing for fragmented packet; just ack
                    (isACKed, isNACKed) = (True, False)
                else:
                    # relaying packet

                    if type == d.APP_TYPE_DATA:
                        # update the number of hops
                        newPayload     = copy.deepcopy(payload)
                        newPayload['hops'] += 1
                    else:
                        # copy the payload and forward
                        newPayload     = copy.deepcopy(payload)

                    # create packet
                    relayPacket = {
                        'asn':         asn,
                        'type':        type,
                        'code':        code,
                        'payload':     newPayload,
                        'retriesLeft': d.TSCH_MAXTXRETRIES,
                        'srcIp':       srcIp,
                        'dstIp':       dstIp,
                        'sourceRoute': srcRoute,
                    }

                    # enqueue packet in TSCH queue
                    if type == d.APP_TYPE_DATA and self.settings.frag_numFragments > 1:
                        self.mote.app.fragment_and_enqueue_packet(relayPacket)
                        # we return ack since we've received the last fragment successfully
                        (isACKed, isNACKed) = (True, False)
                    else:
                        isEnqueued = self.enqueue(relayPacket)
                        if isEnqueued:

                            # update mote stats
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RELAYED['type'])

                            (isACKed, isNACKed) = (True, False)

                        else:
                            self.mote._radio_drop_packet(relayPacket,
                                                    SimEngine.SimLog.LOG_TSCH_DROP_RELAY_FAIL_ENQUEUE['type'])
                            (isACKed, isNACKed) = (False, True)

            else:
                # this was an idle listen
                
                (isACKed, isNACKed) = (False, False)

            self.waitingFor = None

            return (isACKed,isNACKed)
    
    def getOffsetToDagRoot(self):
        """
        calculate time offset compared to the DAGroot
        """

        if self.mote.dagRoot:
            return 0.0

        asn                  = self.engine.getAsn()
        offset               = 0.0
        child                = self.mote
        parent               = self.mote.rpl.getPreferredParent()

        if child.tsch.asnLastSync:
            while True:
                secSinceSync     = (asn-child.tsch.asnLastSync)*self.settings.tsch_slotDuration  # sec
                # FIXME: for ppm, should we not /10^6?
                relDrift         = child.drift - parent.drift                                # ppm
                offset          += relDrift * secSinceSync                                   # us
                if parent.dagRoot:
                    break
                else:
                    child        = parent
                    parent       = child.rpl.getPreferredParent()

        return offset
    
    #======================== private ==========================================
    
    # active cell
    
    def _tsch_schedule_activeCell(self):

        asn        = self.engine.getAsn()
        tsCurrent  = asn % self.settings.tsch_slotframeLength

        # find closest active slot in schedule
        with self.dataLock:

            if not self.schedule:
                self.engine.removeEvent(uniqueTag=(self.mote.id, '_tsch_action_activeCell'))
                return

            tsDiffMin             = None

            for (ts, cell) in self.schedule.items():
                if   ts == tsCurrent:
                    tsDiff        = self.settings.tsch_slotframeLength
                elif ts > tsCurrent:
                    tsDiff        = ts-tsCurrent
                elif ts < tsCurrent:
                    tsDiff        = (ts+self.settings.tsch_slotframeLength)-tsCurrent
                else:
                    raise SystemError()

                if (not tsDiffMin) or (tsDiffMin > tsDiff):
                    tsDiffMin     = tsDiff

        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn         = asn+tsDiffMin,
            cb          = self._tsch_action_activeCell,
            uniqueTag   = (self.mote.id, '_tsch_action_activeCell'),
            priority    = 0,
        )

    def _tsch_action_activeCell(self):
        """
        active slot starts. Determine what todo, either RX or TX, use the propagation model to introduce
        interference and Rx packet drops.
        """

        asn = self.engine.getAsn()
        ts  = asn % self.settings.tsch_slotframeLength

        with self.dataLock:

            # make sure this is an active slot
            assert ts in self.schedule
            # make sure we're not in the middle of a TX/RX operation
            assert not self.waitingFor

            cell = self.schedule[ts]

            # Signal to scheduling function that a cell to a neighbor has been triggered
            self.mote.sf.signal_cell_elapsed(
                self.mote,
                cell['neighbor'],
                cell['dir'],
            )

            if  cell['dir'] == d.DIR_RX:

                # start listening
                self.radio.startRx(
                    channel       = cell['ch'],
                )

                # indicate that we're waiting for the RX operation to finish
                self.waitingFor   = d.DIR_RX

            elif cell['dir'] == d.DIR_TX:

                # check whether packet to send
                self.pktToSend = None
                if self.txQueue:
                    for pkt in self.txQueue:
                        # send the frame if next hop matches the cell destination
                        if pkt['nextHop'] == [cell['neighbor']]:
                            self.pktToSend = pkt
                            break

                # send packet
                if self.pktToSend:

                    # Signal to scheduling function that a cell to a neighbor is used
                    self.mote.sf.signal_cell_used(
                        self.mote,
                        cell['neighbor'],
                        cell['dir'],
                        d.DIR_TX,
                        pkt['type'],
                    )

                    cell['numTx'] += 1

                    if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                        if pkt['code'] == d.IANA_6TOP_CMD_ADD:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_REQ['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_REQ['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            raise SystemError()

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_RESP['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_RESP['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                            pass
                        else:
                            raise SystemError()

                    self.radio.startTx(
                        channel   = cell['ch'],
                        type      = self.pktToSend['type'],
                        code      = self.pktToSend['code'],
                        smac      = self.mote,
                        dmac      = [cell['neighbor']],
                        srcIp     = self.pktToSend['srcIp'],
                        dstIp     = self.pktToSend['dstIp'],
                        srcRoute  = self.pktToSend['sourceRoute'],
                        payload   = self.pktToSend['payload'],
                    )

                    # indicate that we're waiting for the TX operation to finish
                    self.waitingFor   = d.DIR_TX

            elif cell['dir'] == d.DIR_TXRX_SHARED:

                if cell['neighbor'] == self.mote._myNeighbors():
                    self.pktToSend = None
                    if self.txQueue and self.backoffBroadcast == 0:
                        for pkt in self.txQueue:
                            # send join packets on the shared cell only on first hop
                            if pkt['type'] == d.APP_TYPE_JOIN and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # send 6P messages on the shared broadcast cell only if there is no dedicated cells to that neighbor
                            elif pkt['type'] == d.IANA_6TOP_TYPE_REQUEST and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # send 6P messages on the shared broadcast cell only if there is no dedicated cells to that neighbor
                            elif pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # DIOs and EBs always go on the shared broadcast cell
                            elif pkt['type'] == d.RPL_TYPE_DIO or pkt['type'] == d.TSCH_TYPE_EB:
                                self.pktToSend = pkt
                                break
                            else:
                                continue
                    # Decrement backoff
                    if self.backoffBroadcast > 0:
                        self.backoffBroadcast -= 1
                else:
                    if self.isSync:
                        # check whether packet to send
                        self.pktToSend = None
                        if self.txQueue and self.backoffPerNeigh[cell['neighbor']] == 0:
                            for pkt in self.txQueue:
                                # send the frame if next hop matches the cell destination
                                if pkt['nextHop'] == [cell['neighbor']]:
                                    self.pktToSend = pkt
                                    break

                    # Decrement backoffPerNeigh
                    if self.backoffPerNeigh[cell['neighbor']] > 0:
                        self.backoffPerNeigh[cell['neighbor']] -= 1
                # send packet
                if self.pktToSend:

                    cell['numTx'] += 1

                    # to scheduling function that a cell to a neighbor is used
                    self.mote.sf.signal_cell_used(
                        self.mote,
                        cell['neighbor'],
                        cell['dir'],
                        d.DIR_TX,
                        pkt['type'],
                    )

                    if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                        if pkt['code'] == d.IANA_6TOP_CMD_ADD:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_REQ['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_REQ['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            assert False

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_RESP['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_RESP['type'])
                            self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                            pass
                        else:
                            assert False

                    self.radio.startTx(
                        channel   = cell['ch'],
                        type      = self.pktToSend['type'],
                        code      = self.pktToSend['code'],
                        smac      = self.mote,
                        dmac      = self.pktToSend['nextHop'],
                        srcIp     = self.pktToSend['srcIp'],
                        dstIp     = self.pktToSend['dstIp'],
                        srcRoute  = self.pktToSend['sourceRoute'],
                        payload   = self.pktToSend['payload'],
                    )
                    # indicate that we're waiting for the TX operation to finish
                    self.waitingFor   = d.DIR_TX

                else:
                    # start listening
                    self.radio.startRx(
                         channel       = cell['ch'],
                     )
                    # indicate that we're waiting for the RX operation to finish
                    self.waitingFor = d.DIR_RX

            # schedule next active cell
            self._tsch_schedule_activeCell()

    # EBs
    
    def _tsch_schedule_sendEB(self):

        if self.settings.tsch_ebPeriod_sec == 0:
            # disable periodic EB transmission
            return

        with self.dataLock:

            asn = self.engine.getAsn()

            if self.settings.tsch_probBcast_enabled:
                futureAsn = int(self.settings.tsch_slotframeLength)
            else:
                futureAsn = int(math.ceil(
                    random.uniform(
                        0.8 * self.settings.tsch_ebPeriod_sec,
                        1.2 * self.settings.tsch_ebPeriod_sec,
                    ) / self.settings.tsch_slotDuration
                ))

            # schedule at start of next cycle
            self.engine.scheduleAtAsn(
                asn=asn + futureAsn,
                cb=self._tsch_action_sendEB,
                uniqueTag=(self.mote.id, '_tsch_action_sendEB'),
                priority=3,
            )

    def _tsch_action_sendEB(self):

        with self.dataLock:

            if self.settings.tsch_probBcast_enabled:
                beaconProb = float(self.settings.tsch_probBcast_ebProb) / float(len(self.mote.secjoin.areAllNeighborsJoined())) if len(self.mote.secjoin.areAllNeighborsJoined()) else float(self.settings.tsch_probBcast_ebProb)
                sendBeacon = True if random.random() < beaconProb else False
            else:
                sendBeacon = True
            if self.mote.rpl.getPreferredParent() or self.mote.dagRoot:
                if self.mote.secjoin.isJoined() or not self.settings.secjoin_enabled:
                    if sendBeacon:
                        
                        # only start sending EBs if: I am a DAG root OR (I have a preferred parent AND dedicated cells to that parent)
                        if self.mote.dagRoot or (self.mote.rpl.getPreferredParent() and self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) != 0):

                            # create new packet
                            newPacket = {
                                'asn': self.engine.getAsn(),
                                'type': d.TSCH_TYPE_EB,
                                'code': None,
                                'payload': [self.mote.rpl.getDagRank()],  # the payload is the rpl rank
                                'retriesLeft': 1,  # do not retransmit broadcast
                                'srcIp': self.mote,
                                'dstIp': d.BROADCAST_ADDRESS,
                                'sourceRoute': []
                            }

                            # enqueue packet in TSCH queue
                            if not self.enqueue(newPacket):
                                # update mote stats
                                self.mote._radio_drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])
                        
                        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_TX_EB['type'])

            self._tsch_schedule_sendEB()  # schedule next EB

    def _tsch_action_receiveEB(self, type, smac, payload):

        # abort if I'm the root
        if self.mote.dagRoot:
            return

        # got an EB, increment stats
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_RX_EB['type'])

        if not self.isSync:
            # receiving EB while not sync'ed: sync!

            assert self.settings.secjoin_enabled

            # log
            self.mote._log(
                d.INFO,
                "[tsch] synced on EB received from mote {0}.",
                (smac.id,),
            )

            self.firstBeaconAsn = self.engine.getAsn()
            self.isSync         = True

            # set neighbors variables before starting request cells to the preferred parent
            for m in self.mote._myNeighbors():
                self._resetBackoffPerNeigh(m)

            # add the minimal cell to the schedule (read from EB)
            self.add_minimal_cell()

            # trigger join process
            self.mote.secjoin.scheduleJoinProcess()  # trigger the join process

    # back-off
    
    def _resetBroadcastBackoff(self):
        self.backoffBroadcast = 0
        self.backoffBroadcastExponent = d.TSCH_MIN_BACKOFF_EXPONENT - 1

    def _resetBackoffPerNeigh(self, neigh):
        self.backoffPerNeigh[neigh] = 0
        self.backoffExponentPerNeigh[neigh] = d.TSCH_MIN_BACKOFF_EXPONENT - 1
    
    # listening for EBs
    
    def _action_listenEBs(self):

        if not self.isSync:
            
            # choose random channel
            channel = random.randint(0, self.settings.phy_numChans-1)
            
            # start listening
            self.radio.startRx(
                channel = channel,
            )
            
            # indicate that we're waiting for the RX operation to finish
            self.waitingFor = d.DIR_RX
