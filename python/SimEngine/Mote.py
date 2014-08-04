#!/usr/bin/python

'''
 @authors:
       Thomas Watteyne    <watteyne@eecs.berkeley.edu>    
       Xavier Vilajosana  <xvilajosana@uoc.edu> 
                          <xvilajosana@eecs.berkeley.edu>
'''

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Mote')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

import copy
import random
import threading
import math
import SimEngine
import Propagation
import SimSettings

class Mote(object):
    
    HOUSEKEEPING_PERIOD      = 1
    QUEUE_SIZE               = 10
    
    # sufficient num. of tx to estimate pdr by ACK
    NUM_SUFFICIENT_TX        = 10  
    
    # sufficient num. of DIO to determine parent is stable
    NUM_SUFFICIENT_DIO       = 1
    
    PARENT_SWITCH_THRESHOLD  = 768# corresponds to 1.5 hops. 6tisch minimal draft use 384 for 2*ETX. 
    MIN_HOP_RANK_INCREASE    = 256
    MAX_ETX                  = 4
    MAX_LINK_METRIC          = MAX_ETX*MIN_HOP_RANK_INCREASE*2 # 4 transmissions allowed for one hop for parents
    MAX_PATH_COST            = 256*MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
    PARENT_SET_SIZE          = 3
    
    SMOOTHING                = 0.5
    
    DIR_TX                   = 'TX'
    DIR_RX                   = 'RX'
    
    DEBUG                    = 'DEBUG'
    WARNING                  = 'WARNING'
    
    TYPE_DATA                = 'DATA'
    
    TX                       = 'TX'
    RX                       = 'RX'
    #ratio 1/4 -- changing this threshold the detection of a bad cell can be tuned, if
    #as higher the slower to detect a wrong cell but the more prone to avoid churn
    #as lower the faster but with some chances to introduces churn due to unstable medium
    PDR_THRESHOLD            = 4.0   
                             
    def __init__(self,id):
        
        # store params
        self.id              = id
        
        self.dagRoot         = False
        # variables
        self.settings        = SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine()
        self.propagation     = Propagation.Propagation()
        self.dataLock        = threading.RLock()
        self.setLocation()
        self.waitingFor      = None
        self.radioChannel    = None
        self.PDR             = {} #indexed by neighbor
        self.RSSI            = {} #indexed by neighbor        
        self.numCells        = {}
        self.booted          = False
        self.schedule        = {}
        self.txQueue         = []
        self.tPower          = 0
        self.antennaGain     = 0
        self.radioSensitivity = -101
        

        # set _action_monitoring after all traffic generated (1.1 * slot frame duration assumed)
        # so that cell scheduling can start
        # this setting also prevents that _action_activeCell can be called without no data at queue
        self.firstHousekeepinPeriod = 1.1 * self.settings.slotDuration * self.settings.timeslots 
        
        # set DIO period as 1 cycle of slotframe
        self.dioPeriod = self.settings.timeslots
        # number of received DIOs
        self.numRxDIO = {} #indexed by neighbor
        self.collectDIO = False
        self.dataStart = False
        
        # RPL initialization
        self.ranks           = {} #indexed by neighbor
        self.dagRanks        = {} #indexed by neighbor
        self.trafficDistribution = {} # indexed by parents, traffic portion of outgoing traffic
                
        if self.id == 0: # mote with id 0 becomes a DAG root  
           self.dagRoot = True
           self.rank    = 0
           self.dagRank = 0
           self.parent  = self
           self.numPktReached = 0 # number of packets reached to DAG root
        else:
           self.dagRoot = False
           self.rank    = None
           self.dagRank = None
           self.parent  = None # preferred parent    
           self.parents = [] # set of parents

        self._resetStats()

        self.incomingTraffics = {} #indexed by neighbor
        self.averageIncomingTraffics = {}#indexed by neighbor
        
        
    #======================== public =========================================
                        
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
            self.RSSI[neighbor] = rssi

    def getRSSI(self,neighbor):
        ''' returns the RSSI to that neighbor'''
        with self.dataLock:
            return self.RSSI[neighbor]
    
    def boot(self):
        ''' boots the mote '''
        with self.dataLock:
            self.booted      = False
        
        # schedule first monitoring
        self._schedule_monitoring(delay = self.firstHousekeepinPeriod)        
        # schedule first active cell
        self._schedule_next_ActiveCell()
        # schedule DIO
        self._schedule_DIO()
        # reset traffic stats
        self._resetIncomingTraffics()
    
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
    
    def setLocation(self):
        with self.dataLock:
            self.x = random.random()*self.settings.side #in km, * 10^3 to represent meters
            self.y = random.random()*self.settings.side #in km, * 10^3 to represent meters (these are in cm so it can be plotted)

    def getLocation(self):
        with self.dataLock:
            return (self.x,self.y)
    
    def getStats(self):
        with self.dataLock:
            return copy.deepcopy(self.stats)
    
    # TODO: replace direct call by packets
    def isUnusedSlot(self,ts):
        with self.dataLock:
            return not (ts in self.schedule)
    
    # TODO: replace direct call by packets
    def scheduleCell(self,ts,ch,dir,neighbor):
        ''' adds a cell to the schedule '''
        self._log(self.DEBUG,"scheduleCell ts={0} ch={1} dir={2} with {3}".format(ts,ch,dir,neighbor.id))
        
        with self.dataLock:
            assert ts not in self.schedule.keys()
            self.schedule[ts] = {
                'ch':                 ch,
                'dir':                dir,
                'neighbor':           neighbor,
                'numTx':              0,
                'numTxAck':           0,
                'numRx':              0,
                'numTxFailures':    0,
                'numRxFailures':    0,
            }
            
    def removeCell(self,ts,neighbor):
        ''' removes a cell from the schedule '''
        self._log(self.DEBUG,"removeCell ts={0} with {1}".format(ts,neighbor.id))
        with self.dataLock:
            assert ts in self.schedule.keys()
            assert neighbor == self.schedule[ts]['neighbor']
            del self.schedule[ts]
    
    def setRank(self):
        with self.dataLock:
            if self.dagRoot == True:
                self.rank = 0
                self.dagRank = 0 
            elif self.parent != None:
                self.rank = self.ranks[self.parent] + self.computeRankIncrease(self.parent)
                self.dagRank = int(self.rank/self.MIN_HOP_RANK_INCREASE) 
    
    def setParent(self):
        with self.dataLock:
    
            if self.dagRoot == False:
                
                if self.parent != None:
                    # a preferred parent is already set
                    self.setRank()            
                    rankIncrease = self.computeRankIncrease(self.parent)
                    
                    # Reset the preferred parent if it does not satisfy the requirements
                    # if rankIncrease > self.MAX_LINK_METRIC or self.rank > self.MAX_PATH_COST:
                    # condition of MAX_LINK_METRIC excluded to avoid loop   
                    if self.rank > self.MAX_PATH_COST:
                        self.parent = None
                    
                    # initialize a set of parents
                    self.parents = []
                    resultingRanks = {}
                    for (neighbor, dagRank) in self.dagRanks.items():
                                                
                        # compare dagRank of neighbor with that of current parent
                        neighborRankInc = self.computeRankIncrease(neighbor)
                        neighborResultingRank = self.ranks[neighbor] + neighborRankInc
                                                                            
                        # check requirements for a set of parents
                        if (dagRank < self.dagRank 
                            #and neighborRankInc <= self.MAX_LINK_METRIC # condition of MAX_LINK_METRIC excluded to avoid loop
                            and neighborResultingRank <= self.MAX_PATH_COST):                                                                            
                            resultingRanks[neighbor] = neighborResultingRank
                            
                    ranks = sorted(resultingRanks.items(), key = lambda x:x[1])
                    self.parents = [nei for (nei,_) in ranks]
                    self.parents = self.parents[0:self.PARENT_SET_SIZE]
                                                
                    if len(self.parents) != 0:
                        if self.parent in self.parents:                            
                            # check requirement if changing a preferred parent 
                            if self.rank - resultingRanks[self.parents[0]] > self.PARENT_SWITCH_THRESHOLD:
                                print "a preferred parent of {0} changes from {1} to {2}".format(self.id, self.parent.id, self.parents[0].id) 
                                self.parent = self.parents[0]
                                self.setRank()
                                # DAG rank of a parent has to be lower than DAG rank of a child 
                                for p in self.parents[1:self.PARENT_SET_SIZE]:
                                    if self.dagRanks[p] >= self.dagRank:
                                        self.parents.remove(p) 
                                                                
                        else:
                            print "a preferred parent of {0} is reset to {1}".format(self.id, self.parents[0].id) 
                            self.parent = self.parents[0]
                            self.setRank()
                            for p in self.parents[1:self.PARENT_SET_SIZE]:
                                if self.dagRanks[p] >= self.dagRank:
                                    self.parents.remove(p) 

                    else: # case that no neighbors satisfy the parent requirements
                        # find tentative parents with low resulting rank
                        resultingRanks = {}
                        for (neighbor, _) in self.dagRanks.items():
                            resultingRanks[neighbor] = self.ranks[neighbor] + self.computeRankIncrease(neighbor)
                        ranks = sorted(resultingRanks.items(), key = lambda x:x[1])
                        self.parents = [nei for (nei,_) in ranks]
                        self.parents = self.parents[0:self.PARENT_SET_SIZE]
                        self.parent = self.parents[0]
                        self.setRank()
                        print "no neighbors satisfy the parent requirements for {0}; tentatively set {1} as a preferred parent".format(self.id, self.parent.id) 
                        for p in self.parents[1:self.PARENT_SET_SIZE]:
                            if self.dagRanks[p] >= self.dagRank:
                                self.parents.remove(p) 
                                                
                elif self.dagRanks != {}:
                    # first parent setting
                    # len(self.dagRanks) == 1 as the setParent() is called soon after the first neighbor is inserted in dagRanks
                    
                    (minRank, minNeighbor) = min((v,k) for (k,v) in self.dagRanks.items())                    
                    rankIncrease = self.computeRankIncrease(minNeighbor)
                    resultingRank = self.ranks[minNeighbor] + rankIncrease                        
                    
                    # condition of MAX_LINK_METRIC excluded to avoid loop
                    #if (rankIncrease <= self.MAX_LINK_METRIC and resultingRank <= self.MAX_PATH_COST):                              
                    if (resultingRank <= self.MAX_PATH_COST):                              
                        self.parent = minNeighbor
                        self.setRank()
                        self.parents.append(minNeighbor)
                        print "a preferred parent of {0} is set to {1}".format(self.id, self.parent.id) 
                
            
    def computeRankIncrease(self, neighbor):
        # calculate rank increase to neighbor
        with self.dataLock:    
            
            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr = self.getPDR(neighbor)/100.0
            numTx = self.NUM_SUFFICIENT_TX
            numTxAck = math.floor(pdr*numTx)
                    
            for (_,cell) in self.schedule.items():
                if (cell['neighbor'] == neighbor) and (cell['dir'] == self.TX):
                    numTx += cell['numTx']
                    numTxAck += cell['numTxAck']
            
            # calculate ETX            
            if numTxAck > 0:
                etx = float(numTx)/float(numTxAck)            
            else:
                etx = float(numTx)/0.1 # to avoid division by zero

            # minimal 6tisch uses 2*ETX*MIN_HOP_RANK_INCREASE    
            return int(2 * self.MIN_HOP_RANK_INCREASE * etx)

    def setTrafficDistribution(self):
        ''' sets the period to communicate for all neighbors/parents '''
        with self.dataLock:
            
            # divides data portion to parents in inverse ratio to DagRank
            sum = 0.0
            resultingRanks = {}
            self.trafficDistribution = {}
            for p in self.parents:
                resultingRanks[p] = self.ranks[p] + self.computeRankIncrease(p)
                sum += 1.0/resultingRanks[p]
            for p in self.parents:
                portion = (1.0/resultingRanks[p])/sum
                self.trafficDistribution[p] = portion
        
    def selectNextHop(self):
        # select next hop to relay a packet based on the current traffic allotment
        with self.dataLock:
            
            numNeighborInQueue = {}            
            for neighbor in self.PDR.keys():
                numNeighborInQueue[neighbor] = 0
                    
            # count num of packets in queue per neighbor 
            for i in range(len(self.txQueue)):
                neighbor = self.txQueue[i]['nextHop']
                numNeighborInQueue[neighbor] += 1

            asn = self.engine.getAsn()                    
            # get timeslotOffset of current asn
            ts = asn%self.settings.timeslots
            
            txCells = self.getTxCells()
            # finally returns the neighbor which does not have a packet to send in queue
            i = 1
            while True:
                scan = (ts+i) % self.settings.timeslots # search starts from next asn (ts+1)
                for j in range(len(txCells)):
                    if scan == txCells[j][0]:
                        neighbor = txCells[j][2]
                        numNeighborInQueue[neighbor] -= 1
                        if numNeighborInQueue[neighbor] < 0:
                            return neighbor
                        else:
                            break
                i += 1
            
    def estimateETX(self,neighbor):
        # estimate ETX from self to neighbor by averaging the all Tx cells
        with self.dataLock:

            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr = self.getPDR(neighbor)/100.0
            numTx = self.NUM_SUFFICIENT_TX
            numAck = math.floor(pdr*numTx)

            for ts in self.schedule.keys():
                ce = self.schedule[ts]
                if ce['neighbor'] == neighbor and ce['dir'] == self.TX:
                    numTx  += ce['numTx']
                    numAck += ce['numTxAck']
                    
            #estimate PDR if sufficient num of tx is available
            if numAck == 0:
                etx = float(numTx) # set a large value when pkts are never ack
            else:    
                etx = float(numTx) / float(numAck)        
            
            if numTx > self.MAX_ETX: # to avoid large ETX consumes too many cells
                etx = self.MAX_ETX
            
            return etx  
    
    #======================== actions =========================================
    
    #===== RPL
    
    def _schedule_DIO(self):
        ''' tells to the simulator engine to add an event of DIO 
        '''
        with self.dataLock:  
            asn = self.engine.getAsn()
                    
            # get timeslotOffset of current asn
            ts = asn%self.settings.timeslots
            
            # schedule at the start of next cycle
            self.engine.scheduleAtAsn(
                asn         = asn-ts+self.dioPeriod, 
                cb          = self._action_DIO,
                uniqueTag   = (self.id,'DIO'),
            )


    def _action_DIO(self):
        ''' Broadcast DIO to neighbors. Current implementation assumes DIO can be sent out of band.
        '''
        self._log(self.DEBUG,"_action_DIO")
        
        with self.dataLock:

            if self.parent != None:
            
                # update rank
                self.setRank()
                
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
                        neighbor.setParent()
                        neighbor.setTrafficDistribution()
                    
            self._schedule_DIO()                
            
    
    #===== activeCell
    
    def _action_activeCell(self):
        ''' active slot starts. Determine what todo, either RX or TX, use the propagation model to introduce
            interference and Rx packet drops.
        '''
        self._log(self.DEBUG,"_action_activeCell")
        
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.timeslots
        
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
                self.waitingFor   = self.RX
            
            elif cell['dir']==self.DIR_TX:
                
                # check whether packet to send
                pktToSend = None
                for i in range(len(self.txQueue)):
                    if self.txQueue[i]['nextHop']==cell['neighbor']:
                       pktToSend = self.txQueue.pop(i)
                       break
                
                # send packet
                if pktToSend:
                    
                    cell['numTx'] += 1
                    
                    self.propagation.startTx(
                        channel   = cell['ch'],
                        type      = pktToSend['type'],
                        smac      = self,
                        dmac      = pktToSend['nextHop'],
                        payload   = pktToSend['payload'],
                    )
                    
                    # indicate that we're waiting for the RX operation to finish
                    self.waitingFor   = self.TX
                else:
                    # debug purpose to check 
                    self.propagation.noTx(
                        channel   = cell['ch'],
                        smac      = self,
                        dmac      = cell['neighbor']
                    )
                    # schedule next active cell

                    self._schedule_next_ActiveCell()
                       
    def txDone(self,success):
        '''end of tx slot. compute stats and schedules next action '''
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.timeslots
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.waitingFor==self.TX
            
            cell = self.schedule[ts]
            
            if success:
                self.schedule[ts]['numTxAck'] += 1
            else:
                # failure include collision and normal packet error
                self.schedule[ts]['numTxFailures'] += 1    
            
            self.waitingFor = None
            
            # schedule next active cell
            self._schedule_next_ActiveCell()
    
    def rxDone(self,type=None,smac=None,dmac=None,payload=None,failure=False):
        '''end of rx slot. compute stats and schedules next action ''' 
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        ts = asn%self.settings.timeslots
        
        with self.dataLock:
            
            assert ts in self.schedule
            assert self.waitingFor==self.RX
            
            cell = self.schedule[ts]
            
            # successfully received
            if smac:
                self.schedule[ts]['numRx'] += 1
            # collision
            if failure:
                self.schedule[ts]['numRxFailures'] += 1
                
            
            
            self.waitingFor = None
            
            if self.dagRoot == True and smac != None:
                self._incrementStats('dataRecieved')
                        
            if self.dagRoot == False and self.parent != None and smac != None and self.getTxCells()!=[]:
                
                # count incoming traffic for each node
                self._incrementIncomingTraffics(smac)
                # add to queue
                self._incrementStats('dataRecieved')
                nextHop = self.selectNextHop()
                if len(self.txQueue)<self.QUEUE_SIZE:
                    self.txQueue += [{
                        'asn':      self.engine.getAsn(),
                        'nextHop':  nextHop,
                        'type':     type,
                        'payload':  payload,
                    }]
                    self._incrementStats('dataQueueOK')
                else:
                    self._incrementStats('dataQueueFull')
        
                
        # schedule next active cell
        self._schedule_next_ActiveCell()
    
    def _schedule_next_ActiveCell(self):
        ''' called by the engine. determines the next action to be taken in case this Mote has a schedule''' 
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        tsCurrent = asn%self.settings.timeslots
        
        # find closest active slot in schedule
        with self.dataLock:
            
            if not self.schedule:
                self._log(self.WARNING,"empty schedule")
                return
            
            tsDiffMin             = None
            for (ts,cell) in self.schedule.items():
                if   ts==tsCurrent:
                    tsDiff        = self.settings.timeslots
                elif ts>tsCurrent:
                    tsDiff        = ts-tsCurrent
                elif ts<tsCurrent:
                    tsDiff        = (ts+self.settings.timeslots)-tsCurrent
                else:
                    raise SystemError()
                
                if (not tsDiffMin) or (tsDiffMin>tsDiff):
                    tsDiffMin     = tsDiff
        
        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn         = asn+tsDiffMin,
            cb          = self._action_activeCell,
            uniqueTag   = (self.id,'activeCell'),
        )
    
    #===== sendData
    
    def _action_sendData(self):
        ''' actual send data function. Evaluates queue length too '''
        
        if self.getTxCells() != []:
            nextHop = self.selectNextHop()
            
            # add to queue
            self._incrementStats('dataGenerated')
            if len(self.txQueue)<self.QUEUE_SIZE:
                self.txQueue += [{
                    'asn':      self.engine.getAsn(),
                    'nextHop':  nextHop,
                    'type':     self.TYPE_DATA,
                    'payload':  [],
                }]
                self._incrementStats('dataQueueOK')
            else:
                self._incrementStats('dataQueueFull')
        
        # schedule next _action_sendData
        self._schedule_sendData()
            
    def _schedule_sendData(self):
        ''' create an event that is inserted into the simulator engine to send the data according to the traffic'''

        # compute random
        delay      = self.settings.traffic*(0.9+0.2*random.random())
        
        # schedule
        self.engine.scheduleIn(
            delay     = delay,
            cb        = self._action_sendData,
            uniqueTag = (self.id, 'sendData')
        )
    
    #===== monitoring
    

    def rescheduleCellIfNeeded(self, node):
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
            if bce[2]/self.PDR_THRESHOLD > worst_cell[2]:
            
                #reschedule the cell -- add to avoid scheduling the same
                print "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id)
                self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
                self._addCellToNeighbor(worst_cell[1]['neighbor'])
                #and delete old one
                self._removeCellToNeighbor(worst_cell[0], worst_cell[1])
                # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
                self.engine.removeEvent(uniqueTag=(worst_cell[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
                self._incrementStats('numCellsReallocated')
                break
        
        # check whether all scheduled cells are collided
        if self.schedule.has_key(worst_cell[0]): # worst cell is not removed
            avgPDR = float(numAckTotal)/float(numTxTotal)
            if self.getPDR(node)/100.0/self.PDR_THRESHOLD > avgPDR: 
                # reallocate all the scheduled cells
                for bce in bundle_avg:
                    print "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(bce[0], bce[1]['ch'], self.id, bce[1]['neighbor'].id)
                    self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(bce[0], bce[1]['ch'], self.id, bce[1]['neighbor'].id))
                    self._addCellToNeighbor(bce[1]['neighbor'])
                    #and delete old one
                    self._removeCellToNeighbor(bce[0], bce[1])
                    # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                    self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
                    self.engine.removeEvent(uniqueTag=(bce[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
                    self._incrementStats('numCellsReallocated')
        
        
    def _removeWorstCellToNeighbor(self, node):
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
            #print "remove cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0], worst_cell[1]['ch'], self.id, worst_cell[1]['neighbor'].id)
            self._log(self.DEBUG, "remove cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
            self._removeCellToNeighbor(worst_cell[0], worst_cell[1])
            # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
            self.engine.removeEvent(uniqueTag=(self.id,'activeCell'), exceptCurrentASN = True)
            self._schedule_next_ActiveCell()
            self.engine.removeEvent(uniqueTag=(worst_cell[1]['neighbor'].id,'activeCell'), exceptCurrentASN = True)
            worst_cell[1]['neighbor']._schedule_next_ActiveCell()
            
    def _action_monitoring(self):
        ''' the monitoring action. allocates more cells if the objective is not met. '''
        self._log(self.DEBUG,"_action_monitoring")
                
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
                self._schedule_sendData()
            
            # calculate incoming traffic stats
            self._averageIncomingTraffics()
            self._resetIncomingTraffics()
            
            # calculate total traffic
            totalTraffic = 1.0/self.settings.traffic*self.settings.timeslots*self.settings.slotDuration # converts from (sec/pkt) to (pkt/cycle)
            for n in self.PDR.keys():
                if self.averageIncomingTraffics.has_key(n):
                    totalTraffic += self.averageIncomingTraffics[n]/self.HOUSEKEEPING_PERIOD*self.settings.timeslots*self.settings.slotDuration
            
            for (n,portion) in self.trafficDistribution.items():
                            
                # ETX acts as overprovision
                #reqNumCell = math.ceil(self.estimateETX(n)*portion*totalTraffic) # required bandwidth
                reqNumCell = math.ceil(portion*totalTraffic) # required bandwidth
                
                # Compare outgoing traffic with total traffic to be sent 
                while True:                
                    numCell = self.numCells.get(n)

                    if reqNumCell > numCell:
                        # schedule another cell if needed
                        self._addCellToNeighbor(n)
                        if numCell == self.numCells.get(n): # cannot find free time slot
                            break
                    elif reqNumCell < numCell:
                        self._removeWorstCellToNeighbor(n)
                        if numCell == self.numCells.get(n): # cannot find worst cell due to insufficient tx
                            break                        
                    else: # reqNumCell = numCell
                        break
                
                #find worst cell in a bundle and if it is way worst and reschedule it
                self.rescheduleCellIfNeeded(n)
                # Neighbor also has to update its next active cell 
                n._schedule_next_ActiveCell()
                          
            
            # remove scheduled cells if its destination is not a parent        
            for n in self.PDR.keys():        # for all neighbors
                if not self.trafficDistribution.has_key(n): 
                    remove = False
                    for (ts,cell) in self.schedule.items():
                        if cell['neighbor'] == n and cell['dir'] == self.TX:
                            remove = True
                            self._removeCellToNeighbor(ts,cell)
                    if remove == True: # if at least one cell is removed, then updade next active cell
                        n._schedule_next_ActiveCell()       
            
            # schedule next active cell
            # Note: this is needed in case the monitoring action modified the schedule
            self._schedule_next_ActiveCell()
                    
            # schedule next monitoring
            self._schedule_monitoring()
    
    def _schedule_monitoring(self, delay = HOUSEKEEPING_PERIOD):
        ''' tells to the simulator engine to add an event to monitor the network'''
        if delay == self.HOUSEKEEPING_PERIOD:
            self.engine.scheduleIn(
                delay     = delay*(0.9+0.2*random.random()),
                cb        = self._action_monitoring,
                uniqueTag = (self.id,'monitoring')
            )
        else:
            self.engine.scheduleIn(
                delay     = delay,
                cb        = self._action_monitoring,
                uniqueTag = (self.id,'monitoring')
            )
            
    
    def _addCellToNeighbor(self,neighbor):
        ''' tries to allocate a cell to a neighbor. It retries until it finds one available slot. '''
        with self.dataLock:
            found = False
            trial = 0
            while not found:
                candidateTimeslot      = random.randint(0,self.settings.timeslots-1)
                candidateChannel       = random.randint(0,self.settings.channels-1)
                
                if trial==10000:
                    print'try {0} times but cannot find a empty time slot for both nodes'.format(trial)
                    break
                trial += 1

                if (
                        self.isUnusedSlot(candidateTimeslot) and
                        neighbor.isUnusedSlot(candidateTimeslot)
                    ):
                    found = True
                    self.scheduleCell(
                        ts             = candidateTimeslot,
                        ch             = candidateChannel,
                        dir            = self.DIR_TX,
                        neighbor       = neighbor,
                    )
                    neighbor.scheduleCell(
                        ts             = candidateTimeslot,
                        ch             = candidateChannel,
                        dir            = self.DIR_RX,
                        neighbor       = self,
                    )
                    #print 'allocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}'.format(candidateTimeslot, candidateChannel, self.id, neighbor.id)
                    if neighbor not in self.numCells:
                        self.numCells[neighbor]    = 0
                    self.numCells[neighbor]  += 1
                    
                    #TODO count number or retries.
    
    def _removeCellToNeighbor(self,ts,cell):
        ''' removes a cell in the schedule of this node and the neighbor '''
        with self.dataLock:
            self.removeCell(
                 ts             = ts,
                 neighbor       = cell['neighbor'],
                 )
            cell['neighbor'].removeCell(
                 ts             = ts,
                 neighbor       = self,
                 )
            self.numCells[cell['neighbor']]  -= 1
                    #TODO count number or retries.    
    #======================== private =========================================
    
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
    
    def _resetStats(self):
        with self.dataLock:
            self.stats = {
                'dataGenerated':  0,
                'dataRecieved':  0,                
                'dataQueueOK':    0,
                'dataQueueFull':  0,
                'numCellsReallocated': 0,
            }
    
    def _incrementStats(self,name):
        with self.dataLock:
            self.stats[name] += 1
    
    def _resetIncomingTraffics(self):
        with self.dataLock:
            for neighbor in self.PDR.keys():
                self.incomingTraffics[neighbor] = 0

    def _incrementIncomingTraffics(self,neighbor):
        with self.dataLock:
            self.incomingTraffics[neighbor] += 1

    def _averageIncomingTraffics(self):
        with self.dataLock:
            for neighbor in self.PDR.keys():
                if self.averageIncomingTraffics.has_key(neighbor):
                    self.averageIncomingTraffics[neighbor] = self.SMOOTHING*self.incomingTraffics[neighbor] \
                    + (1-self.SMOOTHING)*self.averageIncomingTraffics[neighbor]
                elif self.incomingTraffics[neighbor] != 0:
                    self.averageIncomingTraffics[neighbor] = self.incomingTraffics[neighbor]
                    
        