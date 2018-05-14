"""
"""

# =========================== imports =========================================

import random

# Mote sub-modules
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
        self.schedule                       = {}      # indexed by slotOffset, contains cell
        self.txQueue                        = []
        self.pktToSend                      = None
        self.waitingFor                     = None
        self.channel                        = None
        self.asnLastSync                    = None
        self.isSync                         = False
        self.join_proxy                     = None
        self.iAmSendingEBs                  = False
        self.iAmSendingDIOs                 = False
        self.drift                          = random.uniform(-d.RADIO_MAXDRIFT, d.RADIO_MAXDRIFT)

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
    
    def _getCells(self, neighbor, cellOptions):
        if neighbor!=None:
            assert type(neighbor)==int
        
        if neighbor is None:
            return [
                (slotOffset, c['channelOffset'], c['neighbor'])
                    for (slotOffset, c) in self.schedule.items()
                        if sorted(c['cellOptions']) == sorted(cellOptions)
            ]
        else:
            return [
                (slotOffset, c['channelOffset'], c['neighbor'])
                    for (slotOffset, c) in self.schedule.items()
                        if sorted(c['cellOptions']) == sorted(cellOptions) and c['neighbor'] == neighbor
            ]
    
    def getTxCells(self, neighbor = None):
        return self._getCells(
            neighbor    = neighbor,
            cellOptions = [d.CELLOPTION_TX],
        )
    def getRxCells(self, neighbor = None):
        return self._getCells(
            neighbor    = neighbor,
            cellOptions = [d.CELLOPTION_RX],
        )
    def getTxRxSharedCells(self, neighbor = None):
        return self._getCells(
            neighbor    = neighbor,
            cellOptions = [d.CELLOPTION_TX,d.CELLOPTION_RX,d.CELLOPTION_SHARED],
        )
    
    # activate
    
    def startSendingEBs(self):
        self.iAmSendingEBs  = True
    
    def startSendingDIOs(self):
        self.iAmSendingDIOs = True
    
    # minimal

    def add_minimal_cell(self):

        self.addCell(
            slotOffset       = 0,
            channelOffset    = 0,
            neighbor         = None, # None means "any"
            cellOptions      = [d.CELLOPTION_TX,d.CELLOPTION_RX,d.CELLOPTION_SHARED],
        )

    # schedule interface

    def addCell(self, slotOffset, channelOffset, neighbor, cellOptions):
    
        assert isinstance(slotOffset, int)
        assert isinstance(channelOffset, int)
        if neighbor!=None:
            assert isinstance(neighbor, int)
        assert isinstance(cellOptions, list)
        
        # make sure I have no activity at that slotOffset already
        assert slotOffset not in self.schedule.keys()
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_ADD_CELL,
            {
                '_mote_id':       self.mote.id,
                'slotOffset':     slotOffset,
                'channelOffset':  channelOffset,
                'neighbor':       neighbor,
                'cellOptions':    cellOptions,
            }
        )
        
        # add cell
        self.schedule[slotOffset] = {
            'channelOffset':      channelOffset,
            'neighbor':           neighbor,
            'cellOptions':        cellOptions,
            # backoff management
            'backoff':            0,
            'backoffExponent':    d.TSCH_MIN_BACKOFF_EXPONENT,
            # per-cell statistics
            'numTx':              0,
            'numTxAck':           0,
            'numRx':              0,
        }
        
        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_next_active_cell()

    def deleteCell(self, slotOffset, channelOffset, neighbor, cellOptions):
        assert isinstance(slotOffset, int)
        assert isinstance(channelOffset, int)
        assert isinstance(neighbor, int)
        assert isinstance(cellOptions, list)
        
        # make sure I'm removing a cell that I have in my schedule
        assert slotOffset in self.schedule.keys()
        assert self.schedule[slotOffset]['channelOffset']  == channelOffset
        assert self.schedule[slotOffset]['neighbor']       == neighbor
        assert self.schedule[slotOffset]['cellOptions']    == cellOptions
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_DELETE_CELL,
            {
                '_mote_id':       self.mote.id,
                'slotOffset':     slotOffset,
                'channelOffset':  channelOffset,
                'neighbor':       neighbor,
                'cellOptions':    cellOptions,
            }
        )

        # delete cell
        del self.schedule[slotOffset]

        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self.tsch_schedule_next_active_cell()

    # data interface with upper layers

    def enqueue(self, packet):

        assert packet['type'] != d.PKT_TYPE_DIO
        assert packet['type'] != d.PKT_TYPE_EB
        assert 'srcMac' in packet['mac']
        assert 'dstMac' in packet['mac']
        
        goOn = True
        
        # check there is space in txQueue
        if goOn:
            if len(self.txQueue) >= d.TSCH_QUEUE_SIZE:
                # my TX queue is full
                
                # drop
                self.mote.drop_packet(
                    packet  = packet,
                    reason  = SimEngine.SimLog.DROPREASON_TXQUEUE_FULL,
                )
                
                # couldn't enqueue
                goOn = False
        
        # check that I have cell to transmit on
        if goOn:
            if (not self.getTxCells()) and (not self.getTxRxSharedCells()):
                # I don't have any cell to transmit on
                
                # drop
                self.mote.drop_packet(
                    packet  = packet,
                    reason  = SimEngine.SimLog.DROPREASON_NO_TX_CELLS,
                )
                
                # couldn't enqueue
                goOn = False
        
        # if I get here, everyting is OK, I can enqueue
        if goOn:
            # set retriesLeft which should be renewed at every hop
            packet['mac']['retriesLeft'] = d.TSCH_MAXTXRETRIES
            # add to txQueue
            self.txQueue    += [packet]
        
        return goOn

    # interface with radio

    def txDone(self, isACKed):
        assert isACKed in [True,False]
        
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength
        cell       = self.schedule[slotOffset]
        
        assert slotOffset in self.getSchedule()
        assert d.CELLOPTION_TX in cell['cellOptions']
        assert self.waitingFor == d.WAITING_FOR_TX
        
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
            
            assert self.pktToSend['type'] in [d.PKT_TYPE_EB,d.PKT_TYPE_DIO]
            assert isACKed==False
            
            # DIOs and EBs were never in txQueue, no need to remove
            
        else:
            # I just sent a unicast packet...
        
            # TODO send txDone up
            
            # update the cell's backoff
            newBackoff         = cell['backoff']
            newBackoffExponent = cell['backoffExponent']
            if d.CELLOPTION_SHARED in cell['cellOptions']:
                # just transmitted in a SHARED cell
                
                # update backoff according to Section 6.2.5.3 of IEEE802.15.4-2015
                if isACKed==True:
                    newBackoff              = 0
                    newBackoffExponent      = d.TSCH_MIN_BACKOFF_EXPONENT
                else:
                    newBackoff              = random.randint(0,(2**cell['backoffExponent'])-1)
                    if cell['backoffExponent']<d.TSCH_MAX_BACKOFF_EXPONENT:
                        newBackoffExponent  = cell['backoffExponent']+1
            else:
                # just transmitted in a dedicated cell
                
                # Section 6.2.5.3 of IEEE802.15.4-2015: "The backoff window is reset to the minimum value if the transmission in a dedicated link is successful and the transmit queue is then empty."
                if (isACKed==True) and (not self.txQueue):
                    newBackoff                   = 0
                    newBackoffExponent           = d.TSCH_MIN_BACKOFF_EXPONENT
            if (newBackoff!=cell['backoff']) or (newBackoffExponent!=cell['backoffExponent']):
                # apply
                cell['backoff']             = newBackoff
                cell['backoffExponent']     = newBackoffExponent
                
                # log
                self.log(
                    SimEngine.SimLog.LOG_TSCH_BACKOFFCHANGED,
                    {
                        '_mote_id':       self.mote.id,
                        'cell':           cell,
                    }
                )
            
            # indicate unicast transmission to the neighbor table
            self.mote.neighbors_indicate_tx(self.pktToSend,isACKed)
            
            if isACKed:
                # ... which was ACKed

                # update schedule stats
                cell['numTxAck'] += 1

                # time correction
                if cell['neighbor'] == self.mote.rpl.getPreferredParent():
                    self.asnLastSync = asn # ACK-based sync
                
                # remove packet from queue
                self.getTxQueue().remove(self.pktToSend)

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
                    self.mote.drop_packet(
                        packet  = self.pktToSend,
                        reason  = SimEngine.SimLog.DROPREASON_MAX_RETRIES,
                    )
        
        # end of radio activity, not waiting for anything
        self.waitingFor = None
        self.pktToSend  = None

    def rxDone(self, packet):
        
        # local variables
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength
        
        # make sure I'm in the right state
        if self.getIsSync():
            assert slotOffset in self.getSchedule()
            assert d.CELLOPTION_RX in self.getSchedule()[slotOffset]['cellOptions']
            assert self.waitingFor == d.WAITING_FOR_RX
        
        # not waiting for anything anymore
        self.waitingFor = None
        
        # abort if received nothing (idle listen)
        if packet==None:
            return False # isACKed
        
        # indicate reception to the neighbor table
        self.mote.neighbors_indicate_rx(packet)
        
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
            self.getSchedule()[slotOffset]['numRx'] += 1
        
        if   packet['mac']['dstMac']==self.mote.id:
            # link-layer unicast to me
            
            # ACK frame
            isACKed = True
            
            # dispatch to the right upper layer
            if   packet['type'] in [
                    d.PKT_TYPE_SIXP_ADD_REQUEST,
                    d.PKT_TYPE_SIXP_ADD_RESPONSE,
                    d.PKT_TYPE_SIXP_DELETE_REQUEST,
                    d.PKT_TYPE_SIXP_DELETE_RESPONSE,
                ]:
                self.mote.sixp.receive(packet)
            elif 'net' in packet:
                self.mote.sixlowpan.recvPacket(packet)
            else:
                raise SystemError()

        elif packet['mac']['dstMac']==d.BROADCAST_ADDRESS:
            # link-layer broadcast
            
            # do NOT ACK frame (broadcast)
            isACKed = False
            
            # dispatch to the right upper layer
            if   packet['type'] == d.PKT_TYPE_EB:
                self._tsch_action_receiveEB(packet)
            elif 'net' in packet:
                assert packet['type']==d.PKT_TYPE_DIO
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
        if self.mote.rpl.getPreferredParent()!=None:
            parent_id        = self.mote.rpl.getPreferredParent()
        else:
            parent_id        = self.mote.tsch.join_proxy
        parent               = self.engine.motes[parent_id]
        parents              = []
        while True:

            if parent.id in parents:
                # loop is detected; return the current offset value
                return offset
            else:
                # record the current parent for loop detection
                parents.append(parent.id)

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
            intraSlotOrder   = d.INTRASLOTORDER_STARTSLOT,
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
        self.waitingFor = d.WAITING_FOR_RX
        
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

        for (slotOffset, cell) in self.schedule.items():
            if   slotOffset == tsCurrent:
                tsDiff        = self.settings.tsch_slotframeLength
            elif slotOffset > tsCurrent:
                tsDiff        = slotOffset-tsCurrent
            elif slotOffset < tsCurrent:
                tsDiff        = (slotOffset+self.settings.tsch_slotframeLength)-tsCurrent
            else:
                raise SystemError()

            if (not tsDiffMin) or (tsDiff < tsDiffMin):
                tsDiffMin     = tsDiff

        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn              = asn+tsDiffMin,
            cb               = self._tsch_action_active_cell,
            uniqueTag        = (self.mote.id, '_tsch_action_active_cell'),
            intraSlotOrder   = d.INTRASLOTORDER_STARTSLOT,
        )
    
    def _tsch_action_active_cell(self):
        
        # local shorthands
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength
        cell       = self.schedule[slotOffset]

        # make sure this is an active slot
        assert slotOffset in self.schedule
        
        # make sure we're not in the middle of a TX/RX operation
        assert self.waitingFor == None
        
        # make sure we are not busy sending a packet
        assert self.pktToSend == None
        
        # execute cell
        if   cell['cellOptions'] == [d.CELLOPTION_TX]:
            # dedicated TX cell
            
            # find packet to send
            for pkt in self.txQueue:
                if pkt['mac']['dstMac'] == cell['neighbor']:
                    self.pktToSend = pkt
                    break
            
            # notify SF
            self.mote.sf.indication_dedicated_tx_cell_elapsed(
                cell    = cell,
                used    = (self.pktToSend!=None),
            )
            
            # send packet
            if self.pktToSend:
                self._tsch_action_TX(self.pktToSend)
        
        elif sorted(cell['cellOptions']) == sorted([d.CELLOPTION_TX,d.CELLOPTION_RX,d.CELLOPTION_SHARED]):
            # minimal cell
            
            # look for packet to send
            if cell['backoff']>0:
                # backoff is active, we cannot send
                
                # decrement backoff
                cell['backoff']-=1
            else:
                # no backoff in place, look for packet
                
                # try to find a packet to neighbor to which I don't have any dedicated cell(s)...
                if not self.pktToSend:
                    for pkt in self.txQueue:
                        if  (
                                # DIOs and EBs always on minimal cell
                                (
                                    pkt['type'] in [d.PKT_TYPE_DIO,d.PKT_TYPE_EB]
                                )
                                or
                                # other frames on the minimal cell if no dedicated cells to the nextHop
                                (
                                    self.getTxCells(pkt['mac']['dstMac']) == []
                                    and
                                    self.getTxRxSharedCells(pkt['mac']['dstMac'])==[]
                                )
                            ):
                            self.pktToSend = pkt
                            break

                # ... if no such packet, probabilistically generate an EB or a DIO
                if not self.pktToSend:
                    if self.mote.clear_to_send_EBs_DIOs_DATA():
                        prob = self.settings.tsch_probBcast_ebDioProb/(1+self.mote.numNeighbors())
                        if random.random()<prob:
                            if random.random()<0.50:
                                if self.iAmSendingEBs:
                                    self.pktToSend = self._create_EB()
                            else:
                                if self.iAmSendingDIOs:
                                    self.pktToSend = self.mote.rpl._create_DIO()

            # send packet, or receive
            if self.pktToSend:
                self._tsch_action_TX(self.pktToSend)
            else:
                self._tsch_action_RX()
        
        elif cell['cellOptions'] == [d.CELLOPTION_RX]:
            # dedicated RX cell
            
            # receive
            self._tsch_action_RX()

        # schedule next active cell
        self.tsch_schedule_next_active_cell()
    
    def _tsch_action_TX(self,pktToSend):
        
        # local shorthands
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength
        cell       = self.schedule[slotOffset]
        
        # update cell stats
        cell['numTx'] += 1
        
        # send packet to the radio
        self.mote.radio.startTx(
            channel          = cell['channelOffset'],
            packet           = pktToSend,
        )

        # indicate that we're waiting for the TX operation to finish
        self.waitingFor      = d.WAITING_FOR_TX
        self.channel         = cell['channelOffset']
        
    def _tsch_action_RX(self):
        
        # local shorthands
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength
        cell       = self.schedule[slotOffset]

        # start listening
        self.mote.radio.startRx(
            channel          = cell['channelOffset'],
        )

        # indicate that we're waiting for the RX operation to finish
        self.waitingFor      = d.WAITING_FOR_RX
        self.channel         = cell['channelOffset']

    # EBs
    
    def _create_EB(self):
        
        # create
        newEB = {
            'type':               d.PKT_TYPE_EB,
            'app': {
                'join_priority':  self.mote.rpl.getDagRank(),
            },
            'mac': {
                'srcMac':         self.mote.id,            # from mote
                'dstMac':         d.BROADCAST_ADDRESS,     # broadcast
            },
        }
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_EB_TX,
            {
                "_mote_id":  self.mote.id,
                "packet":    newEB,
            }
        )
        
        return newEB

    def _tsch_action_receiveEB(self, packet):
        
        assert packet['type'] == d.PKT_TYPE_EB
        
        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_EB_RX,
            {
                "_mote_id":  self.mote.id,
                "packet":    packet,
            }
        )
        
        # abort if I'm the root
        if self.mote.dagRoot:
            return
        
        if not self.getIsSync():
            # receiving EB while not sync'ed
            
            # I'm now sync'ed!
            self.setIsSync(True) # mote
            
            # the mote that sent the EB is now by join proxy
            self.join_proxy = packet['mac']['srcMac']
            
            # activate different services
            self.mote.sf.startMonitoring() # mote
            
            # add the minimal cell to the schedule (read from EB)
            self.add_minimal_cell() # mote

            # trigger join process
            self.mote.secjoin.startJoinProcess()
