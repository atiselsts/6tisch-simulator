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
        self.traffic         = {}
        self.numCells        = {}
        self.booted          = False
        self.schedule        = {}
        self.txQueue         = []
    
    #======================== public =========================================
    
    def setTrafficGoal(self,neighbor,traffic):
        with self.dataLock:
            self.traffic[neighbor] = traffic
    
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
        
        log.debug("[{0}] schedule ts={1} ch={2}".format(self.id,ts,ch))
        
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
    
    #===== sendPk
    
    def _action_activeCell(self,asn):
        
        log.debug("_action_activeCell@{0} ASN={1}".format(self.id,asn))
        
        # schedule next active cell
        self._schedule_next_ActiveCell()
    
    def _schedule_next_ActiveCell(self):
        
        asn = self.engine.getAsn()
        
        # get timeslotOffset of current asn
        tsCurrent = asn%self.settings.timeslots
        
        # find closest active slot in schedule
        with self.dataLock:
            
            if not self.schedule:
                log.warning("empty schedule")
                return
            
            tsDiffMin             = None
            for (ts,cell) in self.schedule.items():
                if   ts==tsCurrent:
                    pass
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
            asn    = asn+tsDiffMin,
            cb     = self._action_activeCell,
        )
    
    #====- housekeeping
    
    def _action_housekeeping(self,asn):
        
        log.debug("_action_housekeeping@{0} ASN={1}".format(self.id,asn))
        
        with self.dataLock:
            for (n,ppgoal) in self.traffic.items():
                while True:
                
                    # calculate the actual traffic
                    if self.numCells.get(n):
                        actualPkperiod  = (self.settings.timeslots*self.settings.slotDuration)/self.numCells[n]
                    else:
                        actualPkperiod  = None
                    
                    # schedule another cell if needed
                    if not actualPkperiod or actualPkperiod>ppgoal:
                        self._addCellToNeighbor(n)
                    else:
                        break
            
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
    
