#!/usr/bin/python
'''
\brief Model of a 6TiSCH mote.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
'''

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Mote')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

#============================ imports =========================================

import copy
import random
import threading
import math

import SimEngine
import SimSettings
import Propagation
import Topology

#============================ defines =========================================

#============================ body ============================================

class Mote(object):
    
    # sufficient num. of tx to estimate pdr by ACK
    NUM_SUFFICIENT_TX                  = 10
    # maximum number of tx counter to forget old data
    NUM_MAX_COUNTER                    = NUM_SUFFICIENT_TX*2
    
    DIR_TX                             = 'TX'
    DIR_RX                             = 'RX'
    
    DEBUG                              = 'DEBUG'
    INFO                               = 'INFO'
    WARNING                            = 'WARNING'
    ERROR                              = 'ERROR'
    
    #=== app
    APP_TYPE_DATA                      = 'DATA'
    #=== rpl
    RPL_PARENT_SWITCH_THRESHOLD        = 768 # corresponds to 1.5 hops. 6tisch minimal draft use 384 for 2*ETX.
    RPL_MIN_HOP_RANK_INCREASE          = 256
    RPL_MAX_ETX                        = 4
    RPL_MAX_RANK_INCREASE              = RPL_MAX_ETX*RPL_MIN_HOP_RANK_INCREASE*2 # 4 transmissions allowed for rank increase for parents
    RPL_MAX_TOTAL_RANK                 = 256*RPL_MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
    RPL_PARENT_SET_SIZE                = 3
    DEFAULT_DIO_INTERVAL_MIN           = 3 # log2(DIO_INTERVAL_MIN), with DIO_INTERVAL_MIN expressed in ms
    DEFAULT_DIO_INTERVAL_DOUBLINGS     = 20 # maximum number of doublings of DIO_INTERVAL_MIN (DIO_INTERVAL_MAX = 2^(DEFAULT_DIO_INTERVAL_MIN+DEFAULT_DIO_INTERVAL_DOUBLINGS) ms)
    DEFAULT_DIO_REDUNDANCY_CONSTANT    = 10 # number of hearings to suppress next transmission in the current interval
    
    #=== otf
    OTF_TRAFFIC_SMOOTHING              = 0.5
    #=== 6top
    #=== tsch
    TSCH_QUEUE_SIZE                    = 10
    TSCH_MAXTXRETRIES                  = 5    
    #=== radio
    RADIO_MAXDRIFT                     = 30 # in ppm
    #=== battery
    # see A Realistic Energy Consumption Model for TSCH Networks.
    # Xavier Vilajosana, Qin Wang, Fabien Chraim, Thomas Watteyne, Tengfei
    # Chang, Kris Pister. IEEE Sensors, Vol. 14, No. 2, February 2014.
    CHARGE_Idle_uC                     = 24.60
    CHARGE_TxDataRxAck_uC              = 64.82
    CHARGE_TxData_uC                   = 49.37
    CHARGE_RxDataTxAck_uC              = 76.90
    CHARGE_RxData_uC                   = 64.65
    
    def __init__(self,id):
        
        # store params
        self.id                        = id
        
        # local variables
        self.dataLock                  = threading.RLock()
        
        self.engine                    = SimEngine.SimEngine()
        self.settings                  = SimSettings.SimSettings()
        self.propagation               = Propagation.Propagation()
        
        # role
        self.dagRoot                   = False
        # rpl
        self.rank                      = None
        self.dagRank                   = None
        self.parentSet                 = []
        self.preferredParent           = None
        self.rplRxDIO                  = {}                    # indexed by neighbor, contains int
        self.neighborRank              = {}                    # indexed by neighbor
        self.neighborDagRank           = {}                    # indexed by neighbor
        self.trafficPortionPerParent   = {}                    # indexed by parent, portion of outgoing traffic
        # otf
        self.asnOTFevent               = None
        self.otfHousekeepingPeriod     = self.settings.otfHousekeepingPeriod
        self.timeBetweenOTFevents      = []
        self.inTraffic                 = {}                    # indexed by neighbor
        self.inTrafficMovingAve        = {}                    # indexed by neighbor
        # 6top
        self.numCellsToNeighbors       = {}                    # indexed by neighbor, contains int
        # changing this threshold the detection of a bad cell can be
        # tuned, if as higher the slower to detect a wrong cell but the more prone
        # to avoid churn as lower the faster but with some chances to introduces
        # churn due to unstable medium
        self.topPdrThreshold           = self.settings.topPdrThreshold
        self.topHousekeepingPeriod     = self.settings.topHousekeepingPeriod

        # tsch
        self.txQueue                   = []
        self.pktToSend                 = None
        self.schedule                  = {}                    # indexed by ts, contains cell
        self.waitingFor                = None
        self.timeCorrectedSlot         = None
        # radio
        self.txPower                   = 0                     # dBm
        self.antennaGain               = 0                     # dBi
        self.minRssi                   = self.settings.minRssi # dBm
        self.noisepower                = -105                  # dBm
        self.drift                     = random.uniform(-self.RADIO_MAXDRIFT, self.RADIO_MAXDRIFT)
        # wireless
        self.RSSI                      = {}                    # indexed by neighbor
        self.PDR                       = {}                    # indexed by neighbor
        # location
        # battery
        self.chargeConsumed            = 0
        
        # stats
        self._resetMoteStats()
        self._resetQueueStats()
        self._resetLatencyStats()
        self._resetHopsStats()
    
    #======================== stack ===========================================
    
    #===== role
    
    def role_setDagRoot(self):
        self.dagRoot              = True
        self.rank                 = 0
        self.dagRank              = 0
        self.packetLatencies      = [] # in slots
        self.packetHops           = []
    
    #===== application
    
    def _app_schedule_sendData(self,init=False):
        ''' create an event that is inserted into the simulator engine to send the data according to the traffic'''
        
        if not init:
            # compute random delay
            delay       = self.settings.pkPeriod*(1+random.uniform(-self.settings.pkPeriodVar,self.settings.pkPeriodVar))            
        else:
            # compute initial time within the range of [next asn, next asn+pkPeriod]
            delay       = self.settings.slotDuration + self.settings.pkPeriod*random.random()
            
        assert delay>0    
        # schedule
        self.engine.scheduleIn(
            delay       = delay,
            cb          = self._app_action_sendData,
            uniqueTag   = (self.id, 'sendData'),
            priority    = 2,
        )
    
    def _app_schedule_enqueueData(self):
        ''' create an event that is inserted into the simulator engine to send a data burst'''
        
        # schedule numPacketsBurst packets at burstTime
        for i in xrange(self.settings.numPacketsBurst):
            self.engine.scheduleIn(
                delay       = self.settings.burstTime,
                cb          = self._app_action_enqueueData,
                uniqueTag   = (self.id, 'enqueueData'),
                priority    = 2,
            )
    
    def _app_action_sendData(self):
        ''' actual send data function. Evaluates queue length too '''
        
        # enqueue data
        self._app_action_enqueueData()
        
        # schedule next _app_action_sendData
        self._app_schedule_sendData()
    
    def _app_action_enqueueData(self):
        ''' actual enqueue data function '''
        
        #self._log(self.DEBUG,"[app] _app_action_sendData")
        
        # only start sending data if I have some TX cells
        if self.getTxCells():
            
            # create new packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           self.APP_TYPE_DATA,
                'payload':        [self.id,self.engine.getAsn(),1], # the payload is used for latency and number of hops calculation
                'retriesLeft':    self.TSCH_MAXTXRETRIES
            }

            # update mote stats
            self._incrementMoteStats('appGenerated')
                        
            # enqueue packet in TSCH queue
            isEnqueued = self._tsch_enqueue(newPacket)
            
            if not isEnqueued:
                # update mote stats
                self._incrementMoteStats('droppedAppFailedEnqueue')
                
    
    #===== rpl
    
    def _rpl_schedule_sendDIO(self,init=False):
        
        with self.dataLock:

            asn    = self.engine.getAsn()
            ts     = asn%self.settings.slotframeLength
                            
            if not init:
                cycle = int(math.ceil(self.settings.dioPeriod/(self.settings.slotframeLength*self.settings.slotDuration)))
            else:
                cycle = 1            
            
            # schedule at start of next cycle
            self.engine.scheduleAtAsn(
                asn         = asn-ts+cycle*self.settings.slotframeLength,
                cb          = self._rpl_action_sendDIO,
                uniqueTag   = (self.id,'DIO'),
                priority    = 3,
            )
            
            # this function is used for debugging RPL
            '''
            self.engine.scheduleAtAsn(
                asn         = asn-ts+self.settings.slotframeLength,
                cb          = self._rpl_action_checkRPL,
                uniqueTag   = (self.id,'checkRPL'),
                priority    = 4,
            )
            '''
    
    def _rpl_action_checkRPL(self):
        parentSet=[(parent.id, parent.rank) for parent in self.parentSet]
        if parentSet:
            max_parent_id, max_parent_rank = max(parentSet,key=lambda x:x[1])
            if self.rank<=max_parent_rank:
                print self.id, self.rank
                print parentSet
            assert self.rank>max_parent_rank
    
    def _rpl_action_sendDIO(self):
        
        #self._log(self.DEBUG,"[rpl] _rpl_action_sendDIO")
        
        with self.dataLock:
            
            if self.rank!=None and self.dagRank!=None:
                
                # update mote stats
                self._incrementMoteStats('rplTxDIO')
                
                # log charge usage for sending DIO is currently neglected
                # self._logChargeConsumed(self.CHARGE_TxData_uC)
                
                # "send" DIO to all neighbors
                for neighbor in self._myNeigbors():
                    
                    # don't update DAGroot
                    if neighbor.dagRoot:
                        continue
                    
                    # don't update poor link
                    if neighbor._rpl_calcRankIncrease(self)>self.RPL_MAX_RANK_INCREASE:
                        continue
                    
                    # log charge usage (for neighbor) for receiving DIO is currently neglected
                    # neighbor._logChargeConsumed(self.CHARGE_RxData_uC)
                    
                    # in neighbor, update my rank/DAGrank
                    neighbor.neighborDagRank[self]    = self.dagRank
                    neighbor.neighborRank[self]       = self.rank
                    
                    # in neighbor, update number of DIOs received
                    if self not in neighbor.rplRxDIO:
                        neighbor.rplRxDIO[self]  = 0
                    neighbor.rplRxDIO[self]     += 1
                    
                    # update mote stats
                    self._incrementMoteStats('rplRxDIO')
                    
                    # skip useless housekeeping
                    if not neighbor.rank or self.rank<neighbor.rank:
                        # in neighbor, do RPL housekeeping
                        neighbor._rpl_housekeeping()                        
                    
                    # update time correction
                    if neighbor.preferredParent == self:
                        asn                        = self.engine.getAsn() 
                        neighbor.timeCorrectedSlot = asn
            
            # schedule to send the next DIO
            self._rpl_schedule_sendDIO()
    
    def _rpl_housekeeping(self):
        with self.dataLock:
            
            #===
            # refresh the following parameters:
            # - self.preferredParent
            # - self.rank
            # - self.dagRank
            # - self.parentSet
            
            # calculate my potential rank with each of the motes I have heard a DIO from
            potentialRanks = {}
            for (neighbor,neighborRank) in self.neighborRank.items():
                # calculate the rank increase to that neighbor
                rankIncrease = self._rpl_calcRankIncrease(neighbor)
                if rankIncrease!=None and rankIncrease<=min([self.RPL_MAX_RANK_INCREASE, self.RPL_MAX_TOTAL_RANK-neighborRank]):                
                    # record this potential rank
                    potentialRanks[neighbor] = neighborRank+rankIncrease
            
            # sort potential ranks
            sorted_potentialRanks = sorted(potentialRanks.iteritems(), key=lambda x:x[1])
            
            # switch parents only when rank difference is large enough
            for i in range(1,len(sorted_potentialRanks)):
                if sorted_potentialRanks[i][0] in self.parentSet:
                    # compare the selected current parent with motes who have lower potential ranks 
                    # and who are not in the current parent set 
                    for j in range(i):                    
                        if sorted_potentialRanks[j][0] not in self.parentSet:
                            if sorted_potentialRanks[i][1]-sorted_potentialRanks[j][1]<self.RPL_PARENT_SWITCH_THRESHOLD:
                                mote_rank = sorted_potentialRanks.pop(i)
                                sorted_potentialRanks.insert(j,mote_rank)
                                break
                    
            # pick my preferred parent and resulting rank
            if sorted_potentialRanks:
                oldParentSet = set([parent.id for parent in self.parentSet])
                
                (newPreferredParent,newrank) = sorted_potentialRanks[0]
                
                # compare a current preferred parent with new one
                if self.preferredParent and newPreferredParent!=self.preferredParent:
                    for (mote,rank) in sorted_potentialRanks[:self.RPL_PARENT_SET_SIZE]:
                        
                        if mote == self.preferredParent:                      
                            # switch preferred parent only when rank difference is large enough
                            if rank-newrank<self.RPL_PARENT_SWITCH_THRESHOLD:
                                (newPreferredParent,newrank) = (mote,rank)
                            
                    # update mote stats
                    self._incrementMoteStats('rplChurnPrefParent')
                    # log
                    self._log(
                        self.INFO,
                        "[rpl] churn: preferredParent {0}->{1}",
                        (self.preferredParent.id,newPreferredParent.id),
                    )
                
                # update mote stats
                if self.rank and newrank!=self.rank:
                    self._incrementMoteStats('rplChurnRank')
                    # log
                    self._log(
                        self.INFO,
                        "[rpl] churn: rank {0}->{1}",
                        (self.rank,newrank),
                    )
                
                # store new preferred parent and rank
                (self.preferredParent,self.rank) = (newPreferredParent,newrank)
                
                # calculate DAGrank
                self.dagRank = int(self.rank/self.RPL_MIN_HOP_RANK_INCREASE)
            
                # pick my parent set
                self.parentSet = [n for (n,_) in sorted_potentialRanks if self.neighborRank[n]<self.rank][:self.RPL_PARENT_SET_SIZE]
                assert self.preferredParent in self.parentSet
                
                if oldParentSet!=set([parent.id for parent in self.parentSet]):
                    self._incrementMoteStats('rplChurnParentSet')
                
            #===
            # refresh the following parameters:
            # - self.trafficPortionPerParent
            
            etxs        = dict([(p, 1.0/(self.neighborRank[p]+self._rpl_calcRankIncrease(p))) for p in self.parentSet])
            sumEtxs     = float(sum(etxs.values()))
            self.trafficPortionPerParent = dict([(p, etxs[p]/sumEtxs) for p in self.parentSet])
            
            # # uncomment the following lines to debug parent selection
            # print self.id
            # print [(parent.id, parent.rank) for parent in self.parentSet]
            # print [(parent[0].id, parent[0].rank) for parent in sorted_potentialRanks]
            # nonParents=set([(parent[0].id, parent[0].rank) for parent in sorted_potentialRanks])-set([(parent.id, parent.rank) for parent in self.parentSet])
            # print nonParents
            # if nonParents:
                # print max([parent.rank for parent in self.parentSet])
                # print min([parent[1] for parent in nonParents])
                # assert max([parent.rank for parent in self.parentSet])<=min([parent[1] for parent in nonParents])
            
            # remove TX cells to neighbor who are not in parent set
            for neighbor in self.numCellsToNeighbors.keys():
                if neighbor not in self.parentSet:
                
                    # log
                    self._log(
                        self.INFO,
                        "[otf] removing cell to {0}, since not in parentSet {1}",
                        (neighbor.id,[p.id for p in self.parentSet]),
                    )
                    
                    tsList=[ts for ts, cell in self.schedule.iteritems() if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX]
                    self._top_cell_deletion_sender(neighbor,tsList)
    
    def _rpl_calcRankIncrease(self, neighbor):
        
        with self.dataLock:
            
            # estimate the ETX to that neighbor
            etx = self._estimateETX(neighbor)
            
            # return if that failed
            if not etx:
                return
            
            # per draft-ietf-6tisch-minimal, rank increase is 2*ETX*RPL_MIN_HOP_RANK_INCREASE
            return int(2*self.RPL_MIN_HOP_RANK_INCREASE*etx)
    
    #===== otf
    
    def _otf_schedule_housekeeping(self):
        
        self.engine.scheduleIn(
            delay       = self.otfHousekeepingPeriod*(0.9+0.2*random.random()),
            cb          = self._otf_housekeeping,
            uniqueTag   = (self.id,'otfHousekeeping'),
            priority    = 4,
        )
    
    def _otf_housekeeping(self):
        '''
        OTF algorithm: decides when to add/delete cells.
        '''
        
        #self._log(self.DEBUG,"[otf] _otf_housekeeping")
        
        with self.dataLock:
            
            # calculate the "moving average" incoming traffic, in pkts since last cycle, per neighbor
            with self.dataLock:
                for neighbor in self._myNeigbors():
                    if neighbor in self.inTrafficMovingAve:
                        newTraffic  = 0
                        newTraffic += self.inTraffic[neighbor]*self.OTF_TRAFFIC_SMOOTHING               # new
                        newTraffic += self.inTrafficMovingAve[neighbor]*(1-self.OTF_TRAFFIC_SMOOTHING)  # old
                        self.inTrafficMovingAve[neighbor] = newTraffic
                    elif self.inTraffic[neighbor] != 0:
                        self.inTrafficMovingAve[neighbor] = self.inTraffic[neighbor]
            
            # reset the incoming traffic statistics, so they can build up until next housekeeping
            self._otf_resetInTraffic()
            
            # calculate my total generated traffic, in pkt/s
            genTraffic       = 0
            genTraffic      += 1.0/self.settings.pkPeriod # generated by me
            for neighbor in self.inTrafficMovingAve:
                genTraffic  += self.inTrafficMovingAve[neighbor]/self.otfHousekeepingPeriod   # relayed
            # convert to pkts/cycle
            genTraffic      *= self.settings.slotframeLength*self.settings.slotDuration
            
            remainingPortion = 0.0
            parent_portion = self.trafficPortionPerParent.items()
            # sort list so that the parent assigned larger traffic can be checked first
            sorted_parent_portion = sorted(parent_portion, key = lambda x: x[1], reverse=True)

            # split genTraffic across parents, trigger 6top to add/delete cells accordingly
            for (parent,portion) in sorted_parent_portion:
                
                # if some portion is remaining, this is added to this parent
                if remainingPortion != 0.0:
                    portion                             += remainingPortion
                    remainingPortion                     = 0.0
                    self.trafficPortionPerParent[parent] = portion
                    
                # calculate required number of cells to that parent
                etx = self._estimateETX(parent)
                if etx>self.RPL_MAX_ETX: # cap ETX
                    etx  = self.RPL_MAX_ETX
                reqCells      = int(math.ceil(portion*genTraffic*etx))
                
                # calculate the OTF threshold
                threshold     = int(math.ceil(portion*self.settings.otfThreshold))
                
                # measure how many cells I have now to that parent
                nowCells      = self.numCellsToNeighbors.get(parent,0)
                
                if nowCells<reqCells:
                    # I don't have enough cells
                    
                    # calculate how many to add
                    numCellsToAdd = reqCells-nowCells+(threshold+1)/2
                    
                    # log
                    self._log(
                        self.INFO,
                        "[otf] not enough cells to {0}: have {1}, need {2}, add {3}",
                        (parent.id,nowCells,reqCells,numCellsToAdd),
                    )
                    
                    # update mote stats
                    self._incrementMoteStats('otfAdd')
                    
                    # have 6top add cells
                    self._top_cell_reservation_request(parent,numCellsToAdd)
                    
                    # measure how many cells I have now to that parent
                    nowCells     = self.numCellsToNeighbors.get(parent,0)
                    
                    # store handled portion and remaining portion
                    if nowCells<reqCells:
                        handledPortion   = (float(nowCells)/etx)/genTraffic
                        remainingPortion = portion - handledPortion
                        self.trafficPortionPerParent[parent] = handledPortion
                    
                    # remember OTF triggered
                    otfTriggered = True
                
                elif reqCells<nowCells-threshold:
                    # I have too many cells
                    
                    # calculate how many to remove
                    numCellsToRemove = nowCells-reqCells-(threshold+1)/2
                    
                    # log
                    self._log(
                        self.INFO,
                        "[otf] too many cells to {0}:  have {1}, need {2}, remove {3}",
                        (parent.id,nowCells,reqCells,numCellsToRemove),
                    )
                    
                    # update mote stats
                    self._incrementMoteStats('otfRemove')
                    
                    # have 6top remove cells
                    self._top_removeCells(parent,numCellsToRemove)
                    
                    # remember OTF triggered
                    otfTriggered = True
                    
                else:
                    # nothing to do
                    
                    # remember OTF did NOT trigger
                    otfTriggered = False
                
                # maintain stats
                if otfTriggered:
                    now = self.engine.getAsn()
                    if not self.asnOTFevent:
                        assert not self.timeBetweenOTFevents
                    else:
                        self.timeBetweenOTFevents += [now-self.asnOTFevent]
                    self.asnOTFevent = now
            
            # schedule next housekeeping
            self._otf_schedule_housekeeping()
    
    def _otf_resetInTraffic(self):
        with self.dataLock:
            for neighbor in self._myNeigbors():
                self.inTraffic[neighbor] = 0
    
    def _otf_incrementIncomingTraffic(self,neighbor):
        with self.dataLock:
            self.inTraffic[neighbor] += 1
    
        
    
    #===== 6top

    def _top_schedule_housekeeping(self):
        
        self.engine.scheduleIn(
            delay       = self.topHousekeepingPeriod*(0.9+0.2*random.random()),
            cb          = self._top_housekeeping,
            uniqueTag   = (self.id,'topHousekeeping'),
            priority    = 5,
        )
    
    def _top_housekeeping(self):
        '''
        For each neighbor I have TX cells to, relocate cells if needed.
        '''
        
        # collect all neighbors I have TX cells to
        txNeighbors = [cell['neighbor'] for (ts,cell) in self.schedule.items() if cell['dir']==self.DIR_TX]
        
        # remove duplicates
        txNeighbors = list(set(txNeighbors))
        
        # do some housekeeping for each neighbor
        for neighbor in txNeighbors:
            self._top_housekeeping_per_neighbor(neighbor)
        
        self._top_schedule_housekeeping()
        
    def _top_housekeeping_per_neighbor(self,neighbor):
        '''
        For a particular neighbor, decide to relocate cells if needed.
        '''
        
        #===== step 0. refresh old statistics
        
        for (ts,cell) in self.schedule.items():
            if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX:
                # this is a TX cell to that neighbor
                
                # refresh statistics if it gets old
                if cell['numTx'] > self.NUM_MAX_COUNTER:
                    cell['numTx']    /= 2
                    cell['numTxAck'] /= 2
                
            
        #===== step 1. collect statistics:
        
        # pdr for each cell
        cell_pdr = []
        for (ts,cell) in self.schedule.items():
            if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX:
                # this is a TX cell to that neighbor
                
                # abort if not enough TX to calculate meaningful PDR
                if cell['numTx']<self.NUM_SUFFICIENT_TX:
                    continue
                
                # calculate pdr for that cell
                pdr = float(cell['numTxAck']) / float(cell['numTx'])
                
                # store result
                cell_pdr += [(ts,pdr)]
        
        # pdr for the bundle as a whole
        bundleNumTx     = sum([cell['numTx']    for cell in self.schedule.values() if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX])
        bundleNumTxAck  = sum([cell['numTxAck'] for cell in self.schedule.values() if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX])
        if bundleNumTx<self.NUM_SUFFICIENT_TX:
            bundlePdr   = None
        else:
            bundlePdr   = float(bundleNumTxAck) / float(bundleNumTx)
        
        #===== step 2. relocate worst cell in bundle, if any
        # this step will identify the cell with the lowest PDR in the bundle.
        # It it's PDR is self.topPdrThreshold lower than the average of the bundle
        # this step will move that cell.
        
        relocation = False
        
        if cell_pdr:
            
            # identify the cell with worst pdr, and calculate the average
            
            worst_ts   = None
            worst_pdr  = None
            ave_pdr    = float(sum([pdr for (ts,pdr) in cell_pdr]))/float(len(cell_pdr))
            
            for (ts,pdr) in cell_pdr:
                if worst_pdr==None or pdr<worst_pdr:
                    worst_ts  = ts
                    worst_pdr = pdr
            
            assert worst_ts!=None
            assert worst_pdr!=None
            
            # relocate worst cell is "bad enough"
            if worst_pdr<(ave_pdr/self.topPdrThreshold):
                
                # log
                self._log(
                    self.INFO,
                    "[6top] relocating cell ts {0} to {1} (pdr={2:.3f} significantly worse than others {3})",
                    (worst_ts,neighbor,worst_pdr,cell_pdr),
                )
                
                # measure how many cells I have now to that parent
                nowCells = self.numCellsToNeighbors.get(neighbor,0)
                
                # relocate: add new first
                self._top_cell_reservation_request(neighbor,1)
                
                # relocate: remove old only when successfully added 
                if nowCells < self.numCellsToNeighbors.get(neighbor,0):
                    self._top_cell_deletion_sender(neighbor,[worst_ts])
                
                    # update stats
                    self._incrementMoteStats('topRelocatedCells')
                
                    # remember I relocated a cell for that bundle
                    relocation = True
        
        #===== step 3. relocate the complete bundle
        # this step only runs if the previous hasn't, and we were able to
        # calculate a bundle PDR.
        # this step verifies that the average PDR for the complete bundle is
        # expected, given the RSSI to that neighbor. If it's lower, this step
        # will move all cells in the bundle.
        
        bundleRelocation = False
        
        if (not relocation) and bundlePdr!=None:
            
            # calculate the theoretical PDR to that neighbor, using the measured RSSI
            rssi            = self.getRSSI(neighbor)
            theoPDR         = Topology.Topology.rssiToPdr(rssi)
            
            # relocate complete bundle if measured RSSI is significantly worse than theoretical
            if bundlePdr<(theoPDR/self.topPdrThreshold):
                for (ts,_) in cell_pdr:
                    
                    # log
                    self._log(
                        self.INFO,
                        "[6top] relocating cell ts {0} to {1} (bundle pdr {2} << theoretical pdr {3})",
                        (ts,neighbor,bundlePdr,theoPDR),
                    )

                    # measure how many cells I have now to that parent
                    nowCells = self.numCellsToNeighbors.get(neighbor,0)
                    
                    # relocate: add new first
                    self._top_cell_reservation_request(neighbor,1)

                    # relocate: remove old only when successfully added 
                    if nowCells < self.numCellsToNeighbors.get(neighbor,0):
                        
                        self._top_cell_deletion_sender(neighbor,[ts])
                        
                        bundleRelocation = True
                
                # update stats
                if bundleRelocation:
                    self._incrementMoteStats('topRelocatedBundles')
        
    def _top_cell_reservation_request(self,neighbor,numCells):
        ''' tries to reserve numCells TX cells to a neighbor. '''
        
        with self.dataLock:
            cells=neighbor.top_cell_reservation_response(self,numCells)
            cellList=[]
            for ts, ch in cells.iteritems():
                # log
                self._log(
                    self.INFO,
                    '[6top] add TX cell ts={0},ch={1} from {2} to {3}',
                    (ts,ch,self.id,neighbor.id),
                )
                cellList += [(ts,ch,self.DIR_TX)]
            self._tsch_addCells(neighbor,cellList)
            
            # update counters
            if neighbor not in self.numCellsToNeighbors:
                self.numCellsToNeighbors[neighbor]    = 0
            self.numCellsToNeighbors[neighbor]  += len(cells)
            
            if len(cells)!=numCells:
                # log
                self._log(
                    self.ERROR,
                    '[6top] scheduled {0} cells out of {1} required between motes {2} and {3}',
                    (len(cells),numCells,self.id,neighbor.id),
                )
                #print '[6top] scheduled {0} cells out of {1} required between motes {2} and {3}'.format(len(cells),numCells,self.id,neighbor.id)
            
    def top_cell_reservation_response(self,neighbor,numCells):
        ''' tries to reserve numCells RX cells to a neighbor. '''
        
        with self.dataLock:
            # timeslot = 0 is reserved for a shared cell (not implemented yet) and thus not used as a dedicated cell
            availableTimeslots=list(set(range(self.settings.slotframeLength))-set(neighbor.schedule.keys())-set(self.schedule.keys()))
            random.shuffle(availableTimeslots)
            cells=dict([(ts,random.randint(0,self.settings.numChans-1)) for ts in availableTimeslots[:numCells]])
            cellList=[]
            for ts, ch in cells.iteritems():
                # log
                self._log(
                    self.INFO,
                    '[6top] add RX cell ts={0},ch={1} from {2} to {3}',
                    (ts,ch,self.id,neighbor.id),
                )
                cellList += [(ts,ch,self.DIR_RX)]
            self._tsch_addCells(neighbor,cellList)
            return cells
    
    def _top_cell_deletion_sender(self,neighbor,tsList):
        with self.dataLock:
            # log
            self._log(
                self.INFO,
                "[6top] remove timeslots={0} with {1}",
                (tsList,neighbor.id),
            )
            self._tsch_removeCells(
                neighbor     = neighbor,
                tsList       = tsList,
            )
            neighbor.top_cell_deletion_receiver(self,tsList)
            self.numCellsToNeighbors[neighbor] -= len(tsList)
            assert self.numCellsToNeighbors[neighbor]>=0
    
    def top_cell_deletion_receiver(self,neighbor,tsList):
        with self.dataLock:
            self._tsch_removeCells(
                neighbor     = neighbor,
                tsList       = tsList,
            )
    
    def _top_removeCells(self,neighbor,numCellsToRemove):
        '''
        Finds cells to neighbor, and remove it.
        '''
        
        # get cells to the neighbors
        scheduleList = []
        
        ''' ########## basic worst cell removing ##########
        for ts, cell in self.schedule.iteritems():
            if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX:
                if cell['numTx']==0:
                    cellPDR=1.0
                else:
                    cellPDR=float(cell['numTxAck'])/cell['numTx']
                scheduleList+=[(ts,cell['numTxAck'],cell['numTx'],cellPDR)]
        
        # introduce randomness in the cell list order
        random.shuffle(scheduleList)
        
        if not self.settings.noRemoveWorstCell:
            
            # triggered only when worst cell selection is due (cell list is sorted according to worst cell selection)
            scheduleListByPDR={}
            for tscell in scheduleList:
                if not scheduleListByPDR.has_key(tscell[3]):
                    scheduleListByPDR[tscell[3]]=[]
                scheduleListByPDR[tscell[3]]+=[tscell]
            rssi            = self.getRSSI(neighbor)
            theoPDR         = Topology.Topology.rssiToPdr(rssi)
            scheduleList=[]
            for pdr in sorted(scheduleListByPDR.keys()):
                if pdr<theoPDR:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2], reverse=True)
                else:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2])
        
        '''

        #''' ########## worst cell removing initialized by theoritical pdr ##########
        for ts, cell in self.schedule.iteritems():
            if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX:
                cellPDR=(float(cell['numTxAck'])+(self.getPDR(neighbor)*self.NUM_SUFFICIENT_TX))/(cell['numTx']+self.NUM_SUFFICIENT_TX)
                scheduleList+=[(ts,cell['numTxAck'],cell['numTx'],cellPDR)]
        
        # introduce randomness in the cell list order
        random.shuffle(scheduleList)
        
        if not self.settings.noRemoveWorstCell:
            
            # triggered only when worst cell selection is due (cell list is sorted according to worst cell selection)
            scheduleListByPDR={}
            for tscell in scheduleList:
                if not scheduleListByPDR.has_key(tscell[3]):
                    scheduleListByPDR[tscell[3]]=[]
                scheduleListByPDR[tscell[3]]+=[tscell]
            rssi            = self.getRSSI(neighbor)
            theoPDR         = Topology.Topology.rssiToPdr(rssi)
            scheduleList=[]
            for pdr in sorted(scheduleListByPDR.keys()):
                if pdr<theoPDR:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2], reverse=True)
                else:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2])        
        #'''

        ''' ########## remove only cells whose reliability is low ##########
        nonRemovingCells = [] # cells that are not removed
        rssi            = self.getRSSI(neighbor)
        theoPDR         = Topology.Topology.rssiToPdr(rssi)

        for ts, cell in self.schedule.iteritems():
            if cell['neighbor']==neighbor and cell['dir']==self.DIR_TX:
                if cell['numTx']<self.NUM_SUFFICIENT_TX:
                    cellPDR=1.0
                    nonRemovingCells+=[(ts,cell['numTxAck'],cell['numTx'],cellPDR)]
                else:
                    cellPDR=float(cell['numTxAck'])/cell['numTx']
                    if cellPDR > theoPDR:
                        nonRemovingCells+=[(ts,cell['numTxAck'],cell['numTx'],cellPDR)]
                    else:
                        scheduleList+=[(ts,cell['numTxAck'],cell['numTx'],cellPDR)]
        
        # introduce randomness in the cell list order
        random.shuffle(scheduleList)
        
        if not self.settings.noRemoveWorstCell:
            
            # triggered only when worst cell selection is due (cell list is sorted according to worst cell selection)
            scheduleListByPDR={}
            for tscell in scheduleList:
                if not scheduleListByPDR.has_key(tscell[3]):
                    scheduleListByPDR[tscell[3]]=[]
                scheduleListByPDR[tscell[3]]+=[tscell]
            scheduleList=[]
            for pdr in sorted(scheduleListByPDR.keys()):
                if pdr<theoPDR:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2], reverse=True)
                else:
                    scheduleList+=sorted(scheduleListByPDR[pdr], key=lambda x: x[2])        
        '''
        
        # remove a given number of cells from the list of available cells (picks the first numCellToRemove)
        tsList=[]
        for tscell in scheduleList[:numCellsToRemove]:
            
            # log
            self._log(
                self.INFO,
                "[otf] remove cell ts={0} to {1} (pdr={2:.3f})",
                (tscell[0],neighbor.id,tscell[3]),
            )
            tsList += [tscell[0]]
        # remove cells
        self._top_cell_deletion_sender(neighbor,tsList)
    
    def _top_isUnusedSlot(self,ts):
        with self.dataLock:
            return not (ts in self.schedule)
    
    #===== tsch
    
    def _tsch_enqueue(self,packet):
        
        if not self.preferredParent:
            # I don't have a route
            
            # increment mote state
            self._incrementMoteStats('droppedNoRoute')
            
            return False
        
        elif not self.getTxCells():
            # I don't have any transmit cells
            
            # increment mote state
            self._incrementMoteStats('droppedNoTxCells')

            return False
        
        elif len(self.txQueue)==self.TSCH_QUEUE_SIZE:
            # my TX queue is full
            
            # update mote stats
            self._incrementMoteStats('droppedQueueFull')

            return False
        
        else:
            # all is good
            
            # enqueue packet
            self.txQueue     += [packet]

            return True
    
    def _tsch_schedule_activeCell(self):
        
        asn        = self.engine.getAsn()
        tsCurrent  = asn%self.settings.slotframeLength
        
        # find closest active slot in schedule
        with self.dataLock:
            
            if not self.schedule:
                #self._log(self.DEBUG,"[tsch] empty schedule")
                self.engine.removeEvent(uniqueTag=(self.id,'activeCell'))
                return
            
            tsDiffMin             = None
            for (ts,cell) in self.schedule.items():
                if   ts==tsCurrent:
                    tsDiff        = self.settings.slotframeLength
                elif ts>tsCurrent:
                    tsDiff        = ts-tsCurrent
                elif ts<tsCurrent:
                    tsDiff        = (ts+self.settings.slotframeLength)-tsCurrent
                else:
                    raise SystemError()
                
                if (not tsDiffMin) or (tsDiffMin>tsDiff):
                    tsDiffMin     = tsDiff
        
        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn         = asn+tsDiffMin,
            cb          = self._tsch_action_activeCell,
            uniqueTag   = (self.id,'activeCell'),
            priority    = 0,
        )
    
    def _tsch_action_activeCell(self):
        ''' active slot starts. Determine what todo, either RX or TX, use the propagation model to introduce
            interference and Rx packet drops.
        '''
        
        #self._log(self.DEBUG,"[tsch] _tsch_action_activeCell")
        
        asn = self.engine.getAsn()
        ts  = asn%self.settings.slotframeLength
        
        with self.dataLock:
            
            # make sure this is an active slot   
            assert ts in self.schedule
            # make sure we're not in the middle of a TX/RX operation
            assert not self.waitingFor
            
            cell = self.schedule[ts]
            
            if  cell['dir']==self.DIR_RX:
                
                # start listening
                self.propagation.startRx(
                    mote          = self,
                    channel       = cell['ch'],
                )
                
                # indicate that we're waiting for the RX operation to finish
                self.waitingFor   = self.DIR_RX
            
            elif cell['dir']==self.DIR_TX:
                
                # check whether packet to send
                self.pktToSend = None
                if self.txQueue:
                    self.pktToSend = self.txQueue[0]
                
                # send packet
                if self.pktToSend:
                    
                    cell['numTx'] += 1
                    
                    self.propagation.startTx(
                        channel   = cell['ch'],
                        type      = self.pktToSend['type'],
                        smac      = self,
                        dmac      = cell['neighbor'],
                        payload   = self.pktToSend['payload'],
                    )
                    
                    # indicate that we're waiting for the TX operation to finish
                    self.waitingFor   = self.DIR_TX
                    
                    # log charge usage
                    self._logChargeConsumed(self.CHARGE_TxDataRxAck_uC)
            
            # schedule next active cell
            self._tsch_schedule_activeCell()
    
    def _tsch_addCells(self,neighbor,cellList):
        ''' adds cells to the schedule '''
        
        with self.dataLock:
            for cell in cellList:
                assert cell[0] not in self.schedule.keys()
                self.schedule[cell[0]] = {
                    'ch':                 cell[1],
                    'dir':                cell[2],
                    'neighbor':           neighbor,
                    'numTx':              0,
                    'numTxAck':           0,
                    'numRx':              0,
                }
                # log
                self._log(
                    self.INFO,
                    "[tsch] add cell ts={0} ch={1} dir={2} with {3}",
                    (cell[0],cell[1],cell[2],neighbor.id),
                )
            self._tsch_schedule_activeCell()
    
    def _tsch_removeCells(self,neighbor,tsList):
        ''' removes a cell from the schedule '''
        
        with self.dataLock:
            # log
            self._log(
                self.INFO,
                "[tsch] remove timeslots={0} with {1}",
                (tsList,neighbor.id),
            )
            for ts in tsList:
                assert ts in self.schedule.keys()
                assert self.schedule[ts]['neighbor']==neighbor
                self.schedule.pop(ts)
            self._tsch_schedule_activeCell()
            
    #===== radio
    
    def txDone(self,isACKed,isNACKed):
        '''end of tx slot'''
        
        asn   = self.engine.getAsn()
        ts    = asn%self.settings.slotframeLength
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.schedule[ts]['dir']==self.DIR_TX
            assert self.waitingFor==self.DIR_TX
            
            if isACKed:
                
                # update schedule stats
                self.schedule[ts]['numTxAck'] += 1
                
                # update queue stats
                self._logQueueDelayStat(asn-self.pktToSend['asn'])
                
                # time correction
                if self.schedule[ts]['neighbor'] == self.preferredParent:
                    self.timeCorrectedSlot = asn

                # remove packet from queue
                self.txQueue.remove(self.pktToSend)
                
            elif isNACKed:
                
                # update schedule stats as if it is successfully tranmitted
                self.schedule[ts]['numTxAck'] += 1
                                
                # time correction
                if self.schedule[ts]['neighbor'] == self.preferredParent:
                    self.timeCorrectedSlot = asn

                # decrement 'retriesLeft' counter associated with that packet
                i = self.txQueue.index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1
                
                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:
                    
                    if  len(self.txQueue) == self.TSCH_QUEUE_SIZE:

                        # update mote stats
                        self._incrementMoteStats('droppedMacRetries')
                        
                        # remove packet from queue
                        self.txQueue.remove(self.pktToSend)
            
            else:
                
                # decrement 'retriesLeft' counter associated with that packet
                i = self.txQueue.index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1
                
                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:
                    
                    if  len(self.txQueue) == self.TSCH_QUEUE_SIZE:

                        # update mote stats
                        self._incrementMoteStats('droppedMacRetries')
                        
                        # remove packet from queue
                        self.txQueue.remove(self.pktToSend)
            
            self.waitingFor = None
    
    def rxDone(self,type=None,smac=None,dmac=None,payload=None):
        '''end of rx slot'''
        
        asn   = self.engine.getAsn()
        ts    = asn%self.settings.slotframeLength
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.schedule[ts]['dir']==self.DIR_RX
            assert self.waitingFor==self.DIR_RX
            
            if smac:
                # I received a packet
                
                # log charge usage
                self._logChargeConsumed(self.CHARGE_RxDataTxAck_uC)
                
                # update schedule stats
                self.schedule[ts]['numRx'] += 1
                
                if self.dagRoot:
                    # receiving packet (at DAG root)
                    
                    # update mote stats
                    self._incrementMoteStats('appReachesDagroot')
                    
                    # calculate end-to-end latency
                    self._logLatencyStat(asn-payload[1])
                    
                    # log the number of hops
                    self._logHopsStat(payload[2])
                    
                    (isACKed, isNACKed) = (True, False)
                
                else:
                    # relaying packet
                    
                    # count incoming traffic for each node
                    self._otf_incrementIncomingTraffic(smac)
                    
                    # update the number of hops
                    newPayload     = copy.deepcopy(payload)
                    newPayload[2] += 1
                    
                    # create packet
                    relayPacket = {
                        'asn':         asn,
                        'type':        type,
                        'payload':     newPayload,
                        'retriesLeft': self.TSCH_MAXTXRETRIES
                    }
                    
                    
                    # enqueue packet in TSCH queue
                    isEnqueued = self._tsch_enqueue(relayPacket)
                    
                    if isEnqueued:

                        # update mote stats
                        self._incrementMoteStats('appRelayed')

                        (isACKed, isNACKed) = (True, False)
                    
                    else:
                        (isACKed, isNACKed) = (False, True)
                                    
            else:
                # this was an idle listen
                
                # log charge usage
                self._logChargeConsumed(self.CHARGE_Idle_uC)
                
                (isACKed, isNACKed) = (False, False)
            
            self.waitingFor = None

            return isACKed, isNACKed

    def calcTime(self):
        ''' calculate time compared to base time of Dag root '''
        
        asn   = self.engine.getAsn()
        
        time   = 0.0
        child  = self
        parent = self.preferredParent
        
        while(True):
            duration  = (asn-child.timeCorrectedSlot) * self.settings.slotDuration # in sec
            driftDiff = child.drift - parent.drift # in ppm
            time += driftDiff * duration # in us
            if parent.dagRoot:
                break
            else:
                child  = parent
                parent = child.preferredParent
        
        return time
        
    
    #===== wireless
    
    def _estimateETX(self,neighbor):
        
        with self.dataLock:

            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr                   = self.getPDR(neighbor)
            numTx                 = self.NUM_SUFFICIENT_TX
            numTxAck              = math.floor(pdr*numTx)
            
            for (_,cell) in self.schedule.items():
                if (cell['neighbor'] == neighbor) and (cell['dir'] == self.DIR_TX):
                    numTx        += cell['numTx']
                    numTxAck     += cell['numTxAck']
            
            # abort if about to divide by 0
            if not numTxAck:
                return
            
            # calculate ETX
            etx = float(numTx)/float(numTxAck)
            
            return etx
    
    def setPDR(self,neighbor,pdr):
        ''' sets the pdr to that neighbor'''
        with self.dataLock:
            self.PDR[neighbor] = pdr
    
    def getPDR(self,neighbor):
        ''' returns the pdr to that neighbor'''
        with self.dataLock:
            return self.PDR[neighbor]
    
    def _myNeigbors(self):
        return [n for n in self.PDR.keys() if self.PDR[n]>0]
    
    def setRSSI(self,neighbor,rssi):
        ''' sets the RSSI to that neighbor'''
        with self.dataLock:
            self.RSSI[neighbor.id] = rssi

    def getRSSI(self,neighbor):
        ''' returns the RSSI to that neighbor'''
        with self.dataLock:
            return self.RSSI[neighbor.id]
    
    #===== location
    
    def setLocation(self,x,y):
        with self.dataLock:
            self.x = x
            self.y = y
    
    def getLocation(self):
        with self.dataLock:
            return (self.x,self.y)
    
    #==== battery
    
    def boot(self):
        if not self.dagRoot:
            self._app_schedule_sendData(init=True)
            if self.settings.numPacketsBurst != None and self.settings.burstTime != None:
                self._app_schedule_enqueueData()
        self._rpl_schedule_sendDIO(init=True)
        self._otf_resetInTraffic()
        self._otf_schedule_housekeeping()
        self._top_schedule_housekeeping()
        self._tsch_schedule_activeCell()
    
    def _logChargeConsumed(self,charge):
        with self.dataLock:
            self.chargeConsumed  += charge
    
    #======================== private =========================================
    
    #===== getters
    
    def getTxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_TX]
    
    def getRxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_RX]
    
    #===== stats
    
    # mote state
    
    def _resetMoteStats(self):
        with self.dataLock:
            self.motestats = {
                # app
                'appGenerated':            0,   # number of packets app layer generated
                'appRelayed':              0,   # number of packets relayed
                'appReachesDagroot':       0,   # number of packets received at the DAGroot
                'droppedAppFailedEnqueue': 0,# dropped packets because app failed enqueue them
                # queue
                'droppedQueueFull':        0,   # dropped packets because queue is full
                # rpl
                'rplTxDIO':                0,   # number of TX'ed DIOs
                'rplRxDIO':                0,   # number of RX'ed DIOs
                'rplChurnPrefParent':      0,   # number of time the mote changes preferred parent
                'rplChurnRank':            0,   # number of time the mote changes rank
                'rplChurnParentSet':       0,   # number of time the mote changes parent set
                'droppedNoRoute':          0,   # packets dropped because no route (no preferred parent)
                # otf
                'droppedNoTxCells':        0,   # packets dropped because no TX cells
                'otfAdd':                  0,   # OTF adds some cells
                'otfRemove':               0,   # OTF removes some cells
                # 6top
                'topRelocatedCells':       0,   # number of time 6top relocates a single cell
                'topRelocatedBundles':     0,   # number of time 6top relocates a bundle
                # tsch
                'droppedMacRetries':       0,   # packets dropped because more than TSCH_MAXTXRETRIES MAC retries
            }
    
    def _incrementMoteStats(self,name):
        with self.dataLock:
            self.motestats[name] += 1
    
    def getMoteStats(self):
        
        # gather statistics
        with self.dataLock:
            returnVal = copy.deepcopy(self.motestats)
            returnVal['numTxCells']         = len(self.getTxCells())
            returnVal['numRxCells']         = len(self.getRxCells())
            returnVal['aveQueueDelay']      = self.getAveQueueDelay()
            returnVal['aveLatency']         = self.getAveLatency()
            returnVal['aveHops']            = self.getAveHops()            
            returnVal['txQueueFill']        = len(self.txQueue)
            returnVal['chargeConsumed']     = self.chargeConsumed
            returnVal['numTx']              = sum([cell['numTx'] for (_,cell) in self.schedule.items()])
        
        # reset the statistics
        self._resetMoteStats()
        self._resetQueueStats()
        self._resetLatencyStats()
        self._resetHopsStats()
                
        return returnVal
    
    # cell stats
    
    def getCellStats(self,ts_p,ch_p):
        ''' retrieves cell stats '''
        returnVal = None
        with self.dataLock:
            for (ts,cell) in self.schedule.items():
                if ts==ts_p and cell['ch']==ch_p:
                    returnVal = {
                        'dir':            cell['dir'],
                        'neighbor':       cell['neighbor'].id,
                        'numTx':          cell['numTx'],
                        'numTxAck':       cell['numTxAck'],
                        'numRx':          cell['numRx'],
                    }
                    break
        return returnVal
    
    # queue stats
    
    def getAveQueueDelay(self):
        d = self.queuestats['delay']
        return float(sum(d))/len(d) if len(d)>0 else 0
    
    def _resetQueueStats(self):
        with self.dataLock:
            self.queuestats = {
                'delay':               [],
            }
    
    def _logQueueDelayStat(self,delay):
        with self.dataLock:
            self.queuestats['delay'] += [delay]
    
    # latency stats
    
    def getAveLatency(self):
        with self.dataLock:
            d = self.packetLatencies
            return float(sum(d))/float(len(d)) if len(d)>0 else 0
    
    def _resetLatencyStats(self):
        with self.dataLock:
            self.packetLatencies = []
    
    def _logLatencyStat(self,latency):
        with self.dataLock:
            self.packetLatencies += [latency]

    # hops stats
    
    def getAveHops(self):
        with self.dataLock:
            d = self.packetHops
            return float(sum(d))/float(len(d)) if len(d)>0 else 0
    
    def _resetHopsStats(self):
        with self.dataLock:
            self.packetHops = []
    
    def _logHopsStat(self,hops):
        with self.dataLock:
            self.packetHops += [hops]
    
    #===== log
    
    def _log(self,severity,template,params=()):
        
        if   severity==self.DEBUG:
            if not log.isEnabledFor(logging.DEBUG):
                return
            logfunc = log.debug
        elif severity==self.INFO:
            if not log.isEnabledFor(logging.INFO):
                return
            logfunc = log.info
        elif severity==self.WARNING:
            if not log.isEnabledFor(logging.WARNING):
                return
            logfunc = log.warning
        elif severity==self.ERROR:
            if not log.isEnabledFor(logging.ERROR):
                return
            logfunc = log.error
        else:
            raise NotImplementedError()
        
        output  = []
        output += ['[ASN={0:>6} id={1:>4}] '.format(self.engine.getAsn(),self.id)]
        output += [template.format(*params)]
        output  = ''.join(output)
        logfunc(output)

