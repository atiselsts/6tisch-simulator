"""
"""

# =========================== imports =========================================

import random

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

        # singletons (quicker access, instead of recreating every time)
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
        self.drift                          = random.uniform(-d.RADIO_MAXDRIFT, d.RADIO_MAXDRIFT)
        
        # backoff
        self.backoffBroadcast               = None    # FIXME: group under a single 'backoff' dict
        self.backoffBroadcastExponent       = None    # FIXME: group under a single 'backoff' dict
        self._resetBroadcastBackoff()
        self.backoffPerNeigh                = {}      # FIXME: group under a single 'backoff' dict
        self.backoffExponentPerNeigh        = {}      # FIXME: group under a single 'backoff' dict

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
        self.isSync      = val
        self.asnLastSync = self.engine.getAsn()
        
        # transition: listeningForEB->active
        self.engine.removeFutureEvent(      # remove previously scheduled listeningForEB cells
            uniqueTag=(self.mote.id, '_tsch_action_listeningForEB_cell')
        )
        self.tsch_schedule_next_active_cell()    # schedule next active cell
    
    def _getCells(self, direction, neighbor):
        if neighbor!=None:
            assert type(neighbor)==int
        
        if neighbor is None:
            return [
                (ts, c['ch'], c['neighbor'])
                    for (ts, c) in self.schedule.items()
                        if c['dir'] == direction
            ]
        else:
            return [
                (ts, c['ch'], c['neighbor'])
                    for (ts, c) in self.schedule.items()
                        if c['dir'] == direction and c['neighbor'] == neighbor
            ]
    
    def getTxCells(self, neighbor = None):
        return self._getCells(
            direction = d.DIR_TX,
            neighbor  = neighbor,
        )
    def getRxCells(self, neighbor = None):
        return self._getCells(
            direction = d.DIR_RX,
            neighbor  = neighbor,
        )
    def getSharedCells(self, neighbor = None):
        return self._getCells(
            direction = d.DIR_TXRX_SHARED,
            neighbor  = neighbor,
        )
    
    # admin
    
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

        self.addCell(
            neighbor         = self.mote._myNeighbors(), # FIXME: replace by None
            slotoffset       = 0,
            channeloffset    = 0,
            direction        = d.DIR_TXRX_SHARED,
        )

    # schedule interface

    def addCell(self, neighbor, slotoffset, channeloffset, direction):
        
        ''' FIXME
        if neighbor!=None:
            assert isinstance(neighbor, int)
        '''
        assert isinstance(slotoffset, int)
        assert isinstance(channeloffset, int)
        
        # make sure I have no activity at that slotoffset already
        assert slotoffset not in self.schedule.keys()
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_ADD_CELL,
            {
                "ts":             slotoffset,
                "channel":        channeloffset,
                "direction":      direction,
                "source_id":      self.mote.id,
                "neighbor_id":    neighbor if not type(neighbor) == list else d.BROADCAST_ADDRESS
            }
        )
        
        # add cell
        self.schedule[slotoffset] = {
            'ch':                 channeloffset,
            'dir':                direction,
            'neighbor':           neighbor,
            'numTx':              0,
            'numTxAck':           0,
            'numRx':              0,
        }
        
        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_next_active_cell()

    def removeCell(self, neighbor, slotoffset, channeloffset, direction):
        
        assert isinstance(neighbor, int)
        assert isinstance(slotoffset, int)
        assert isinstance(channeloffset, int)
        
        # make sure I'm removing a cell that I have in my schedule
        assert slotoffset in self.schedule.keys()
        assert self.schedule[slotoffset]['ch']        == channeloffset
        assert self.schedule[slotoffset]['dir']       == direction
        assert self.schedule[slotoffset]['neighbor']  == neighbor
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_REMOVE_CELL,
            {
                "ts":              cell[0],
                "channel":         cell[1],
                "direction":       cell[2],
                "source_id":       self.mote.id,
                "neighbor_id":     neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS
            }
        )

        # remove cell
        del self.schedule[slotoffset]

        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_next_active_cell()

    # data interface with upper layers

    def enqueue(self, packet):

        assert 'type' in packet
        assert 'mac' in packet
        assert 'srcMac' in packet['mac']
        assert 'dstMac' in packet['mac']
        
        goOn = True
        
        # check there is space in txQueue
        if goOn:
            if len(self.txQueue) >= d.TSCH_QUEUE_SIZE:
                # my TX queue is full
                
                # drop
                self.mote.radio.drop_packet(
                    pkt     = packet,
                    reason  = SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type']
                )
                
                # couldn't enqueue
                goOn = False
        
        # check that I have cell to transmit on
        if goOn:
            if (not self.getTxCells()) and (not self.getSharedCells()):
                # I don't have any cell to transmit on
                
                # drop
                self.mote.radio.drop_packet(
                    pkt     = packet,
                    reason  = SimEngine.SimLog.LOG_TSCH_DROP_NO_TX_CELLS['type']
                )
                
                # couldn't enqueue
                goOn = False
        
        # if I get here, every is OK, I can enqueue
        if goOn:
            # set retriesLeft which should be renewed at every hop
            packet['mac']['retriesLeft'] = d.TSCH_MAXTXRETRIES
            # add to txQueue
            self.txQueue    += [packet]
        
        return goOn

    # interface with radio

    def txDone(self, isACKed):
        assert isACKed in [True,False]
        
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
        
        if self.pktToSend['mac']['dstMac'] == d.BROADCAST_ADDRESS:
            # I just sent a broadcast packet
            
            assert isACKed==False
            
            # remove packet from queue
            self.getTxQueue().remove(self.pktToSend)
            
            # reset backoff
            self._resetBroadcastBackoff()
        else:
            # I just sent a unicast packet...
        
            # TODO send txDone up
        
            if isACKed:
                # ... which was ACKed

                # update schedule stats
                self.getSchedule()[ts]['numTxAck'] += 1

                # time correction
                if self.getSchedule()[ts]['neighbor'] == self.mote.rpl.getPreferredParent():
                    self.asnLastSync = asn # ACK-based sync
                
                # remove packet from queue
                self.getTxQueue().remove(self.pktToSend)

                # update backoff
                if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED or (self.getSchedule()[ts]['dir'] == d.DIR_TX and not self.txQueue):
                    if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED and self.getSchedule()[ts]['neighbor'] != self.mote._myNeighbors():
                        self._resetBackoffPerNeigh(self.getSchedule()[ts]['neighbor'])
                    else:
                        self._resetBroadcastBackoff()

            else:
                # ... which was NOT ACKed

                # decrement 'retriesLeft' counter associated with that packet
                assert self.pktToSend['mac']['retriesLeft'] > 0
                self.pktToSend['mac']['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.pktToSend['mac']['retriesLeft'] == 0:

                    # remove packet from queue
                    self.getTxQueue().remove(self.pktToSend)

                    # drop
                    self.mote.radio.drop_packet(
                        pkt     = self.pktToSend,
                        reason  = SimEngine.SimLog.LOG_TSCH_DROP_MAX_RETRIES['type']
                    )

                # update backoff
                if self.getSchedule()[ts]['dir'] == d.DIR_TXRX_SHARED:
                    if self.getSchedule()[ts]['neighbor'] == self.mote._myNeighbors():
                        if self.backoffBroadcastExponent < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffBroadcastExponent += 1
                        self.backoffBroadcast = random.randint(0, 2 ** self.backoffBroadcastExponent - 1)
                    else:
                        if self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] += 1
                        self.backoffPerNeigh[self.getSchedule()[ts]['neighbor']] = random.randint(0, 2 ** self.backoffExponentPerNeigh[self.getSchedule()[ts]['neighbor']] - 1)
        
        # end of radio activity, not waiting for anything
        self.waitingFor = None
        self.pktToSend  = None

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
        
        # abort if I received a frame for someone else
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
            self.asnLastSync = asn # packet-based sync
        
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

        if   packet['mac']['dstMac']==self.mote.id:
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
            elif 'net' in packet:
                self.mote.sixlowpan.recvPacket(packet)
            else:
                raise SystemError()

        elif packet['mac']['dstMac']==d.BROADCAST_ADDRESS:
            # link-layer broadcast
            
            # do NOT ACK frame (broadcast)
            isACKed = False
            
            # dispatch to the right upper layer
            if   packet['type'] == d.TSCH_TYPE_EB:
                self._tsch_action_receiveEB(packet)
            elif 'net' in packet:
                assert packet['type']==d.RPL_TYPE_DIO
                self.mote.sixlowpan.recvPacket(packet)
            else:
                raise SystemError()

        else:
            raise SystemError()

        return isACKed

    def computeTimeOffsetToDagRoot(self):
        """
        calculate time offset compared to the DAGroot
        """
        
        assert self.getIsSync()
        assert self.asnLastSync!=None
        
        if self.mote.dagRoot:
            return 0.0

        offset               = 0.0

        child                = self.mote
        parent               = self.engine.motes[self.mote.rpl.getPreferredParent()]
        while True:
            secSinceSync     = (self.engine.getAsn()-child.tsch.asnLastSync)*self.settings.tsch_slotDuration
            # FIXME: for ppm, should we not /10^6?
            relDrift         = child.tsch.drift - parent.tsch.drift  # ppm
            offset          += relDrift * secSinceSync               # us
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
    
    def tsch_schedule_next_listeningForEB_cell(self):
        
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
        self.tsch_schedule_next_listeningForEB_cell()
    
    # active cell

    def tsch_schedule_next_active_cell(self):
        
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
        
        # local shorthands
        asn  = self.engine.getAsn()
        ts   = asn % self.settings.tsch_slotframeLength
        cell = self.schedule[ts]

        # make sure this is an active slot
        assert ts in self.schedule
        
        # make sure we're not in the middle of a TX/RX operation
        assert self.waitingFor == None
        
        # make sure we are not busy sending a packet
        assert self.pktToSend == None
        
        # signal to scheduling function that a cell to a neighbor has been triggered
        self.mote.sf.signal_cell_elapsed(
            self.mote,
            cell['neighbor'],
            cell['dir'],
        )
        
        # execute cell
        if   cell['dir'] == d.DIR_TX:
            # TX cell
            
            # find packet to send
            for pkt in self.txQueue:
                if pkt['mac']['dstMac'] == cell['neighbor']:
                    self.pktToSend = pkt
                    break
            
            # send packet
            if self.pktToSend:
                self._tsch_action_TX(self.pktToSend)
        
        elif cell['dir'] == d.DIR_TXRX_SHARED:
            # TXRXSHARED cell
            
            # find packet to send
            if self.backoffBroadcast == 0:
                for pkt in self.txQueue:
                    if  (
                            # DIOs and EBs always on minimal cell
                            (
                                pkt['type'] in [d.RPL_TYPE_DIO,d.TSCH_TYPE_EB]
                            )
                            or
                            # other frames on the minimal cell if no dedicated cells to the nextHop
                            (
                                self.getTxCells(pkt['mac']['dstMac']) == []
                                and
                                self.getSharedCells(pkt['mac']['dstMac'])==[]
                            )
                        ):
                        self.pktToSend = pkt
                        break
            
            # decrement backoff
            if self.backoffBroadcast > 0:
                self.backoffBroadcast -= 1
            
            # send packet, or receive
            if self.pktToSend:
                self._tsch_action_TX(self.pktToSend)
            else:
                self._tsch_action_RX()
        
        elif cell['dir'] == d.DIR_RX:
            # RX cell
            
            # receive
            self._tsch_action_RX()

        # schedule next active cell
        self.tsch_schedule_next_active_cell()
    
    def _tsch_action_TX(self,pktToSend):
        
        # local shorthands
        asn  = self.engine.getAsn()
        ts   = asn % self.settings.tsch_slotframeLength
        cell = self.schedule[ts]
        
        # inform SF cell is used
        self.mote.sf.signal_cell_used(
            self.mote,
            cell['neighbor'],
            cell['dir'],
            d.DIR_TX,
            pktToSend['type'],
        )
        
        # update cell stats
        cell['numTx'] += 1
        
        # send packet to the radio
        self.mote.radio.startTx(
            channel          = cell['ch'],
            packet           = pktToSend,
        )

        # indicate that we're waiting for the TX operation to finish
        self.waitingFor      = d.DIR_TX
        self.channel         = cell['ch']
        
    def _tsch_action_RX(self):
        
        # local shorthands
        asn  = self.engine.getAsn()
        ts   = asn % self.settings.tsch_slotframeLength
        cell = self.schedule[ts]

        # start listening
        self.mote.radio.startRx(
            channel          = cell['ch'],
        )

        # indicate that we're waiting for the RX operation to finish
        self.waitingFor      = d.DIR_RX
        self.channel         = cell['ch']

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
                        'mac': {
                            'srcMac':       self.mote.id,            # from mote
                            'dstMac':       d.BROADCAST_ADDRESS,     # broadcast
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

    # backoff

    def _resetBroadcastBackoff(self):
        self.backoffBroadcast               = 0
        self.backoffBroadcastExponent       = d.TSCH_MIN_BACKOFF_EXPONENT - 1

    def _resetBackoffPerNeigh(self, neigh):
        self.backoffPerNeigh[neigh]         = 0
        self.backoffExponentPerNeigh[neigh] = d.TSCH_MIN_BACKOFF_EXPONENT - 1
