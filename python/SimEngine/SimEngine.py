#!/usr/bin/python

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
import Mote
from SimSettings import SimSettings as s

class SimEngine(threading.Thread):
    
    SLOT_DURATION  = 0.015
    
    #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimEngine,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        
        # variables
        self.dataLock        = threading.RLock()
        self.propagation     = Propagation.Propagation()
        self.asn             = 0
        self.events          = []
        self.simDelay        = 0
        self.motes           = [Mote.Mote(id) for id in range(s().numMotes)]
        self.goOn            = True
        
        # set the mote's traffic goals
        for id in range(len(self.motes)):
            neighborId = None
            while (neighborId==None) or (neighborId==id):
                neighborId = random.randint(0,len(self.motes)-1)
            self.motes[id].setDataEngine(
                self.motes[neighborId],
                s().traffic,
            )
        
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
        
        # log
        log.info("thread {0} starting".format(self.name))
        
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
                assert self.events[0][0]>self.asn
                
                # update the current ASN
                self.asn = self.events[0][0]
                
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
        
        # log
        log.info("thread {0} ends".format(self.name))
    
    #======================== public ==========================================
    
    def scheduleIn(self,delay,cb):
        
        with self.dataLock:
            asn = int(self.asn+(float(delay)/float(s().slotDuration)))
            
            self.scheduleAtAsn(asn,cb)
    
    def scheduleAtAsn(self,asn,cb,uniqueTag=None):
        
        with self.dataLock:
            
            # make sure we are scheduling in the future
            assert asn>self.asn
            
            # remove all events with same uniqueTag
            if uniqueTag:
                i = 0
                while i<len(self.events):
                    (a,c,t) = self.events[i]
                    if t==uniqueTag:
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
    
    #======================== private =========================================