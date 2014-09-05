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
    RPL_MAX_RANK_INCREASE              = 256*RPL_MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
    RPL_PARENT_SET_SIZE                = 3
    #=== otf
    OTF_HOUSEKEEPING_PERIOD_S          = 1
    OTF_TRAFFIC_SMOOTHING              = 0.5
    #=== 6top
    # ratio 1/4 -- changing this threshold the detection of a bad cell can be
    # tuned, if as higher the slower to detect a wrong cell but the more prone
    # to avoid churn as lower the faster but with some chances to introduces
    # churn due to unstable medium
    TOP_PDR_THRESHOLD                  = 4.0
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
        self.rplRxDIO                  = {}      # indexed by neighbor, contains int
        self.neighborRank              = {}      # indexed by neighbor
        self.neighborDagRank           = {}      # indexed by neighbor
        self.trafficPortionPerParent   = {}      # indexed by parent, portion of outgoing traffic
        # otf
        self.asnOTFevent               = None
        self.timeBetweenOTFevents      = []
        self.inTraffic                 = {}      # indexed by neighbor
        self.inTrafficMovingAve        = {}      # indexed by neighbor
        # 6top
        self.numCellsToNeighbors       = {}      # indexed by neighbor, contains int
        # tsch
        self.txQueue                   = []
        self.pktToSend                 = None
        self.schedule                  = {}      # indexed by ts, contains cell
        self.waitingFor                = None
        self.timeCorrectedSlot        = None
        # radio
        self.txPower                   = 0       # dBm
        self.antennaGain               = 0       # dBi
        self.minRssi                   = self.settings.sensitivity - self.settings.waterfallRisingBand # dBm
        self.noisepower                = -105    # dBm
        self.drift                     = random.uniform(-self.RADIO_MAXDRIFT, self.RADIO_MAXDRIFT)
        # wireless
        self.RSSI                      = {}      # indexed by neighbor
        self.PDR                       = {}      # indexed by neighbor
        # location
        # battery
        self.chargeConsumed            = 0
        
        # stats
        self._resetMoteStats()
        self._resetQueueStats()
        self._resetLatencyStats()
    
    #======================== stack ===========================================
    
    #===== role
    
    def role_setDagRoot(self):
        self.dagRoot              = True
        self.rank                 = 0
        self.dagRank              = 0
        self.packetLatencies      = [] # in slots
    
    #===== application
    
    def _app_schedule_sendData(self):
        ''' create an event that is inserted into the simulator engine to send the data according to the traffic'''
        
        # compute random
        delay           = self.settings.pkPeriod*(1+random.uniform(-self.settings.pkPeriodVar,self.settings.pkPeriodVar))
        assert delay>0
        
        # schedule
        self.engine.scheduleIn(
            delay       = delay,
            cb          = self._app_action_sendData,
            uniqueTag   = (self.id, 'sendData')
        )
    
    def _app_schedule_enqueueData(self):
        ''' create an event that is inserted into the simulator engine to send a data burst'''
        
        # schedule numPacketsBurst packets at burstTime
        for i in xrange(self.settings.numPacketsBurst):
            self.engine.scheduleIn(
                delay       = self.settings.burstTime,
                cb          = self._app_action_enqueueData,
                uniqueTag   = (self.id, 'enqueueData')
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
                'payload':        [self.id,self.engine.getAsn()], # the payload is used for latency calculation
                'retriesLeft':    self.TSCH_MAXTXRETRIES
            }
            
            # update mote stats
            self._incrementMoteStats('appGenerated')
            
            # enqueue packet in TSCH queue
            self._tsch_enqueue(newPacket)
    
    #===== rpl
    
    def _rpl_schedule_sendDIO(self):
        
        with self.dataLock:
            
            asn    = self.engine.getAsn()
            ts     = asn%self.settings.slotframeLength
            
            # schedule at start of next cycle
            self.engine.scheduleAtAsn(
                asn         = asn-ts+self.settings.slotframeLength,
                cb          = self._rpl_action_sendDIO,
                uniqueTag   = (self.id,'DIO'),
            )
    
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
            
            # no RPL housekeeping needed on DAGroot
            if self.dagRoot:
                return
            
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
                if rankIncrease==None:
                    # could not calculate, don't consider this neighbor
                    continue
                
                # don't consider this neighbor it it's too costly to communicate with
                if rankIncrease>self.RPL_MAX_RANK_INCREASE:
                    continue
                
                # record this potential rank
                potentialRanks[neighbor] = neighborRank+rankIncrease
            
            # sort potential ranks
            sorted_potentialRanks = sorted(potentialRanks.iteritems(), key=lambda x:x[1])
            
            # pick my preferred parent and resulting rank
            if sorted_potentialRanks:
                (newPreferredParent,newrank) = sorted_potentialRanks[0]
                
                # update mote stats
                if self.preferredParent and newPreferredParent!=self.preferredParent:
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
            
            #===
            # refresh the following parameters:
            # - self.trafficPortionPerParent
            
            etxs        = dict([(p, 1.0/(self.neighborRank[p]+self._rpl_calcRankIncrease(p))) for p in self.parentSet])
            sumEtxs     = float(sum(etxs.values()))
            self.trafficPortionPerParent = dict([(p, etxs[p]/sumEtxs) for p in self.parentSet])
    
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
            delay       = self.OTF_HOUSEKEEPING_PERIOD_S*(0.9+0.2*random.random()),
            cb          = self._otf_housekeeping,
            uniqueTag   = (self.id,'housekeeping')
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
                genTraffic  += self.inTrafficMovingAve[neighbor]/self.OTF_HOUSEKEEPING_PERIOD_S   # relayed
            # convert to pkts/cycle
            genTraffic      *= self.settings.slotframeLength*self.settings.slotDuration
            
            # split genTraffic across parents, trigger 6top to add/delete cells accordingly
            for (parent,portion) in self.trafficPortionPerParent.items():
                
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
                    for _ in xrange(numCellsToAdd):
                        self._6top_addCell(parent)
                    
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
                    for _ in xrange(numCellsToRemove):
                        self._6top_removeCell(parent)
                    
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
            
            
            # remove TX cells to neighbor who are not in parent set
            for neighbor in self.numCellsToNeighbors.keys():
                if neighbor not in self.parentSet:
                
                    # log
                    self._log(
                        self.INFO,
                        "[otf] removing cell to {0}, since not in parentSet {1}",
                        (neighbor.id,[p.id for p in self.parentSet]),

                    numCellsToRemove = self.numCellsToNeighbors[neighbor]
                    for _ in xrange(numCellsToRemove):
                        self._6top_removeCell(neighbor)

            # trigger 6top housekeeping
            self._6top_housekeeping()
            
            # schedule my and my neighbor's next active cell
            self._tsch_schedule_activeCell()
            for neighbor in self._myNeigbors():
                neighbor._tsch_schedule_activeCell()
            
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
    
    def _6top_housekeeping(self):
        '''
        For each neighbor I have TX cells to, relocate cells if needed.
        '''
        
        # collect all neighbors I have TX cells to
        txNeighbors = [cell['neighbor'] for (ts,cell) in self.schedule.items() if cell['dir']==self.DIR_TX]
        
        # remove duplicates
        txNeighbors = list(set(txNeighbors))
        
        # do some housekeeping for each neighbor
        for neighbor in txNeighbors:
            self._6top_housekeeping_per_neighbor(neighbor)
        
    def _6top_housekeeping_per_neighbor(self,neighbor):
        '''
        For a particular neighbor, decide to relocate cells if needed.
        '''
        
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
        # It it's PDR is TOP_PDR_THRESHOLD lower than the average of the bundle
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
            if worst_pdr<(ave_pdr/self.TOP_PDR_THRESHOLD):
                
                # log
                self._log(
                    self.INFO,
                    "[6top] relocating cell ts {0} to {1} (pdr={2:.3f} significantly worse than others {3})",
                    (worst_ts,neighbor,worst_pdr,cell_pdr),
                )
                
                # relocate: add new, remove old
                self._6top_addCell(neighbor)
                self._6top_removeSpecifiedCell(worst_ts,neighbor)
                
                # update stats
                self._incrementMoteStats('6topRelocatedCells')
                
                # remember I relocated a cell for that bundle
                relocation = True
        
        #===== step 3. relocate the complete bundle
        # this step only runs if the previous hasn't, and we were able to
        # calculate a bundle PDR.
        # this step verifies that the average PDR for the complete bundle is
        # expected, given the RSSI to that neighbor. If it's lower, this step
        # will move all cells in the bundle.
        
        if (not relocation) and bundlePdr!=None:
            
            # calculate the theoretical PDR to that neighbor, using the measured RSSI
            rssi            = self.getRSSI(neighbor)
            theoPDR         = Topology.Topology.rssiToPdr(rssi)
            
            # relocate complete bundle if measured RSSI is significantly worse than theoretical
            if bundlePdr<(theoPDR/self.TOP_PDR_THRESHOLD):
                for (ts,_) in cell_pdr:
                    
                    # log
                    self._log(
                        self.INFO,
                        "[6top] relocating cell ts {0} to {1} (bundle pdr {2} << theoretical pdr {3})",
                        (ts,neighbor,bundlePdr,theoPDR),
                    )
                    
                    # relocate: add new, remove old
                    self._6top_addCell(neighbor)
                    self._6top_removeSpecifiedCell(ts,neighbor)
                
                # update stats
                self._incrementMoteStats('6topRelocatedBundles')
    
    def _6top_addCell(self,neighbor):
        ''' tries to allocate a cell to a neighbor. It retries until it finds one available slot. '''
        
        with self.dataLock:
            for trial in range(0,10000):
                ts      = random.randint(0,self.settings.slotframeLength-1)
                ch      = random.randint(0,self.settings.numChans-1)
                if  (
                        self._6top_isUnusedSlot(ts) and
                        neighbor._6top_isUnusedSlot(ts)
                    ):
                    
                    # log
                    self._log(
                        self.INFO,
                        '[6top] add cell ts={0},ch={1} to {2}',
                        (ts,ch,neighbor.id),
                    )
                    
                    # have tsch add these cells
                    self._tsch_addCell(
                        ts             = ts,
                        ch             = ch,
                        dir            = self.DIR_TX,
                        neighbor       = neighbor,
                    )
                    neighbor._tsch_addCell(
                        ts             = ts,
                        ch             = ch,
                        dir            = self.DIR_RX,
                        neighbor       = self,
                    )
                    
                    # update counters
                    if neighbor not in self.numCellsToNeighbors:
                        self.numCellsToNeighbors[neighbor]    = 0
                    self.numCellsToNeighbors[neighbor]  += 1
                    
                    return True
            
            # log
            self._log(
                self.ERROR,
                '[6top] tried {0} times but unable to find an empty time slot for nodes {1} and {2}',
                (trial+1,self.id,neighbor.id),
            )
    
    def _6top_removeCell(self,neighbor):
        '''
        Removes a cell to neighbor.
        '''

        # case that housekeeping is ON
        self._6top_removeWorstCell(neighbor)        
        
        # case that housekeeping is OFF
        # self._6top_removeRandomCell(neighbor)
        

    def _6top_removeWorstCell(self,neighbor):
        '''
        Finds cells with worst PDR to neighbor, and remove it.
        '''
        
        worst_ts   = None
        worst_pdr  = None
        
        # find the cell with the worth PDR to that neighbor
        for (ts,cell) in self.schedule.items():
            if cell['neighbor']==neighbor:
                
                # don't consider cells we've never TX'ed on
                if cell['numTx'] == 0: # we don't select unused cells
                    continue
                
                pdr = float(cell['numTxAck']) / float(cell['numTx'])
                
                if worst_ts==None or pdr<worst_pdr:
                    worst_ts      = ts
                    worst_pdr     = pdr
        
        # remove that cell
        if worst_ts!=None:
            
            # log
            self._log(
                self.INFO,
                "[otf] remove cell ts={0} to {1} (pdr={2:.3f})",
                (worst_ts,neighbor.id,worst_pdr),
            )
            
            # remove cell
            self._6top_removeSpecifiedCell(worst_ts,neighbor)
        
        else:
            # log
            self._log(
                self.WARNING,
                "[otf] could not find a cell to {0} to remove",
                (neighbor.id,),
            )

    def _6top_removeRandomCell(self,neighbor):
        '''
        Randomly finds a cell to neighbor, and remove it.
        '''
        
        tss = []
        
        # find a cell to that neighbor
        for (ts,cell) in self.schedule.items():
            if cell['neighbor']==neighbor:
                
                tss += [ts]
        
        # remove that cell
        if tss!=[]:
            ts = random.choice(tss)
            # remove cell
            self._6top_removeSpecifiedCell(ts,neighbor)

    def _6top_removeSpecifiedCell(self,ts,neighbor):
        
        # log
        self._log(
            self.INFO,
            "[6top] remove ts={0} with {1}",
            (ts,neighbor.id),
        )
        
        with self.dataLock:
            self._tsch_removeCell(
                ts           = ts,
                neighbor     = neighbor,
            )
            neighbor._tsch_removeCell(
                ts           = ts,
                neighbor     = self,
            )
            self.numCellsToNeighbors[neighbor] -= 1

    
    def _6top_isUnusedSlot(self,ts):
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
            
            if not self.waitingFor:
                # schedule next active cell
                self._tsch_schedule_activeCell()
    
    def _tsch_addCell(self,ts,ch,dir,neighbor):
        ''' adds a cell to the schedule '''
        
        # log
        self._log(
            self.INFO,
            "[tsch] add cell ts={0} ch={1} dir={2} with {3}",
            (ts,ch,dir,neighbor.id),
        )
        
        with self.dataLock:
            assert ts not in self.schedule.keys()
            self.schedule[ts] = {
                'ch':                 ch,
                'dir':                dir,
                'neighbor':           neighbor,
                'numTx':              0,
                'numTxAck':           0,
                'numRx':              0,
            }
    
    def _tsch_removeCell(self,ts,neighbor):
        ''' removes a cell from the schedule '''
        
        # log
        self._log(
            self.INFO,
            "[tsch] remove ts={0} with {1}",
            (ts,neighbor.id),
        )
        
        with self.dataLock:
            assert ts in self.schedule.keys()
            assert self.schedule[ts]['neighbor']==neighbor
            del self.schedule[ts]
    
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
                self.txQueue[i]['retriesLeft'] -= 1
                
                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:
                    
                    # update mote stats
                    self._incrementMoteStats('droppedMacRetries')
                    
                    # remove packet from queue
                    self.txQueue.remove(self.pktToSend)
            
            else:
                
                # decrement 'retriesLeft' counter associated with that packet
                i = self.txQueue.index(self.pktToSend)
                self.txQueue[i]['retriesLeft'] -= 1
                
                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:
                    
                    # update mote stats
                    self._incrementMoteStats('droppedMacRetries')
                    
                    # remove packet from queue
                    self.txQueue.remove(self.pktToSend)
            
            self.waitingFor = None
            
            # schedule next active cell
            self._tsch_schedule_activeCell()
    
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
                    
                    (isACKed, isNACKed) = (True, False)
                
                else:
                    # relaying packet
                    
                    # count incoming traffic for each node
                    self._otf_incrementIncomingTraffic(smac)
                    
                    # create packet
                    relayPacket = {
                        'asn':         asn,
                        'type':        type,
                        'payload':     payload,
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
            
            # schedule next active cell
            self._tsch_schedule_activeCell()

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
            self._app_schedule_sendData()
            if self.settings.numPacketsBurst != None and self.settings.burstTime != None:
                self._app_schedule_enqueueData()
        self._rpl_schedule_sendDIO()
        self._otf_resetInTraffic()
        self._otf_schedule_housekeeping()
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
                'appGenerated':        0,   # number of packets app layer generated
                'appRelayed':          0,   # number of packets relayed
                'appReachesDagroot':   0,   # number of packets received at the DAGroot
                # queue
                'droppedQueueFull':    0,   # dropped packets because queue is full
                # rpl
                'rplTxDIO':            0,   # number of TX'ed DIOs
                'rplRxDIO':            0,   # number of RX'ed DIOs
                'rplChurnPrefParent':  0,   # number of time the mote changes preferred parent
                'rplChurnRank':        0,   # number of time the mote changes rank
                'droppedNoRoute':      0,   # packets dropped because no route (no preferred parent)
                # otf
                'droppedNoTxCells':    0,   # packets dropped because no TX cells
                'otfAdd':              0,   # OTF adds some cells
                'otfRemove':           0,   # OTF removes some cells
                # 6top
                '6topRelocatedCells':  0,   # number of time 6top relocates a single cell
                '6topRelocatedBundles':0,   # number of time 6top relocates a bundle
                # tsch
                'droppedMacRetries':   0,   # packets dropped because more than TSCH_MAXTXRETRIES MAC retries
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
            returnVal['txQueueFill']        = len(self.txQueue)
            returnVal['chargeConsumed']     = self.chargeConsumed
            returnVal['numTx']              = sum([cell['numTx'] for (_,cell) in self.schedule.items()])
        
        # reset the statistics
        self._resetMoteStats()
        self._resetQueueStats()
        self._resetLatencyStats()
        
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

