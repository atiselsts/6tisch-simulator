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
    
    SLOT_DURATION = 0.015
    
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
        self.delay           = 0
        self.motes           = [Mote.Mote(id) for id in range(s().numMotes)]
        self.goOn            = True
        
        # set the mote's pkperiod goals
        for i in range(len(self.motes)):
            self.motes[i].setPkperiodGoal(self.motes[random.randint(0,len(self.motes)-1)],s().pkperiod)
        
        # boot all the motes
        for i in range(len(self.motes)):
            self.motes[i].boot()
        
        # initialize parent class
        threading.Thread.__init__(self)
        self.name            = 'SimEngine'
        
        # start myself
        self.start()
    
    #======================== thread ==========================================
    
    def run(self):
        
        # log
        log.debug("thread {0} starting".format(self.name))
        
        while self.goOn:
            
            with self.dataLock: 
            
                if not self.events:
                    log.info("end of simulation at ASN={0}".format(self.asn))
                    break
                
                # get the next event to handle
                (asn,cbs) = self.events.pop(0)
                
                # update the current ASN
                self.asn = asn
                
                # call the callbacks
                for cb in cbs:
                    cb(self.asn)
                
                # tell the propagation engine to propagate
                self.propagation.propagate()
                
                # wait a bit
                time.sleep(self.delay)
        
        # log
        log.debug("thread {0} ends".format(self.name))
        log.debug("thread {0} ends".format(self.name))
    
    #======================== public ==========================================
    
    def scheduleIn(self,delay,cb):
        
        with self.dataLock:
            asn = int(self.asn+(float(delay)/float(s().slotDuration)))
            
            self.schedule(asn,cb)
    
    def schedule(self,asn,cb):
        
        with self.dataLock:
            
            assert asn>self.asn
            
            if not self.events:
                self.events.append((asn,[cb]))
                return
            
            for i in range(len(self.events)):
                if i>1:
                    previousAsn   = self.events[i-1][0]
                else:
                    previousAsn   = None
                thisAsn           = self.events[i][0]
                if i<len(self.events)-1:
                    nextAsn       = self.events[i+1][0]
                else:
                    nextAsn       = None
                if   thisAsn==asn:
                    # something already scheduled at this ASN, add this cb
                    self.events[i][1] += [cb]
                    return
                elif (
                    # between two already schedule ASNs
                    previousAsn        and
                    nextAsn            and
                    previousAsn<asn    and 
                    asn<nextAsn
                    ):
                    self.events.insert(i,[asn,[cb]])
                    return
                elif (
                    not previousAsn    and
                    asn<nextAsn
                    ):
                    # schedule at the beginning
                    self.events.insert(0,[asn,[cb]])
                    return
                elif (
                    not nextAsn        and
                    previousAsn<asn
                    ):
                    # schedule at the end
                    self.events.append([asn,[cb]])
                    return
            raise SystemError()
    
    def getAsn(self):
        with self.dataLock:
            return self.asn
    
    def setDelay(self,delay):
        with self.dataLock:
            self.delay = delay
    
    def getDelay(self):
        with self.dataLock:
            return self.delay
    
    def close(self):
        self.goOn = False
    
    #======================== private =========================================