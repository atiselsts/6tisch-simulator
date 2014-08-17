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

#============================ defines =========================================

#============================ body ============================================

class Mote(object):
    
    # sufficient num. of tx to estimate pdr by ACK
    NUM_SUFFICIENT_TX             = 10
    # sufficient num. of DIO to determine parent is stable
    NUM_SUFFICIENT_DIO            = 1
    
    DIR_TX                        = 'TX'
    DIR_RX                        = 'RX'
    
    DEBUG                         = 'DEBUG'
    WARNING                       = 'WARNING'
    
    #=== app
    APP_TYPE_DATA                 = 'DATA'
    #=== rpl
    RPL_PARENT_SWITCH_THRESHOLD   = 768 # corresponds to 1.5 hops. 6tisch minimal draft use 384 for 2*ETX.
    RPL_MIN_HOP_RANK_INCREASE     = 256
    RPL_MAX_ETX                   = 4
    RPL_MAX_PATH_COST             = 256*RPL_MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
    RPL_PARENT_SET_SIZE           = 3
    #=== otf
    OTF_HOUSEKEEPING_PERIOD_S     = 1
    OTF_TRAFFIC_SMOOTHING         = 0.5
    # ratio 1/4 -- changing this threshold the detection of a bad cell can be
    # tuned, if as higher the slower to detect a wrong cell but the more prone
    # to avoid churn as lower the faster but with some chances to introduces
    # churn due to unstable medium
    OTF_PDR_THRESHOLD             = 4.0
    #=== tsch
    TSCH_QUEUE_SIZE               = 10
    TSCH_MAXTXRETRIES             = 3
    
    def __init__(self,id):
        
        # store params
        self.id                   = id
        
        # local variables
        self.engine               = SimEngine.SimEngine()
        self.settings             = SimSettings.SimSettings()
        self.propagation          = Propagation.Propagation()
        
        self.dagRoot              = False
        
        self.dataLock             = threading.RLock()
        self.setLocation()
        self.waitingFor           = None
        self.RSSI                 = {} #indexed by neighbor
        self.PDR                  = {} #indexed by neighbor
        self.numCells             = {}
        self.schedule             = {}
        self.txQueue              = []
        self.txPower              = 0
        self.antennaGain          = 0
        self.radioSensitivity     = -101
        self.noisepower           = -105 # in dBm
        self.pktToSend            = None
        self.asnOTFevent          = None
        self.timeBetweenOTFevents = []
        
        # set DIO period as 1 cycle of slotframe
        self.dioPeriod            = self.settings.slotframeLength
        # number of received DIOs
        self.numRxDIO             = {} #indexed by neighbor
        self.collectDIO           = False
        self.dataStart            = False
        
        # RPL initialization
        self.ranks                = {} # indexed by neighbor
        self.dagRanks             = {} # indexed by neighbor
        self.trafficDistribution  = {} # indexed by parents, traffic portion of outgoing traffic
        
        if self.id == 0: # mote with id 0 becomes a DAG root
           self.dagRoot           = True
           self.rank              = 0
           self.dagRank           = 0
           self.parent            = self
           self.accumLatency      = 0 # Accumulated latency to reach to DAG root (in slot)
        else:
           self.dagRoot           = False
           self.rank              = None
           self.dagRank           = None
           self.parentSet         = [] # set of parents
           self.parent            = None # preferred parent
        
        self._resetStats()
        
        self.incomingTraffic     = {} #indexed by neighbor
        self.averageIncomingTraffics = {}#indexed by neighbor
    
    #======================== stack ===========================================
    
    #===== application
    
    def _app_schedule_sendData(self):
        ''' create an event that is inserted into the simulator engine to send the data according to the traffic'''

        # compute random
        delay           = self.settings.pkPeriod*(1.0+self.settings.pkPeriodVar*(-1+2*random.random()))
        assert delay>0
        
        # schedule
        self.engine.scheduleIn(
            delay       = delay,
            cb          = self._app_action_sendData,
            uniqueTag   = (self.id, 'sendData')
        )
    
    def _app_action_sendData(self):
        ''' actual send data function. Evaluates queue length too '''
        
        if self.getTxCells() != []:
            
            # add to queue
            self._incrementStats('dataGenerated')
            if len(self.txQueue)==self.TSCH_QUEUE_SIZE:
                self._incrementStats('dataQueueFull')
            else:
                self._incrementStats('dataQueueOK')
                self.txQueue += [{
                    'asn':        self.engine.getAsn(),
                    'type':       self.APP_TYPE_DATA,
                    'payload':    [self.id,self.engine.getAsn()], # the payload is used for latency calculation
                    'retriesLeft':self.TSCH_MAXTXRETRIES
                }]
        
        # schedule next _app_action_sendData
        self._app_schedule_sendData()
    
    def _app_divideTrafficBetweenParents(self):
        ''' sets the period to communicate for all neighbors/parents '''
        with self.dataLock:
            
            # divides data portion to parents in inverse ratio to DagRank
            reciprocalResultingRanks = dict([(p, 1.0/(self.ranks[p]+self._rpl_computeRankIncrease(p))) for p in self.parentSet])
            sumRecRanks = float(sum(reciprocalResultingRanks.values()))
            self.trafficDistribution = dict([(p, reciprocalResultingRanks[p]/sumRecRanks) for p in self.parentSet])
    
    #===== RPL
    
    def _rpl_schedule_DIO(self):
        ''' tells to the simulator engine to add an event of DIO
        '''
        with self.dataLock:
            asn = self.engine.getAsn()
                    
            # get timeslotOffset of current asn
            ts = asn%self.settings.slotframeLength
            
            # schedule at the start of next cycle
            self.engine.scheduleAtAsn(
                asn         = asn-ts+self.dioPeriod,
                cb          = self._rpl_action_DIO,
                uniqueTag   = (self.id,'DIO'),
            )
    
    def _rpl_action_DIO(self):
        ''' Broadcast DIO to neighbors. Current implementation assumes DIO can be sent out of band.
        '''
        self._log(self.DEBUG,"_rpl_action_DIO")
        
        with self.dataLock:

            if self.parent != None:
            
                # update rank
                self._rpl_setRank()
                
                for neighbor in self.PDR.keys():
                    if neighbor.dagRoot == False:
                        # neighbor stores DAG rank and rank from the sender
                        neighbor.dagRanks[self] = self.dagRank
                        neighbor.ranks[self] = self.rank
                        
                        # count num of DIO received
                        if self in neighbor.numRxDIO:
                            neighbor.numRxDIO[self] += 1
                        else:
                            neighbor.numRxDIO[self] = 0
                        
                        # neighbor updates its parent
                        neighbor._rpl_setParent()
                        neighbor._app_divideTrafficBetweenParents()
                    
            self._rpl_schedule_DIO()
    
    def _rpl_setRank(self):
        with self.dataLock:
            if self.dagRoot == True:
                self.rank = 0
                self.dagRank = 0
            elif self.parent != None:
                self.rank = self.ranks[self.parent] + self._rpl_computeRankIncrease(self.parent)
                self.dagRank = int(self.rank/self.RPL_MIN_HOP_RANK_INCREASE)
    
    def _rpl_setParent(self):
        with self.dataLock:
    
            if self.dagRoot == False:
                
                if self.parent != None:
                    # a preferred parent is already set
                    self._rpl_setRank()
                    rankIncrease = self._rpl_computeRankIncrease(self.parent)
                    
                    # Reset the preferred parent if it does not satisfy the requirements
                    if self.rank > self.RPL_MAX_PATH_COST:
                        self.parent = None
                    
                    # initialize a set of parents
                    self.parentSet = []
                    resultingRanks = {}
                    for (neighbor, dagRank) in self.dagRanks.items():
                                                
                        # compare dagRank of neighbor with that of current parent
                        neighborRankInc = self._rpl_computeRankIncrease(neighbor)
                        neighborResultingRank = self.ranks[neighbor] + neighborRankInc
                                                                            
                        # check requirements for a set of parents
                        if (dagRank < self.dagRank
                            and neighborResultingRank <= self.RPL_MAX_PATH_COST):
                            resultingRanks[neighbor] = neighborResultingRank
                            
                    ranks = sorted(resultingRanks.items(), key = lambda x:x[1])
                    self.parentSet = [nei for (nei,_) in ranks]
                    self.parentSet = self.parentSet[0:self.RPL_PARENT_SET_SIZE]
                                                
                    if len(self.parentSet) != 0:
                        if self.parent in self.parentSet:
                            # check requirement if changing a preferred parent
                            if self.rank - resultingRanks[self.parentSet[0]] > self.RPL_PARENT_SWITCH_THRESHOLD:
                                log.info("a preferred parent of {0} changes from {1} to {2}".format(self.id, self.parent.id, self.parentSet[0].id))
                                self.parent = self.parentSet[0]
                                self._rpl_setRank()
                                # DAG rank of a parent has to be lower than DAG rank of a child
                                for p in self.parentSet[1:self.RPL_PARENT_SET_SIZE]:
                                    if self.dagRanks[p] >= self.dagRank:
                                        self.parentSet.remove(p)
                        else:
                            log.info("a preferred parent of {0} is reset to {1}".format(self.id, self.parentSet[0].id))
                            self.parent = self.parentSet[0]
                            self._rpl_setRank()
                            for p in self.parentSet[1:self.RPL_PARENT_SET_SIZE]:
                                if self.dagRanks[p] >= self.dagRank:
                                    self.parentSet.remove(p)
                        
                    else: # case that no neighbors satisfy the parent requirements
                        # find tentative parents with low resulting rank
                        resultingRanks = {}
                        for (neighbor, _) in self.dagRanks.items():
                            resultingRanks[neighbor] = self.ranks[neighbor] + self._rpl_computeRankIncrease(neighbor)
                        ranks = sorted(resultingRanks.items(), key = lambda x:x[1])
                        self.parentSet = [nei for (nei,_) in ranks]
                        self.parentSet = self.parentSet[0:self.RPL_PARENT_SET_SIZE]
                        self.parent = self.parentSet[0]
                        self._rpl_setRank()
                        log.warning("no neighbors satisfy the parent requirements for {0}; tentatively set {1} as a preferred parent".format(self.id, self.parent.id))
                        for p in self.parentSet[1:self.RPL_PARENT_SET_SIZE]:
                            if self.dagRanks[p] >= self.dagRank:
                                self.parentSet.remove(p)
                
                elif self.dagRanks != {}:
                    # first parent setting
                    # len(self.dagRanks) == 1 as the _rpl_setParent() is called soon after the first neighbor is inserted in dagRanks
                    
                    (minRank, minNeighbor) = min((v,k) for (k,v) in self.dagRanks.items())
                    rankIncrease = self._rpl_computeRankIncrease(minNeighbor)
                    resultingRank = self.ranks[minNeighbor] + rankIncrease
                    
                    if (resultingRank <= self.RPL_MAX_PATH_COST):
                        self.parent = minNeighbor
                        self._rpl_setRank()
                        self.parentSet.append(minNeighbor)
                        log.info("a preferred parent of {0} is set to {1}".format(self.id, self.parent.id))
    
    def _rpl_computeRankIncrease(self, neighbor):
        # calculate rank increase to neighbor
        with self.dataLock:
            
            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr = self.getPDR(neighbor)/100.0
            numTx = self.NUM_SUFFICIENT_TX
            numTxAck = math.floor(pdr*numTx)
                    
            for (_,cell) in self.schedule.items():
                if (cell['neighbor'] == neighbor) and (cell['dir'] == self.DIR_TX):
                    numTx += cell['numTx']
                    numTxAck += cell['numTxAck']
            
            # calculate ETX
            if numTxAck > 0:
                etx = float(numTx)/float(numTxAck)
            else:
                etx = float(numTx)/0.1 # to avoid division by zero

            # minimal 6tisch uses 2*ETX*RPL_MIN_HOP_RANK_INCREASE
            return int(2 * self.RPL_MIN_HOP_RANK_INCREASE * etx)
    
    #===== otf
    
    def _otf_schedule_monitoring(self):
        ''' tells to the simulator engine to add an event to monitor the network'''
        self.engine.scheduleIn(
            delay     = self.OTF_HOUSEKEEPING_PERIOD_S*(0.9+0.2*random.random()),
            cb        = self._otf_action_monitoring,
            uniqueTag = (self.id,'monitoring')
        )
    
    def _otf_action_monitoring(self):
        ''' the monitoring action. allocates more cells if the objective is not met. '''
        self._log(self.DEBUG,"_otf_action_monitoring")
        
        with self.dataLock:
            
            # if DIO from all neighbors are collected, set self.collectDIO = True
            if self.collectDIO == False:
                self.collectDIO = True
                for neighbor in self.PDR.keys():
                    if self.numRxDIO.has_key(neighbor):
                        if self.numRxDIO[neighbor] < self.NUM_SUFFICIENT_DIO:
                            self.collectDIO = False
                            break
                    else:
                        self.collectDIO = False
                        break
            
            # data generation starts if DIOs are received from all the neighbors
            if self.collectDIO == True and self.dataStart == False and self.dagRoot == False:
                self.dataStart = True
                self._app_schedule_sendData()
            
            # calculate incoming traffic stats
            self._otf_averageIncomingTraffic()
            self._otf_resetIncomingTraffic()
            
            # calculate total traffic
            totalTraffic = 1.0/self.settings.pkPeriod*self.settings.slotframeLength*self.settings.slotDuration # converts from (sec/pkt) to (pkt/cycle)
            for n in self.PDR.keys():
                if self.averageIncomingTraffics.has_key(n):
                    totalTraffic += self.averageIncomingTraffics[n]/self.OTF_HOUSEKEEPING_PERIOD_S*self.settings.slotframeLength*self.settings.slotDuration
            
            if self.dataStart == True:
                for n,portion in self.trafficDistribution.iteritems():
                    
                    # ETX acts as overprovision
                    reqNumCell = int(math.ceil(self._otf_estimateETX(n)*portion*totalTraffic)) # required bandwidth
                    #reqNumCell = math.ceil(portion*totalTraffic) # required bandwidth
                    threshold = int(math.ceil(portion*self.settings.otfThreshold))
                    
                    # Compare outgoing traffic with total traffic to be sent
                    numCell = self.numCells.get(n)
                    if numCell is None:
                        numCell=0
                    otfEvent=True
                    if reqNumCell > numCell:
                        for i in xrange(reqNumCell-numCell+(threshold+1)/2):
                            if not self._6top_addCell(n):
                                break # cannot find free time slot
                    elif reqNumCell < numCell-threshold:
                        for i in xrange(numCell-reqNumCell-(threshold+1)/2):
                            if not self._otf_removeWorstCellToNeighbor(n):
                                break # cannot find worst cell due to insufficient tx
                    else:
                        otfEvent=False
                    if otfEvent:
                        if self.asnOTFevent == None:
                            self.asnOTFevent=self.engine.getAsn()
                            assert len(self.timeBetweenOTFevents)==0
                        else:
                            now=self.engine.getAsn()
                            self.timeBetweenOTFevents+=[now-self.asnOTFevent]
                            self.asnOTFevent=now
                #find worst cell in a bundle and if it is way worst and reschedule it
                self._otf_rescheduleCellIfNeeded(n)
                # Neighbor also has to update its next active cell
                n._tsch_schedule_activeCell()
            
            # remove scheduled cells if its destination is not a parent
            for n in self.PDR.keys():        # for all neighbors
                if not self.trafficDistribution.has_key(n):
                    remove = False
                    for (ts,cell) in self.schedule.items():
                        if cell['neighbor'] == n and cell['dir'] == self.DIR_TX:
                            remove = True
                            self._6top_removeCell(ts,cell)
                    if remove == True: # if at least one cell is removed, then updade next active cell
                        n._tsch_schedule_activeCell()
            
            # schedule next active cell
            # Note: this is needed in case the monitoring action modified the schedule
            self._tsch_schedule_activeCell()
            
            # schedule next monitoring
            self._otf_schedule_monitoring()
    
    def _otf_estimateETX(self,neighbor):
        # estimate ETX from self to neighbor by averaging the all Tx cells
        with self.dataLock:

            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr = self.getPDR(neighbor)/100.0
            numTx = self.NUM_SUFFICIENT_TX
            numAck = math.floor(pdr*numTx)

            for ts in self.schedule.keys():
                ce = self.schedule[ts]
                if ce['neighbor'] == neighbor and ce['dir'] == self.DIR_TX:
                    numTx  += ce['numTx']
                    numAck += ce['numTxAck']
                    
            #estimate PDR if sufficient num of tx is available
            if numAck == 0:
                etx = float(numTx) # set a large value when pkts are never ack
            else:
                etx = float(numTx) / float(numAck)
            
            if numTx > self.RPL_MAX_ETX: # to avoid large ETX consumes too many cells
                etx = self.RPL_MAX_ETX
            
            return etx
    
    def _otf_removeWorstCellToNeighbor(self, node):
        ''' finds the worst cell in each bundle and remove it from schedule
        '''
        worst_cell = (None, None, None)
        count = 0 # for debug
        #look into all links that point to the node
        for ts in self.schedule.keys():
            ce = self.schedule[ts]
            if ce['neighbor'] == node:
                
                #compute PDR to each node
                count += 1
                if ce['numTx'] == 0: # we don't select unused cells
                    pdr = 1.0
                elif ce['numTxAck'] == 0:
                    pdr = float(0.1/float(ce['numTx'])) # this enables to decide e.g. (Tx,Ack) = (10,0) is worse than (1,0)
                else:
                    pdr = float(ce['numTxAck']) / float(ce['numTx'])
                
                if worst_cell == (None,None,None):
                    worst_cell = (ts, ce, pdr)
                
                #find worst cell in terms of pdr
                if pdr < worst_cell[2]:
                    worst_cell = (ts, ce, pdr)
        
        if worst_cell != (None,None,None):
            # remove the worst cell
            log.info("remove cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0], worst_cell[1]['ch'], self.id, worst_cell[1]['neighbor'].id))
            self._log(self.DEBUG, "remove cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
            self._6top_removeCell(worst_cell[0], worst_cell[1])
            # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
            self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
            self._tsch_schedule_activeCell()
            self.engine.removeEvent(uniqueTag=(worst_cell[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
            worst_cell[1]['neighbor']._tsch_schedule_activeCell()
            return True
    
    def _otf_rescheduleCellIfNeeded(self, node):
        ''' finds the worst cell in each bundle. If the performance of the cell is bad compared to
            other cells in the bundle reschedule this cell.
        '''
        bundle_avg = []
        worst_cell = (None, None, None)
        
        #look into all links that point to the node
        numTxTotal  = 0
        numAckTotal = 0
        for ts in self.schedule.keys():
            ce = self.schedule[ts]
            if ce['neighbor'] == node and ce['numTx'] >= self.NUM_SUFFICIENT_TX:

                numTxTotal += ce['numTx']
                numAckTotal += ce['numTxAck']

                #compute PDR to each node with sufficient num of tx
                pdr = float(ce['numTxAck']) / float(ce['numTx'])
                
                
                if worst_cell == (None,None,None):
                    worst_cell = (ts, ce, pdr)
                
                #find worst cell in terms of pdr
                if pdr < worst_cell[2]:
                    worst_cell = (ts, ce, pdr)
                                 
                #this is part of a bundle of cells for that neighbor, keep
                #the tuple ts, schedule entry, pdr
                bundle_avg += [(ts, ce, pdr)]
        
        #compute the distance to the other cells in the bundle,
        #if the worst cell is far from any of the other cells reschedule it
        for bce in bundle_avg:
            #compare pdr, maxCell pdr will be smaller than other cells so the ratio will
            # be bigger if worst_cell is very bad.
            if bce[2]/self.OTF_PDR_THRESHOLD > worst_cell[2]:
            
                #reschedule the cell -- add to avoid scheduling the same
                log.info("reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
                self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
                self._6top_addCell(worst_cell[1]['neighbor'])
                #and delete old one
                self._6top_removeCell(worst_cell[0], worst_cell[1])
                # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
                self.engine.removeEvent(uniqueTag=(worst_cell[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
                self._incrementStats('numCellsReallocated')
                break
        
        # check whether all scheduled cells are collided
        if self.schedule.has_key(worst_cell[0]): # worst cell is not removed
            avgPDR = float(numAckTotal)/float(numTxTotal)
            if self.getPDR(node)/100.0/self.OTF_PDR_THRESHOLD > avgPDR:
                # reallocate all the scheduled cells
                for bce in bundle_avg:
                    log.info("reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(bce[0], bce[1]['ch'], self.id, bce[1]['neighbor'].id))
                    self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(bce[0], bce[1]['ch'], self.id, bce[1]['neighbor'].id))
                    self._6top_addCell(bce[1]['neighbor'])
                    #and delete old one
                    self._6top_removeCell(bce[0], bce[1])
                    # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                    self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
                    self.engine.removeEvent(uniqueTag=(bce[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
                    self._incrementStats('numCellsReallocated')
    
    def _otf_resetIncomingTraffic(self):
        with self.dataLock:
            for neighbor in self.PDR.keys():
                self.incomingTraffic[neighbor] = 0
    
    def _otf_incrementIncomingTraffic(self,neighbor):
        with self.dataLock:
            self.incomingTraffic[neighbor] += 1
    
    def _otf_averageIncomingTraffic(self):
        with self.dataLock:
            for neighbor in self.PDR.keys():
                if self.averageIncomingTraffics.has_key(neighbor):
                    self.averageIncomingTraffics[neighbor] = self.OTF_TRAFFIC_SMOOTHING*self.incomingTraffic[neighbor] \
                    + (1-self.OTF_TRAFFIC_SMOOTHING)*self.averageIncomingTraffics[neighbor]
                elif self.incomingTraffic[neighbor] != 0:
                    self.averageIncomingTraffics[neighbor] = self.incomingTraffic[neighbor]
    
    #===== 6top
    
    def _6top_addCell(self,neighbor):
        ''' tries to allocate a cell to a neighbor. It retries until it finds one available slot. '''
        
        with self.dataLock:
            for trial in range(0,10000):
                candidateTimeslot      = random.randint(0,self.settings.slotframeLength-1)
                candidateChannel       = random.randint(0,self.settings.numChans-1)
                if  (
                        self._6top_isUnusedSlot(candidateTimeslot) and
                        neighbor._6top_isUnusedSlot(candidateTimeslot)
                    ):
                    self._tsch_addCell(
                        ts             = candidateTimeslot,
                        ch             = candidateChannel,
                        dir            = self.DIR_TX,
                        neighbor       = neighbor,
                    )
                    neighbor._tsch_addCell(
                        ts             = candidateTimeslot,
                        ch             = candidateChannel,
                        dir            = self.DIR_RX,
                        neighbor       = self,
                    )
                    log.info('allocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}'.format(candidateTimeslot, candidateChannel, self.id, neighbor.id))
                    if neighbor not in self.numCells:
                        self.numCells[neighbor]    = 0
                    self.numCells[neighbor]  += 1
                    
                    #TODO count number or retries.
                    return True
            log.error('tried {0} times but unable to find an empty time slot for nodes {1} and {2}'.format(trial+1,self.id,neighbor.id))
    
    def _6top_removeCell(self,ts,cell):
        ''' removes a cell in the schedule of this node and the neighbor '''
        with self.dataLock:
            self._tsch_removeCell(
                ts           = ts,
                neighbor     = cell['neighbor'],
            )
            cell['neighbor']._tsch_removeCell(
                ts           = ts,
                neighbor     = self,
            )
            self.numCells[cell['neighbor']] -= 1
    
    def _6top_isUnusedSlot(self,ts):
        with self.dataLock:
            return not (ts in self.schedule)
    
    #===== TSCH
    
    def _tsch_schedule_activeCell(self):
        ''' called by the engine. determines the next action to be taken in case this Mote has a schedule'''
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        tsCurrent = asn%self.settings.slotframeLength
        
        # find closest active slot in schedule
        with self.dataLock:
            
            if not self.schedule:
                self._log(self.WARNING,"empty schedule")
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
        self._log(self.DEBUG,"_tsch_action_activeCell")
        
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.slotframeLength
        
        with self.dataLock:
            # make sure this is an active slot
            # NOTE: might be relaxed when schedule is changed
               
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
                if self.txQueue != []:
                    self.pktToSend = self.txQueue[0]
                    self.txQueue[0]['retriesLeft'] -= 1
                
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
                else:
                    # debug purpose to check
                    self.propagation.noTx(
                        channel   = cell['ch'],
                        smac      = self,
                        dmac      = cell['neighbor']
                    )
                    # schedule next active cell
                    
                    self._tsch_schedule_activeCell()
    
    def _tsch_addCell(self,ts,ch,dir,neighbor):
        ''' adds a cell to the schedule '''
        self._log(self.DEBUG,"_tsch_addCell ts={0} ch={1} dir={2} with {3}".format(ts,ch,dir,neighbor.id))
        
        with self.dataLock:
            assert ts not in self.schedule.keys()
            self.schedule[ts] = {
                'ch':                 ch,
                'dir':                dir,
                'neighbor':           neighbor,
                'numTx':              0,
                'numTxAck':           0,
                'numRx':              0,
                'numTxFailures':      0,
                'numRxFailures':      0,
            }
    
    def _tsch_removeCell(self,ts,neighbor):
        ''' removes a cell from the schedule '''
        self._log(self.DEBUG,"_tsch_removeCell ts={0} with {1}".format(ts,neighbor.id))
        with self.dataLock:
            assert ts in self.schedule.keys()
            assert neighbor == self.schedule[ts]['neighbor']
            del self.schedule[ts]
    
    #===== radio
    
    def txDone(self,success):
        '''end of tx slot. compute stats and schedules next action '''
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.slotframeLength
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.waitingFor==self.DIR_TX
            
            cell = self.schedule[ts]
            
            if success:
                self.schedule[ts]['numTxAck'] += 1
                self.txQueue.remove(self.pktToSend)
                self.engine.queueDelays+=[self.engine.getAsn()-self.pktToSend['asn']]
                
            else:
                # failure include collision and normal packet error
                self.schedule[ts]['numTxFailures'] += 1
                i = self.txQueue.index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] == 0:
                    self.txQueue.remove(self.pktToSend)
            self.waitingFor = None
            
            # schedule next active cell
            self._tsch_schedule_activeCell()
    
    def rxDone(self,type=None,smac=None,dmac=None,payload=None,failure=False):
        '''end of rx slot. compute stats and schedules next action '''
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.slotframeLength
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.waitingFor==self.DIR_RX
            
            cell = self.schedule[ts]
            
            # successfully received
            if smac:
                self.schedule[ts]['numRx'] += 1
            # collision
            if failure:
                self.schedule[ts]['numRxFailures'] += 1
            
            self.waitingFor = None
            
            if self.dagRoot == True and smac != None:
                self._incrementStats('dataReceived')
                self.accumLatency += asn-payload[1]
                        
            if self.dagRoot == False and self.parent != None and smac != None and self.getTxCells()!=[]:
                
                # count incoming traffic for each node
                self._otf_incrementIncomingTraffic(smac)
                
                # add to queue
                self._incrementStats('dataReceived')
                if len(self.txQueue)<self.TSCH_QUEUE_SIZE:
                    self.txQueue += [{
                        'asn':      self.engine.getAsn(),
                        'type':     type,
                        'payload':  payload,
                        'retriesLeft': self.TSCH_MAXTXRETRIES
                    }]
                    self._incrementStats('dataQueueOK')
                else:
                    self._incrementStats('dataQueueFull')
        
        # schedule next active cell
        self._tsch_schedule_activeCell()
    
    #===== wireless connectivity
    
    def setPDR(self,neighbor,pdr):
        ''' sets the pdr to that neighbor'''
        with self.dataLock:
            self.PDR[neighbor] = pdr
            
    def getPDR(self,neighbor):
        ''' returns the pdr to that neighbor'''
        with self.dataLock:
            return self.PDR[neighbor]
        
    def setRSSI(self,neighbor,rssi):
        ''' sets the RSSI to that neighbor'''
        with self.dataLock:
            self.RSSI[neighbor.id] = rssi

    def getRSSI(self,neighbor):
        ''' returns the RSSI to that neighbor'''
        with self.dataLock:
            return self.RSSI[neighbor.id]
    
    #===== location
    
    def setLocation(self):
        with self.dataLock:
            self.x = self.settings.squareSide*random.random()
            self.y = self.settings.squareSide*random.random()
    
    def getLocation(self):
        with self.dataLock:
            return (self.x,self.y)
    
    #==== battery
    
    def boot(self):
        self._rpl_schedule_DIO()
        self._otf_resetIncomingTraffic()
        self._otf_schedule_monitoring()
        self._tsch_schedule_activeCell()
    
    #======================== private =========================================
    
    #===== getters
    
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
                        'numTxFailures':  cell['numTxFailures'],
                        'numRxFailures':  cell['numRxFailures'],
                    }
                    break
        return returnVal
    
    def getTxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_TX]
    
    def getRxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_RX]
    
    #===== stats
    
    def getStats(self):
        with self.dataLock:
            return copy.deepcopy(self.stats)
    
    def _resetStats(self):
        with self.dataLock:
            self.stats = {
                'dataGenerated':       0,
                'dataReceived':        0,
                'dataQueueOK':         0,
                'dataQueueFull':       0,
                'numCellsReallocated': 0,
            }
    
    def _incrementStats(self,name):
        with self.dataLock:
            self.stats[name] += 1
    
    #===== log
    
    def _log(self,severity,message):
        
        output  = []
        output += ['[ASN={0} id={1}] '.format(self.engine.getAsn(),self.id)]
        output += [message]
        output  = ''.join(output)
        
        if   severity==self.DEBUG:
            if log.isEnabledFor(logging.DEBUG):
                logfunc = log.debug
            else:
                logfunc = None
        elif severity==self.WARNING:
            logfunc = log.warning
        
        if logfunc:
            logfunc(output)