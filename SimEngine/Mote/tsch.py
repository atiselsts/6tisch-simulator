"""
"""

# =========================== imports =========================================

import random
import copy

# Mote sub-modules
import sf
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Tsch(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self.schedule                       = {}      # indexed by ts, contains cell
        self.txQueue                        = []
        self.pktToSend                      = None
        self.waitingFor                     = None
        self.channel                        = None
        self.asnLastSync                    = None
        self.isSync                         = False
        self.backoffBroadcast               = 0
        self.drift                          = random.uniform(-d.RADIO_MAXDRIFT, d.RADIO_MAXDRIFT)
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
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_SYNCED,
            {
                "_mote_id":   self.mote.id,
            }
        )
        
        # set
        self.isSync = val
        
        # listeningForEB->active transition 
        self.engine.removeFutureEvent(      # remove previously scheduled listeningForEB cells
            uniqueTag=(self.mote.id, '_tsch_action_listeningForEB_cell')
        )
        self.tsch_schedule_active_cell()    # schedule next active cell

    def getTxCells(self, neighbor = None):
        
        if neighbor!=None:
            assert type(neighbor)==int
        
        if neighbor is None:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TX]
        else:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                    c['dir'] == d.DIR_TX and c['neighbor'] == neighbor]

    def getRxCells(self, neighbor = None):
        
        if neighbor!=None:
            assert type(neighbor)==int
        
        if neighbor is None:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_RX]
        else:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                    c['dir'] == d.DIR_RX and c['neighbor'] == neighbor]

    def getSharedCells(self, neighbor = None):
        
        if neighbor!=None:
            assert type(neighbor)==int
        
        if neighbor is None:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TXRX_SHARED]
        else:
            return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                    c['dir'] == d.DIR_TXRX_SHARED and c['neighbor'] == neighbor]

    def activate(self):
        '''
        Active the TSCH state machine.
        - on the dagRoot, from boot
        - on the mote, after having received an EB
        '''
        
        # start sending EBs
        self._tsch_schedule_sendEB()

        # if not join, set the neighbor variables when initializing stack.
        # with join this is done when the nodes become synced. If root, initialize here anyway
        if (not self.settings.secjoin_enabled) or self.mote.dagRoot:
            for m in self.mote._myNeighbors():
                self._resetBackoffPerNeigh(m)
    
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
        
        # add cell
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
            self.log(
                SimEngine.SimLog.LOG_TSCH_ADD_CELL,
                {
                    "ts": cell[0],
                    "channel": cell[1],
                    "direction": cell[2],
                    "source_id": self.mote.id,
                    "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS
                }
            )
        
        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_active_cell()

    def removeCells(self, neighbor, tsList):
        """ removes cell(s) from the schedule """
        
        # remove cell
        for cell in tsList:
            assert type(cell) == int
            # log
            self.log(
                SimEngine.SimLog.LOG_TSCH_REMOVE_CELL,
                {
                    "ts": cell[0],
                    "channel": cell[1],
                    "direction": cell[2],
                    "source_id": self.mote.id,
                    "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS
                }
            )

            assert cell in self.schedule.keys()
            assert self.schedule[cell]['neighbor'] == neighbor
            self.schedule.pop(cell)

        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_active_cell()

    # data interface with upper layers

    def enqueue(self, packet):

        # 'type', 'mac', and 'net' are mandatory fields of a packet. in this
        # sense, a set of packet.keys() should have them.
        assert set(['type','mac','net']).issubset(set(packet.keys()))

        # srcMac and dstMac should be in place
        assert 'srcMac' in packet['mac']
        assert 'dstMac' in packet['mac']
        
        returnVal = True
        
        # check there is space in txQueue
        if returnVal:
            if len(self.txQueue) >= d.TSCH_QUEUE_SIZE:
                # my TX queue is full
                
                # drop
                self.mote.radio.drop_packet(
                    pkt     = packet,
                    reason  = SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type']
                )
                
                # couldn't enqueue
                returnVal = False
        
        # check that I have cell to transmit on
        if returnVal:
            if (not self.getTxCells()) and (not self.getSharedCells()):
                # I don't have any cell to transmit on
                
                # drop
                self.mote.radio.drop_packet(
                    pkt     = packet,
                    reason  = SimEngine.SimLog.LOG_TSCH_DROP_NO_TX_CELLS['type']
                )
                
                # couldn't enqueue
                returnVal = False
        
        # if I get here, every is OK, I can enqueue
        if returnVal:
            # set retriesLeft which should be renewed at every hop
            packet['mac']['retriesLeft'] = d.TSCH_MAXTXRETRIES,
            # add to txQueue
            self.txQueue    += [packet]
        
        return returnVal

    # interface with radio

    def txDone(self, isACKed):
        """end of tx slot"""
        
        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        assert ts in self.getSchedule()
        assert self.getSchedule()[ts]['dir'] == d.DIR_TX or self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED
        assert self.waitingFor == d.DIR_TX
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_TXDONE,
            {
                '_mote_id':       self.mote.id,
                'channel':        self.channel,
                'packet':         self.pktToSend,
                'isACKed':        isACKed,
            }
        )
        
        if isACKed:

            # update schedule stats
            self.getSchedule()[ts]['numTxAck'] += 1

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
                        asn            = fireASN,
                        cb             = self.mote.sixp.timer_fired,
                        uniqueTag      = (self.mote.id, uniqueTag),
                        intraSlotOrder = 5,
                    )
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.mote.id, uniqueTag)
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}"
                            .format(
                                self.mote.id,
                                self.pktToSend['dstIp'].id,
                                fireASN,
                                str(uniqueTag)
                            )
                        }
                    )
                elif self.pktToSend['code'] == d.IANA_6TOP_CMD_DELETE:
                    assert self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETERESPONSE

                    # calculate the asn at which it should fire
                    fireASN = int(self.engine.getAsn() + (float(self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                    uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                    self.engine.scheduleAtAsn(
                        asn            = fireASN,
                        cb             = self.mote.sixp.timer_fired,
                        uniqueTag      = (self.mote.id, uniqueTag),
                        intraSlotOrder = 5,
                    )
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.mote.id, uniqueTag)
                    self.mote.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}"
                            .format(
                                self.mote.id,
                                self.pktToSend['dstIp'].id,
                                fireASN,
                                str(self.mote.id),
                                str(uniqueTag)
                            )
                        }
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

        elif self.pktToSend['net']['dstIp'] == d.BROADCAST_ADDRESS:

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
            if self.txQueue[i]['mac']['retriesLeft'] > 0:
                self.txQueue[i]['mac']['retriesLeft'] -= 1

            # drop packet if retried too many time
            if self.txQueue[i]['mac']['retriesLeft'] == 0:

                if  len(self.txQueue) == d.TSCH_QUEUE_SIZE:

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

    def rxDone(self, packet):
        
        # local variables
        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength
        
        # make sure I'm in the right state
        if self.getIsSync():
            assert ts in self.getSchedule()
            assert self.getSchedule()[ts]['dir'] == d.DIR_RX or self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED
            assert self.waitingFor == d.DIR_RX
        
        # not waiting for anything anymore
        self.waitingFor = None
        
        # abort if received nothing (idle listen)
        if packet==None:
            return False # isACKed
        
        # abort if unicast to some other mote
        if packet['mac']['dstMac'] not in [d.BROADCAST_ADDRESS,self.mote.id]:
            return False # isACKed
        
        # if I get here, I received a frame at the link layer (either unicast for me, or broadcast)
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_RXDONE,
            {
                '_mote_id':        self.mote.id,
                'packet':          packet,
            }
        )
        
        # time correction
        if packet['mac']['srcMac'] == self.mote.rpl.getPreferredParent():
            self.asnLastSync = asn
        
        # update schedule stats
        if self.getIsSync():
            self.getSchedule()[ts]['numRx'] += 1
        
        # signal activity to SF
        if self.getIsSync():
            self.mote.sf.signal_cell_used(
                self.mote,
                self.getSchedule()[ts]['neighbor'],
                self.getSchedule()[ts]['dir'],
                d.DIR_RX,
                packet['type'],
            )

        if   'net' in packet:
            # sanity-check:
            # - unicast IPv6 packet should have unicast MAC address
            # - broadcast (multicast) IPv6 packet should have broadcast MAC address
            if (
                    (packet['type'] != d.NET_TYPE_FRAG)
                    and
                    (
                        (
                            (packet['mac']['dstMac'] == self.mote.id)
                            and
                            (packet['net']['dstIp']  == d.BROADCAST_ADDRESS)
                        )
                        or
                        (
                            (packet['type']          != d.NET_TYPE_FRAG)
                            and
                            (packet['mac']['dstMac'] == d.BROADCAST_ADDRESS)
                            and
                            (packet['net']['dstIp']  != d.BROADCAST_ADDRESS)
                        )
                    )
               ):
                raise SystemError()

            # ACK frame
            isACKed = True

            # network-layer packet; pass it to sixlowpan
            self.mote.sixlowpan.recv(packet)

        elif packet['mac']['dstMac']==self.mote.id:
            # link-layer unicast to me
            
            # ACK frame
            isACKed = True
            
            # dispatch to the right upper layer
            if   packet['type'] == d.IANA_6TOP_ADD_REQUEST:
                self.mote.sixp.receive_ADD_REQUEST(packet)
            elif packet['type'] == d.IANA_6TOP_DELETE_REQUEST:
                self.mote.sixp.receive_DELETE_REQUEST(packet)
            elif packet['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                self.mote.sixp.receive_RESPONSE(packet)

        elif packet['mac']['dstMac']==d.BROADCAST_ADDRESS:
            # link-layer broadcast
            
            # do NOT ACK frame
            isACKed = False
            
            # dispatch to the right upper layer
            if   packet['type'] == d.TSCH_TYPE_EB:
                self._tsch_action_receiveEB(packet)

        else:
            raise SystemError()
        
        return isACKed

    def getOffsetToDagRoot(self):
        """
        calculate time offset compared to the DAGroot
        """

        if self.mote.dagRoot:
            return 0.0

        asn                  = self.engine.getAsn()
        offset               = 0.0
        child                = self.mote
        parent               = self.engine.motes[self.mote.rpl.getPreferredParent()]

        if child.tsch.asnLastSync:
            while True:
                secSinceSync     = (asn-child.tsch.asnLastSync)*self.settings.tsch_slotDuration  # sec
                # FIXME: for ppm, should we not /10^6?
                relDrift         = child.tsch.drift - parent.tsch.drift                          # ppm
                offset          += relDrift * secSinceSync                                       # us
                if parent.dagRoot:
                    break
                else:
                    child        = parent
                    parent       = self.engine.motes[child.rpl.getPreferredParent()]

        return offset
    
    def removeTypeFromQueue(self,type):
        i = 0
        while i<len(self.txQueue):
            if self.txQueue[i]['type'] == type:
                del self.txQueue[i]
            else:
                i += 1
    
    #======================== private ==========================================
    
    # listeningForEB
    
    def tsch_schedule_listeningForEB_cell(self):
        
        assert not self.getIsSync()

        # schedule at next ASN
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn()+1,
            cb               = self._tsch_action_listeningForEB_cell,
            uniqueTag        = (self.mote.id, '_tsch_action_listeningForEB_cell'),
            intraSlotOrder   = 0,
        )
    
    def _tsch_action_listeningForEB_cell(self):
        """
        active slot starts, while mote is listening for EBs
        """
        
        assert not self.getIsSync()
        
        # choose random channel
        channel = 0 # FIXME

        # start listening
        self.mote.radio.startRx(
            channel = channel,
        )

        # indicate that we're waiting for the RX operation to finish
        self.waitingFor = d.DIR_RX
        
        # schedule next listeningForEB cell
        self.tsch_schedule_listeningForEB_cell()
    
    # active cell

    def tsch_schedule_active_cell(self):
        
        assert self.getIsSync()
        
        asn        = self.engine.getAsn()
        tsCurrent  = asn % self.settings.tsch_slotframeLength

        # find closest active slot in schedule

        if not self.schedule:
            self.engine.removeFutureEvent(uniqueTag=(self.mote.id, '_tsch_action_active_cell'))
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

            if (not tsDiffMin) or (tsDiff < tsDiffMin):
                tsDiffMin     = tsDiff

        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn              = asn+tsDiffMin,
            cb               = self._tsch_action_active_cell,
            uniqueTag        = (self.mote.id, '_tsch_action_active_cell'),
            intraSlotOrder   = 0,
        )
    
    def _tsch_action_active_cell(self):
        """
        active slot starts, while mote is sync'ed
        """
        asn = self.engine.getAsn()
        ts  = asn % self.settings.tsch_slotframeLength

        # make sure this is an active slot
        assert ts in self.schedule
        
        # make sure we're not in the middle of a TX/RX operation
        assert not self.waitingFor

        cell = self.schedule[ts]

        # signal to scheduling function that a cell to a neighbor has been triggered
        self.mote.sf.signal_cell_elapsed(
            self.mote,
            cell['neighbor'],
            cell['dir'],
        )

        if  cell['dir'] == d.DIR_RX:

            # =============== RX cell

            # start listening
            self.mote.radio.startRx(
                channel       = cell['ch'],
            )

            # indicate that we're waiting for the RX operation to finish
            self.waitingFor   = d.DIR_RX

        elif cell['dir'] == d.DIR_TX:

            # =============== TX cell

            # find packet to send
            self.pktToSend = None
            for pkt in self.txQueue:
            
                # 'type', 'mac', and 'net' are mandatory fields of a packet. in this
                # sense, a set of packet.keys() should have them.
                assert set(['type','mac','net']).issubset(set(pkt.keys()))
            
                # send the frame if next hop matches the cell destination
                if pkt['mac']['dstMac'] == cell['neighbor'].id:
                    self.pktToSend = pkt
                    break

            # send packet
            if self.pktToSend:

                # inform SF cell is used
                self.mote.sf.signal_cell_used(
                    self.mote,
                    cell['neighbor'],
                    cell['dir'],
                    d.DIR_TX,
                    pkt['type'],
                )
                
                # update cell stats
                cell['numTx'] += 1

                '''
                if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                    if   pkt['code'] == d.IANA_6TOP_CMD_ADD:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                    elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                    else:
                        raise SystemError()

                if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                    if self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                        pass
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                        pass
                    else:
                        raise SystemError()
                '''
                
                # send packet to the radio
                self.mote.radio.startTx(
                    channel   = cell['ch'],
                    packet    = self.pktToSend,
                )

                # indicate that we're waiting for the TX operation to finish
                self.waitingFor   = d.DIR_TX
                self.channel      = cell['ch']

        elif cell['dir'] == d.DIR_TXRX_SHARED:
            
            if cell['neighbor'] == self.mote._myNeighbors(): # FIXME, does nothing, always []==[]
                self.pktToSend = None
                if self.txQueue and self.backoffBroadcast == 0:
                    for pkt in self.txQueue:
                        if  (
                                # DIOs and EBs always on minimal cell
                                (
                                    pkt['type'] in [d.RPL_TYPE_DIO,d.TSCH_TYPE_EB]
                                )
                                or
                                # other frames on the minimal cell if no dedicated cells to the nextHop
                                (
                                    self.getTxCells(pkt['mac']['dstMac'])==[]
                                    and
                                    self.getSharedCells(pkt['mac']['dstMac'])==[]
                                )
                            ):
                            self.pktToSend = pkt
                            break
                
                # decrement back-off
                if self.backoffBroadcast > 0:
                    self.backoffBroadcast -= 1
            else:
                assert False # FIXME: apparently we never enter this branch...
                if self.getIsSync():
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

                # update cell stats
                cell['numTx'] += 1

                # signal to scheduling function that a cell to a neighbor is used
                self.mote.sf.signal_cell_used(
                    self.mote,
                    cell['neighbor'],
                    cell['dir'],
                    d.DIR_TX,
                    pkt['type'],
                )
                
                '''
                if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                    if pkt['code'] == d.IANA_6TOP_CMD_ADD:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                    elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                    else:
                        assert False

                if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                    if self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                        self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                        pass
                    elif self.mote.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                        pass
                    else:
                        assert False
                '''

                # send packet to the radio
                self.mote.radio.startTx(
                    channel   = cell['ch'],
                    packet    = self.pktToSend,
                )

                # indicate that we're waiting for the TX operation to finish
                self.waitingFor   = d.DIR_TX
                self.channel      = cell['ch']

            else:
                # start listening
                self.mote.radio.startRx(
                     channel       = cell['ch'],
                )

                # indicate that we're waiting for the RX operation to finish
                self.waitingFor = d.DIR_RX

        # schedule next active cell
        self.tsch_schedule_active_cell()

    # EBs

    def _tsch_schedule_sendEB(self):
        
        # schedule to send an EB every slotframe
        # _tsch_action_sendEB() decides whether to actually send, based on probability
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn() + int(self.settings.tsch_slotframeLength),
            cb               = self._tsch_action_sendEB,
            uniqueTag        = (self.mote.id, '_tsch_action_sendEB'),
            intraSlotOrder   = 3,
        )

    def _tsch_action_sendEB(self):
        
        # compute probability to send an EB
        ebProb     = float(self.settings.tsch_probBcast_ebProb)            \
                     /                                                     \
                     float(len(self.mote.secjoin.areAllNeighborsJoined())) \
                     if                                                    \
                     len(self.mote.secjoin.areAllNeighborsJoined())        \
                     else                                                  \
                     float(self.settings.tsch_probBcast_ebProb)
        sendEB = (random.random() < ebProb)
        
        # enqueue EB, if appropriate
        if sendEB:
            # probability passes
            if self.mote.secjoin.isJoined() or (not self.settings.secjoin_enabled):
                # I have joined
                if  (
                        self.mote.dagRoot
                        or
                        (
                            self.mote.rpl.getPreferredParent()!=None
                            and
                            (
                                (
                                    type(self.mote.sf)==sf.MSF
                                    and
                                    self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(),0)>0
                                )
                                or
                                (
                                    type(self.mote.sf)!=sf.MSF
                                )
                            )
                        )
                    ):
                    
                    # I am the root, or I have a preferred parent with dedicated cells to it
                    
                    # create new packet
                    newEB = {
                        'type':             d.TSCH_TYPE_EB,
                        'app': {
                            'jp':           self.mote.rpl.getDagRank(),
                        },
                        'net': {
                            'srcIp':        self.mote.id,            # from mote
                            'dstIp':        d.BROADCAST_ADDRESS,     # broadcast
                        },
                    }

                    # remove other possible EBs from the queue
                    self.removeTypeFromQueue(d.TSCH_TYPE_EB)
                    
                    # enqueue packet in TSCH queue
                    self.enqueue(newEB)

        # schedule next EB
        self._tsch_schedule_sendEB()

    def _tsch_action_receiveEB(self, packet):
        
        assert packet['type'] == d.TSCH_TYPE_EB
        
        # abort if I'm the root
        if self.mote.dagRoot:
            return
        
        if not self.getIsSync():
            # receiving EB while not sync'ed
            
            # I'm now sync'ed!
            self.setIsSync(True)

            # set neighbors variables before starting request cells to the preferred parent
            # FIXME
            for m in self.mote._myNeighbors():
                self._resetBackoffPerNeigh(m)
            
            # activate the TSCH stack
            self.mote.activate_tsch_stack()
            
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
