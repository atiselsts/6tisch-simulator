#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Mote')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import random
import threading

import SimEngine
import Propagation
import SimSettings

class Mote(object):
    
    HOUSEKEEPING_PERIOD      = 10
    
    DIR_TX                   = 'TX'
    DIR_RX                   = 'RX'
    
    DEBUG                    = 'DEBUG'
    WARNING                  = 'WARNING'
    
    def __init__(self,id):
        
        # store params
        self.id              = id
        
        # variables
        self.settings        = SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine()
        self.propagation     = Propagation.Propagation()
        self.dataLock        = threading.RLock()
        self.x               = random.random()
        self.y               = random.random()
        self.dataPeriod      = {}
        self.numCells        = {}
        self.booted          = False
        self.schedule        = {}
        self.txQueue         = []
    
    #======================== public =========================================
    
    def setDataEngine(self,neighbor,dataPeriod):
        with self.dataLock:
            self.dataPeriod[neighbor] = dataPeriod
            self._schedule_sendPk(neighbor)
    
    def boot(self):
        with self.dataLock:
            self.booted      = False
        
        # schedule first housekeeping
        self._schedule_housekeeping()
        
        # schedule first active cell
        self._schedule_next_ActiveCell()
    
    def getTxCells(self):
        with self.dataLock:
            return [(ts,c['ch'],c['neighbor']) for (ts,c) in self.schedule.items() if c['dir']==self.DIR_TX]
    
    def getLocation(self):
        with self.dataLock:
            return (self.x,self.y)
    
    # TODO: replace direct call by packets
    def isUnusedSlot(self,ts):
        with self.dataLock:
            return not (ts in self.schedule)
    
    # TODO: replace direct call by packets
    def scheduleCell(self,ts,ch,dir,neighbor):
        
        self._log(self.DEBUG,"scheduleCell ts={0} ch={1} dir={2} with {3}".format(ts,ch,dir,neighbor.id))
        
        with self.dataLock:
            assert ts not in self.schedule.keys()
            self.schedule[ts] = {
                'ch':        ch,
                'dir':       dir,
                'neighbor':  neighbor,
                'numTx':     0,
                'numTxAck':  0,
                'numRx':     0,
            }
    
    #======================== actions =========================================
    
    #===== activeCell
    
    def _action_activeCell(self):
        
        self._log(self.DEBUG,"_action_activeCell")
        
        # schedule next active cell
        self._schedule_next_ActiveCell()
    
    def _schedule_next_ActiveCell(self):
        
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        tsCurrent = asn%self.settings.timeslots
        
        # find closest active slot in schedule
        with self.dataLock:
            
            if not self.schedule:
                self._log(self.DEBUG,"empty schedule")
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
    
    #===== sendPk
    
    def _action_sendPk(self,neighbor):
        
        self._log(self.DEBUG,"_action_sendPk to {0}".format(neighbor.id))
        
        # schedule next _action_sendPk
        self._schedule_sendPk(neighbor)
    
    def _schedule_sendPk(self,neighbor):
        
        # cancel activity if neighbor disappeared from schedule
        if neighbor not in self.dataPeriod:
            return
        
        # compute random
        delay      = self.dataPeriod[neighbor]*(0.9+0.2*random.random())
        
        # create lambda function with destination
        cb         = lambda x=neighbor: self._action_sendPk(x)
        
        # schedule
        self.engine.scheduleIn(
            delay  = delay,
            cb     = cb,
        )
    
    #===== housekeeping
    
    def _action_housekeeping(self):
        
        self._log(self.DEBUG,"_action_housekeeping")
        
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
        
        # schedule next active cell
        # Note: this is needed in case the housekeeping action modified the schedule
        self._schedule_next_ActiveCell()
        
        # schedule next housekeeping
        self._schedule_housekeeping()
    
    def _schedule_housekeeping(self):
        self.engine.scheduleIn(
            delay  = self.HOUSEKEEPING_PERIOD*(0.9+0.2*random.random()),
            cb     = self._action_housekeeping,
        )
    
    def _addCellToNeighbor(self,neighbor):
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
    
    #======================== private =========================================
    
    def _log(self,severity,message):
        
        output  = []
        output += ['[ASN={0} id={1}] '.format(self.engine.getAsn(),self.id)]
        output += [message]
        output  = ''.join(output)
        
        if   severity==self.DEBUG:
            logfunc = log.debug
        elif severity==self.WARNING:
            logfunc = log.warning
        
        logfunc(output)
