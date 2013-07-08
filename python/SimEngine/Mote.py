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
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import copy
import random
import threading

import SimEngine
import Propagation
import SimSettings

class Mote(object):
    
    HOUSEKEEPING_PERIOD      = 10
    
    QUEUE_SIZE               = 10
    
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
        
        # variables
        self.settings        = SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine()
        self.propagation     = Propagation.Propagation()
        self.dataLock        = threading.RLock()
        self.x               = random.random() # * 10^4 to represent meters
        self.y               = random.random() # * 10^4 to represent meters (this are cm so it can be plotted)
        self.waitingFor      = None
        self.radioChannel    = None
        self.dataPeriod      = {}
        self.PDR             = {} #indexed by neighbor
        self.numCells        = {}
        self.booted          = False
        self.schedule        = {}
        self.txQueue         = []
        self.tPower          = 0
        self.antennaGain     = 0
        self.radioSensitivity = -101
        
        self._resetStats()
    
    #======================== public =========================================
    
    def setDataEngine(self,neighbor,dataPeriod):
        ''' sets the period to communicate with that neighbor '''
        with self.dataLock:
            self.dataPeriod[neighbor] = dataPeriod
            self._schedule_sendData(neighbor)
    
    def setPDR(self,neighbor,pdr):
        ''' sets the pdr to that neighbor'''
        with self.dataLock:
            self.PDR[neighbor] = pdr
            
    def getPDR(self,neighbor):
        ''' returns the pdr to that neighbor'''
        with self.dataLock:
            return self.PDR[neighbor]
        
    
    def boot(self):
        ''' boots the mote '''
        with self.dataLock:
            self.booted      = False
        
        # schedule first monitoring
        self._schedule_monitoring()
        
        # schedule first active cell
        self._schedule_next_ActiveCell()
    
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
                        'numTxCollisions':  cell['numTxCollisions'],
                        'numRxCollisions':  cell['numRxCollisions'],
                    }
                    break
        return returnVal
    
    def getTxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_TX]
    
    def getRxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_RX]
    
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
                'numTxCollisions':    0,
                'numRxCollisions':    0,
            }
            
    def removeCell(self,ts,neighbor):
        ''' removes a cell from the schedule '''
        self._log(self.DEBUG,"removeCell ts={0} with {1}".format(ts,neighbor.id))
        with self.dataLock:
            assert ts in self.schedule.keys()
            assert neighbor == self.schedule[ts]['neighbor']
            del self.schedule[ts]
    #======================== actions =========================================
    
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
            
            if   cell['dir']==self.DIR_RX:
                
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
                self.schedule[ts]['numTxCollisions'] += 1    
            
            self.waitingFor = None
            
            # schedule next active cell
            self._schedule_next_ActiveCell()
    
    def rxDone(self,type=None,smac=None,dmac=None,payload=None,collision=False):
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
            if collision:
                self.schedule[ts]['numRxCollisions'] += 1
                
                # TODO: relay packet?
            
            self.waitingFor = None
            
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
                    tsDiff        = None
                elif ts>tsCurrent:
                    tsDiff        = ts-tsCurrent
                elif ts<tsCurrent:
                    tsDiff        = (ts+self.settings.timeslots)-tsCurrent
                else:
                    raise SystemError()
                
                if tsDiff and ((not tsDiffMin) or (tsDiffMin>tsDiff)):
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
        self._schedule_sendData(neighbor)
    
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
            delay  = delay,
            cb     = cb,
        )
    
    #===== monitoring
    

    def rescheduleCellIfNeeded(self, node):
        ''' finds the worst cell in each bundle. If the performance of the cell is bad compared to
            other cells in the bundle reschedule this cell. 
        '''
        bundle_avg = []
        max_cell = (None, None, None)
        #look into all links that point to the node 
        for ts in self.schedule.keys():
            ce = self.schedule[ts]
            if ce['neighbor'] == node:
                #compute PDR to each node
                pdr = float(1.5)
                if ce['numTx'] > 0 and ce['numTxAck'] > 0:
                    pdr =  float(ce['numTxAck']) / float(ce['numTx'])
                    
                elif (ce['numTx'] > 1 and ce['numTxAck'] == 0): 
                    pdr=float(1/float(ce['numTx'])) #detect when  pkts are never ack
                    
                if max_cell == (None,None,None):
                    max_cell = (ts, ce, pdr)
                #find worst cell in terms of number of collisions
                if max_cell[1]['numTxCollisions'] < ce['numTxCollisions']:
                    max_cell = (ts, ce, pdr)
                #this is part of a bundle of cells for that neighbor, keep
                #the tuple ts, schedule entry, pdr
                bundle_avg += [(ts, ce, pdr)]
        
        #compute the distance to the other cells in the bundle,
        #if the worst cell is far from any of the other cells reschedule it
        for bce in bundle_avg:
            if max_cell[2]==0.0:
                return
            
            diff = bce[2] / max_cell[2] #compare pdr, maxCell pdr will be smaller than other cells so the ratio will
                                        # be bigger if max_cell is very bad.
            if diff > self.PDR_THRESHOLD:
                #reschedule the cell -- add to avoid scheduling the same
                print "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(max_cell[0],max_cell[1]['ch'],self.id,max_cell[1]['neighbor'].id)
                self._log(self.DEBUG, "reallocating cell ts:{0},ch:{1},src_id:{2},dst_id:{3}".format(max_cell[0],max_cell[1]['ch'],self.id,max_cell[1]['neighbor'].id))
                self._addCellToNeighbor(max_cell[1]['neighbor'])
                #and delete old one
                self._removeCellToNeighbor(max_cell[0], max_cell[1])
                # it can happen that it was already scheduled an event to be executed at at that ts (both sides)
                self.engine.removeEvent((self.id,'activeCell'))
                self.engine.removeEvent((max_cell[1]['neighbor'].id,'activeCell'))
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
                          
        # schedule next active cell
        # Note: this is needed in case the monitoring action modified the schedule
        self._schedule_next_ActiveCell()
        
        # schedule next monitoring
        self._schedule_monitoring()
    
    def _schedule_monitoring(self):
        ''' tells to the simulator engine to add an event to monitor the network'''
        self.engine.scheduleIn(
            delay  = self.HOUSEKEEPING_PERIOD*(0.9+0.2*random.random()),
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
                'dataQueueOK':    0,
                'dataQueueFull':  0,
                'numCellsReallocated': 0,
            }
    
    def _incrementStats(self,name):
        with self.dataLock:
            self.stats[name] += 1
        