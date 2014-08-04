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
    
    CYCLE_END = 100
    
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
        
        self.scheduledCells = set()
        self.collisionCells = set()
        self.inactivatedCells = set()

        self.numAccumScheduledCells = 0        
        self.numAccumScheduledCollisions = 0
        
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
        #update other topology configurations e.g tree, full mesh, etc.. so topology can build different nets   
        self.motes = self.topology.createTopology(self.topology.CONNECTED)
        
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
                
                if not self.events:
                    log.info("end of simulation at ASN={0}".format(self.asn))
                    break
                
                # make sure we are in the future
                assert self.events[0][0] >= self.asn

                # call callbacks at this ASN other than monitoring
                i = 0
                while True:
                    if self.events[i][0] != self.asn:
                        break
                    # last element in tuple of uniqueTag is 'monitoring'/'sendData'/'DIO'/activeCell'
                    if self.events[i][2][-1] != 'monitoring':
                        (_,cb,_) = self.events.pop(i)
                        cb()
                    else:
                        i += 1
                    
                # count scheduled cells and schedule collisions after 'activeCell' called
                self.countSchedule()
                                
                # tell the propagation engine to propagate
                self.propagation.propagate()

                # call remained callbacks (i.e. monitoring) 
                while True:                    
                    if self.events[0][0]!=self.asn:
                        break
                    (_,cb,_) = self.events.pop(0)
                    cb()
                                    
                # wait a bit
                time.sleep(self.simDelay)

                cycle = int(self.asn/s().timeslots)
                if self.asn % s().timeslots == s().timeslots -1: # end of each cycle
                    if cycle == 0:
                        f.write('# run\tcycle\tsched.\tno SC\tno pkt\tpkt\tSC\tno pkt\tPC\tno PC\tsuccess\tgen pkt\treach\tqueue\toverflow\te2e PDR\n\n')
                    print('Run num: {0} cycle: {1}'.format(self.count, cycle))
                    
                    numGeneratedPkts  = self.countGeneratedPackets()
                    numPacketsInQueue = self.countPacketsInQueue()
                    numOverflow = self.countQueueFull()
                    numPacketsReached = self.motes[0].getStats()['dataRecieved']
                    if numGeneratedPkts-numPacketsInQueue > 0:
                        e2ePDR = float(numPacketsReached)/float(numGeneratedPkts-numPacketsInQueue)
                    else:
                        e2ePDR = 0.0
                    
                    f.write('{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}\t{8}\t{9}\t{10}\t{11}\t{12}\t{13}\t{14}\t{15}\n'.format(
                                                               self.count, #0
                                                               cycle, #1
                                                               self.numAccumScheduledCells, #2
                                                               self.numAccumScheduledCells - self.numAccumScheduledCollisions, #3
                                                               self.propagation.numAccumNoPktAtNSC, #4
                                                               self.propagation.numAccumPktAtNSC, #5
                                                               self.numAccumScheduledCollisions, #6                                                               
                                                               self.propagation.numAccumNoPktAtSC, #7
                                                               self.propagation.numAccumPktCollisions, #8
                                                               self.propagation.numAccumNoPktCollisions, #9
                                                               self.propagation.numAccumSuccess, #10
                                                               numGeneratedPkts, #11
                                                               numPacketsReached,#12
                                                               numPacketsInQueue,#13
                                                               numOverflow,#14
                                                               round(e2ePDR,3) #15
                                                               ))
                    self.propagation.initStats() 
                
                
                                    
                # Terminate condition
                if cycle == self.CYCLE_END:
                    f.write('\n')
                    f.close()
                    self.goOn=False        
        
                
                # update the current ASN
                self.asn += 1        
        # log
        log.info("thread {0} ends".format(self.name))
    
    #======================== public ==========================================
    def removeEvent(self,uniqueTag,exceptCurrentASN=False):
        i = 0
        with self.dataLock:
            while i<len(self.events):
                (a,c,t) = self.events[i]
                if not exceptCurrentASN:
                    if t==uniqueTag:
                        del self.events[i]
                    else: #the list reduces its size when an element is deleted.
                         i += 1
                else: # events at current asn are not removed 
                    if t==uniqueTag and a > self.asn:
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
                    if (t==uniqueTag) and (a > self.asn):
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
    
    def countSchedule(self):
        # count scheduled cells and schedule collision at each asn
        
        with self.dataLock:
            
            # initialize at start of each cycle
            currentTs = self.asn % s().timeslots
            if currentTs == 0: 
                self.numAccumScheduledCells = 0        
                self.numAccumScheduledCollisions = 0

            self.scheduledCells.clear()
            self.collisionCells.clear()
            self.inactivatedCells.clear() # store cells recently added by monitoring function but not activated yet 
            for mote in self.motes:                
                for (ts,ch,_) in mote.getTxCells():
                    if ts == currentTs:
                                                
                        activated = False
                        # check whether this cell is already activated
                        for tx in self.propagation.transmissions:
                            if tx['smac'] == mote:
                                activated = True
                                break
                        for no in self.propagation.notransmissions:
                            if no['smac'] == mote:
                                activated = True
                                break
                        
                        if not activated:
                            self.inactivatedCells.add((ts,ch))
                        elif (ts,ch) not in self.scheduledCells:
                            self.scheduledCells.add((ts,ch))
                        else:
                            self.collisionCells.add((ts,ch))

            self.numAccumScheduledCells += len(self.scheduledCells)
            self.numAccumScheduledCollisions += len(self.collisionCells)
                
    def countPacketsInQueue(self):
        # count the number of packets in queues of all motes at current asn
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                numPkt += len(mote.txQueue)
            return numPkt
    
    def countGeneratedPackets(self):
        # count the number of generated packets of all motes
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                stats = mote.getStats()
                numPkt += stats['dataGenerated']
            return numPkt

    def countQueueFull(self):
        # count the number of generated packets of all motes
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                stats = mote.getStats()
                numPkt += stats['dataQueueFull']
            return numPkt
   
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
            file.write('# SC = Schedule Collision, PC = Packet Collision\n')        
            
        
    #======================== private =========================================