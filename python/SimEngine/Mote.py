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

import SimEngine
import Propagation
import SimSettings

class Mote(object):
    
    HOUSEKEEPING_PERIOD      = 1#10
    QUEUE_SIZE               = 10
    
    # sufficient num. of tx to estimate pdr by ACK
    NUM_SUFFICIENT_TX        = 10  
    
    # sufficient num. of DIO to determine parent is stable
    NUM_SUFFICIENT_DIO       = 1
    
    PARENT_SWITCH_THRESHOLD  = 768# corresponds to 1.5 hops. 6tisch minimal draft use 384 for 2*ETX. 
    MIN_HOP_RANK_INCREASE    = 256
    MAX_LINK_METRIC          = 4*MIN_HOP_RANK_INCREASE*2 # 4 transmissions allowed for one hop for parents
    MAX_PATH_COST            = 256*MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
    PARENT_SET_SIZE          = 3
    
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
        self.dataPeriod      = {}
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
        self.firstHousekeepinPeriod = 1.1 * self.settings.slotDuration*self.settings.timeslots 
        
        # set DIO period as 1 cycle of slotframe
        self.dioPeriod = self.settings.timeslots
        # number of received DIOs
        self.numRxDIO = {} #indexed by neighbor
        self.collectDIO = False
        self.reliableStats = False
        
        self._resetStats()
        
        # RPL initialization
        self.ranks           = {} #indexed by neighbor
        self.dagRanks        = {} #indexed by neighbor
        
        if self.id == 0: # mote with id 0 becomes a DAG root  
           self.dagRoot = True
           self.rank    = 0
           self.dagRank = 0
           self.parent  = self
        else:
           self.dagRoot = False
           self.rank    = None#100*self.MIN_HOP_RANK_INCREASE # Large value not to be chosen as a parent at the beginning
           self.dagRank = None#100
           self.parent  = None # preferred parent    
           self.parents = [] # set of parents
    
    #======================== public =========================================
    
    def setDataEngine(self,neighbor,dataPeriod):
        ''' sets the period to communicate with that neighbor '''
        with self.dataLock:
            self.dataPeriod[neighbor] = dataPeriod
            self._schedule_sendData(neighbor)

    def setDataEngineAll(self):
        ''' sets the period to communicate for all neighbors/parents '''
        with self.dataLock:
            
            # if statistics of all neighbors become reliable, set self.reliableStats = True
            if self.reliableStats == False:                                        
                self.reliableStats = True
                # if one of neighbors lacks sufficient num of Tx, self.reliableStats is set to False
                for (neighbor, _) in self.PDR.items():
                    numTx = 0
                    for (_,cell) in self.schedule.items():
                        if (cell['neighbor'] == neighbor) and (cell['dir'] == self.TX):
                            numTx += cell['numTx']
                    if numTx < self.NUM_SUFFICIENT_TX:
                        self.reliableStats = False
                        break
            
            # if DIO from all neighbors are collected, set self.collectDIO = True            
            if self.collectDIO == False:                
                self.collectDIO = True
                for (neighbor, _) in self.PDR.items():
                    if self.numRxDIO.has_key(neighbor):
                        if self.numRxDIO[neighbor] < self.NUM_SUFFICIENT_DIO:
                            self.collectDIO = False
                            break            
                    else:
                        self.collectDIO = False
                        break            
                        
            # at initial phase, sends data to all neighbors    
            if self.reliableStats == False or self.collectDIO == False:
                # divides data portion equally to all neighbors
                for (neighbor, _) in self.PDR.items():
                    portion = 1.0/len(self.PDR.items())
                    period = self.settings.traffic/portion                    
                    self.dataPeriod[neighbor] = period
                    self._schedule_sendData(neighbor)           
            
            # after statistics become reliable, sends data to parents   
            else:
                # divides data portion to parents in inverse ratio to DagRank
                sum = 0.0
                resultingRanks = {}
                for p in self.parents:
                    resultingRanks[p] = self.ranks[p] + self.computeRankIncrease(p)
                    sum += 1.0/resultingRanks[p]
                for p in self.parents:
                    portion = (1.0/resultingRanks[p])/sum
                    period = self.settings.traffic/portion                    
                    self.dataPeriod[p] = period           
                    self._schedule_sendData(p)
                for (neighbor, _) in self.PDR.items():
                    # remove sendData of neighbor which is not selected as a parent 
                    if neighbor not in self.parents and neighbor in self.dataPeriod.keys():
                        self.engine.removeEvent((self.id, neighbor.id,'sendData'))
                        del self.dataPeriod[neighbor]
                    
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
            numTx = 0
            numTxAck = 0
            for (_,cell) in self.schedule.items():
                if (cell['neighbor'] == neighbor) and (cell['dir'] == self.TX):
                    numTx += cell['numTx']
                    numTxAck += cell['numTxAck']
            
            # calculate ETX            
            if numTx >= self.NUM_SUFFICIENT_TX:
                if numTxAck > 0:
                    etx = float(numTx)/float(numTxAck)            
                else:
                    etx = float(numTx)/0.1 # to avoid division by zero
            else:
                # At the beginning, we set ETX = 1
                etx = 1
            # minimal 6tisch uses 2*ETX*MIN_HOP_RANK_INCREASE    
            return int(2 * self.MIN_HOP_RANK_INCREASE * etx)
        
    def selectNextHop(self):
        # select next hop to relay a packet based on the current traffic allotment
        with self.dataLock:
            portion = {}
            for neighbor in self.dataPeriod.keys():
                portion[neighbor] = self.settings.traffic/self.dataPeriod[neighbor]
            # summation of portions in dataPeriod should be 1.0
            # randomly select neighbor based on portion
            r = random.random()
            upper = 0.0
            for neighbor in portion.keys():
                upper += portion[neighbor]
                if r <= upper:
                    return neighbor
                
            
              
    
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
                
                for (neighbor, _) in self.PDR.items():
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
            
            if smac:
                self.schedule[ts]['numRx'] += 1
            if failure:
                self.schedule[ts]['numRxFailures'] += 1
                
                # TODO: relay packet?
            
            self.waitingFor = None
            
            if self.dagRoot == False and self.parent != None:
                # add to queue
                self._incrementStats('dataRelayed')
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
    
    def _action_sendData(self,neighbor):
        ''' actual send data function. Evaluates queue length too '''
        # log
        self._log(self.DEBUG,"_action_sendData to {0}".format(neighbor.id))
        
        # add to queue
        self._incrementStats('dataGenerated')
        if len(self.txQueue)<self.QUEUE_SIZE:
            self.txQueue += [{
                'asn':      self.engine.getAsn(),
                'nextHop':  neighbor,
                'type':     self.TYPE_DATA,
                'payload':  [],
            }]
            self._incrementStats('dataQueueOK')
        else:
            self._incrementStats('dataQueueFull')
        
        # schedule next _action_sendData
        #self._schedule_sendData(neighbor)
        
        # update data periods of destinations and schedule next _action_sendData
        self.setDataEngineAll()
    
    def _schedule_sendData(self,neighbor):
        ''' create an event that is inserted into the simulator engine to send the data according to the dataPeriod'''
        # cancel activity if neighbor disappeared from schedule
        if neighbor not in self.dataPeriod:
            return
        
        # compute random
        delay      = self.dataPeriod[neighbor]*(0.9+0.2*random.random())
        
        # create lambda function with destination
        cb         = lambda x=neighbor: self._action_sendData(x)
        
        # schedule
        self.engine.scheduleIn(
            delay     = delay,
            cb        = cb,
            uniqueTag = (self.id,neighbor.id,'sendData')
        )
    
    #===== monitoring
    

    def rescheduleCellIfNeeded(self, node):
        ''' finds the worst cell in each bundle. If the performance of the cell is bad compared to
            other cells in the bundle reschedule this cell. 
        '''
        bundle_avg = []
        worst_cell = (None, None, None)
        
        #look into all links that point to the node 
        for ts in self.schedule.keys():
            ce = self.schedule[ts]
            if ce['neighbor'] == node:

                #compute PDR to each node with sufficient num of tx
                if ce['numTx'] >= self.NUM_SUFFICIENT_TX:
                    if ce['numTxAck'] == 0:
                        pdr = float(1/float(ce['numTx'])) # set a small non-zero value when pkts are never ack
                    else:    
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
            diff = bce[2] / worst_cell[2] #compare pdr, maxCell pdr will be smaller than other cells so the ratio will
                                              # be bigger if worst_cell is very bad.     
            if diff > self.PDR_THRESHOLD:
                #reschedule the cell -- add to avoid scheduling the same
                print "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id)
                self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(worst_cell[0],worst_cell[1]['ch'],self.id,worst_cell[1]['neighbor'].id))
                self._addCellToNeighbor(worst_cell[1]['neighbor'])
                #and delete old one
                self._removeCellToNeighbor(worst_cell[0], worst_cell[1])
                # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                self.engine.removeEvent((self.id,'activeCell'))
                self.engine.removeEvent((worst_cell[1]['neighbor'].id,'activeCell'))
                self._incrementStats('numCellsReallocated')
                break;
            
    def _action_monitoring(self):
        ''' the monitoring action. allocates more cells if the objective is not met. '''
        self._log(self.DEBUG,"_action_monitoring")
                
        with self.dataLock:
            for (n,periodGoal) in self.dataPeriod.items():
                while True:
                
                    # calculate the actual dataPeriod
                    if self.numCells.get(n):
                        periodActual   = (self.settings.timeslots*self.settings.slotDuration)/self.numCells[n]
                    else:
                        periodActual   = None
                    
                    # schedule another cell if needed
                    if not periodActual or periodActual>periodGoal:
                        self._addCellToNeighbor(n)
                    else:
                        break
                #find worst cell in a bundle and if it is way worst and reschedule it
                self.rescheduleCellIfNeeded(n)
                # Neighbor also has to update its next active cell 
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
                delay  = delay*(0.9+0.2*random.random()),
                cb     = self._action_monitoring,
            )
        else:
            self.engine.scheduleIn(
                delay  = delay,
                cb     = self._action_monitoring,
            )
            
    
    def _addCellToNeighbor(self,neighbor):
        ''' tries to allocate a cell to a neighbor. It retries until it finds one available slot. '''
        with self.dataLock:
            found = False
            while not found:
                candidateTimeslot      = random.randint(0,self.settings.timeslots-1)
                candidateChannel       = random.randint(0,self.settings.channels-1)
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
                    print 'allocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}'.format(candidateTimeslot, candidateChannel, self.id, neighbor.id)
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
                'dataRelayed':  0,                
                'dataQueueOK':    0,
                'dataQueueFull':  0,
                'numCellsReallocated': 0,
            }
    
    def _incrementStats(self,name):
        with self.dataLock:
            self.stats[name] += 1
        