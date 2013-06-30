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
from SimSettings import SimSettings as s

class Mote(object):
    
    HOUSEKEEPING_PERIOD      = 10
    
    DIR_TX                   = 'TX'
    DIR_RX                   = 'RX'
    
    def __init__(self,id):
        
        # store params
        self.id              = id
        
        # variables
        self.dataLock        = threading.RLock()
        self.x               = random.random()
        self.y               = random.random()
        self.pkperiod        = {}
        self.numCells        = {}
        self.booted          = False
        self.schedule        = []
        self.queue           = []
    
    #======================== public =========================================
    
    def setPkperiodGoal(self,neighbor,pkperiod):
        with self.dataLock:
            self.pkperiod[neighbor] = pkperiod
    
    def isUnusedCell(self,ts_p,ch_p):
        with self.dataLock:
            for (ts,ch,_,_) in self.schedule:
                if (ts,ch)==(ts_p,ch_p):
                    return False
            return True
    
    def scheduleCell(self,ts,ch,dir,neighbor):
        with self.dataLock:
            self.schedule += [(ts,ch,dir,neighbor)]
    
    def getTxCells(self):
        return [(ts,ch) for (ts,ch,dir,_) in self.schedule if dir==self.DIR_TX]
    
    def scheduleRandomCell(self,neighbor):
        with self.dataLock:
            found = False
            while not found:
                candidateTimeslot      = random.randint(0,s().timeslots-1)
                candidateChannel       = random.randint(0,s().channels-1)
                if (
                    neighbor.isUnusedCell(candidateTimeslot,candidateChannel) and
                    self.isUnusedCell(candidateTimeslot,candidateChannel)
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
    
    def boot(self):
        with self.dataLock:
            self.booted      = False
        
        # schedule first housekeeping
        self._schedule_housekeeping()
    
    def getPosition(self):
        with self.dataLock:
            return (self.x,self.y)
    
    #======================== private =========================================
    
    def _action_housekeeping(self,asn):
        log.debug("_action_housekeeping@{0} ASN={1}".format(self.id,asn))
        
        with self.dataLock:
            for (n,ppgoal) in self.pkperiod.items():
                while True:
                
                    # calculate the actual pkperiod
                    if self.numCells.get(n):
                        actualPkperiod  = (s().timeslots*s().slotDuration)/self.numCells[n]
                    else:
                        actualPkperiod  = None
                    
                    # schedule another cell if needed
                    if not actualPkperiod or actualPkperiod>ppgoal:
                        self.scheduleRandomCell(n)
                    else:
                        break
            
        # schedule next housekeeping
        self._schedule_housekeeping()
    
    def _schedule_housekeeping(self):
        SimEngine.SimEngine().scheduleIn(
            delay  = self.HOUSEKEEPING_PERIOD*(0.9+0.2*random.random()),
            cb     = self._action_housekeeping,
        )