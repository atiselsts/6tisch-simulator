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
log = logging.getLogger('SimEngine')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import time
import threading
import random

import Propagation
import Topology
import Mote
from SimSettings import SimSettings as s

class SimEngine(threading.Thread):
    
    CYCLE_END = 300
    
    SLOT_DURATION  = 0.01
    OUTPUT_FILE = "output.dat"
    INIT_FILE = False
    count = 0  
    #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimEngine,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def setCount(cls):
        cls.count+=1

    def __init__(self):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        
        # variables
        self.dataLock        = threading.RLock()
        
        # initialize propagation at start of each run 
        Propagation.Propagation._instance = None
        Propagation.Propagation._init     = False        
        self.propagation     = Propagation.Propagation()
        
        self.asn             = 0
        self.events          = []
        self.simDelay        = 0
        self.motes           = []

        # initialize topology at start of each run         
        Topology.Topology._instance = None
        Topology.Topology._init     = False
        self.topology        = Topology.Topology()
        
        self.goOn            = True
        
        #use the topology component to create the network
        #TODO define topology configurations e.g tree, full mesh, etc.. so topology can build different nets   
        
        #self.motes=self.topology.createTopology(self.topology.RANDOM)
        #self.motes=self.topology.createTopology(self.topology.FULL_MESH)
        #self.motes=self.topology.createTopology(self.topology.RADIUS_DISTANCE)
        #self.motes=self.topology.createTopology(self.topology.MIN_DISTANCE)
        #self.motes=self.topology.createTopology(self.topology.MAX_RSSI)
        self.motes=self.topology.createTopology(self.topology.DODAG_TOPOLOGY)
        
        # boot all the motes
        for i in range(len(self.motes)):
            self.motes[i].boot()
        
        # initialize parent class
        threading.Thread.__init__(self)
        self.name            = 'SimEngine'
        
        # start thread
        self.start()
    
            
    #======================== thread ==========================================
    
    def run(self):
        ''' event driven simulator, this thread manages the events '''
        # log
        log.info("thread {0} starting".format(self.name))
        
        f = open(self.OUTPUT_FILE,'a')
        self.fileInit(f)
        
        startTime = time.time()
        
        while self.goOn:
            
            with self.dataLock: 
                
                '''
                output  = []
                output += ["events:"]
                for (asn,cb,uniqueTag) in self.events:
                    output += ["- asn={0} cb={1} uniqueTag={2}".format(asn,cb,uniqueTag)]
                output  = '\n'.join(output)
                log.debug(output)
                '''
                
                if not self.events:
                    log.info("end of simulation at ASN={0}".format(self.asn))
                    break
                
                # make sure we are in the future
                assert self.events[0][0] >= self.asn
                
                # initialize at start of each cycle
                if self.asn % s().timeslots == 0: 
                    numAccumScheduledCollisions = 0
                        
                # update the current ASN
                #self.asn = self.events[0][0]
                
                # call all the callbacks at this ASN
                while True:
                    if self.events[0][0]!=self.asn:
                        break
                    (_,cb,_) = self.events.pop(0)
                    cb()
                
                # tell the propagation engine to propagate
                self.propagation.propagate()
                
                # wait a bit
                time.sleep(self.simDelay)

                
                # Accumulate num of scheduled collision at each asn
                numAccumScheduledCollisions += self.countScheduleCollision()

                currentCycle = int(self.asn/s().timeslots)
                #nextCycle = int(self.events[0][0]/s().timeslots)
                #if currentCycle < nextCycle: # last event in current cycle
                if self.asn % s().timeslots == s().timeslots -1: # end of each cycle

                    print('Run num: {0} cycle: {1}'.format(self.count, currentCycle))
                    f.write('{0},{1},{2},{3},{4}\n'.format(self.count,
                                                   currentCycle,
                                                   self.propagation.numAccumTxTrialcollisions,
                                                   self.propagation.numAccumPktcollisions,
                                                   numAccumScheduledCollisions))
                    self.propagation.initStats() 
                
                
                                    
                # Terminate condition
                if currentCycle == self.CYCLE_END:
                    f.write('\n')
                    f.close()
                    self.goOn=False        
        
                
                # update the current ASN
                self.asn += 1        
        # log
        log.info("thread {0} ends".format(self.name))
    
    #======================== public ==========================================
    def removeEvent(self,uniqueTag):
        i = 0
        with self.dataLock:
            while i<len(self.events):
                (a,c,t) = self.events[i]
                if t==uniqueTag:
                    del self.events[i]
                else: #the list reduces its size when an element is deleted.
                     i += 1
                 
                
                
    def scheduleIn(self,delay,cb,uniqueTag=None):
        ''' used to generate events. Puts an event to the queue '''    
        with self.dataLock:
            asn = int(self.asn+(float(delay)/float(s().slotDuration)))
            
            self.scheduleAtAsn(asn,cb,uniqueTag)
    
    def scheduleAtAsn(self,asn,cb,uniqueTag=None):
        ''' schedule an event at specific ASN '''
        
        with self.dataLock:
            
            # make sure we are scheduling in the future
            assert asn>self.asn
            
            # remove all events with same uniqueTag
            if uniqueTag:
                i = 0
                while i<len(self.events):
                    (a,c,t) = self.events[i]
                    # remove the future event but do not remove events at the current asn  
                    if (t==uniqueTag) and (asn > self.asn):
                        del self.events[i]
                    else:
                        i += 1
            
            # find correct index in schedule
            i = 0
            found = False
            while found==False:
                if (i>=len(self.events) or self.events[i][0]>asn):
                    found = True
                else:
                    i += 1
            
            # add to schedule
            self.events.insert(i,(asn,cb,uniqueTag))
    
    def getAsn(self):
        with self.dataLock:
            return self.asn
    
    def setDelay(self,simDelay):
        with self.dataLock:
            self.simDelay = simDelay
    
    def getDelay(self):
        with self.dataLock:
            return self.simDelay
    
    def close(self):
        self.goOn = False
    
    def countScheduleCollision(self):
        # countScheduleCollision at current asn
        
        with self.dataLock:
            scheduledCells = set()
            collisionCells = set()
            currentTs = self.asn % s().timeslots
            for mote in self.motes:
                for (ts,ch,_) in mote.getTxCells():
                    if ts == currentTs:
                        if (ts,ch) not in scheduledCells:
                            scheduledCells.add((ts,ch))
                        else:
                            collisionCells.add((ts,ch))
            return len(collisionCells)
                
    
    def fileInit(self, file):
        if self.INIT_FILE == False:
            self.INIT_FILE = True
            file.write('# slotDuration = {0}\n'.format(s().slotDuration))        
            file.write('# numMotes = {0}\n'.format(s().numMotes))        
            file.write('# degree = {0}\n'.format(s().degree))        
            file.write('# channels = {0}\n'.format(s().channels))        
            file.write('# timeslots = {0}\n'.format(s().timeslots))        
            file.write('# traffic = {0}\n'.format(s().traffic))
            file.write('# side = {0}\n'.format(s().side))        
            file.write('# Run num, Cycle, Tx Trial in Collision, Packet Collision, Schedule Collision\n\n')
        
    #======================== private =========================================