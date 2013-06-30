#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Propagation')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import threading

class Propagation(object):
    
     #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Propagation,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        
        # variables
        self.dataLock            = threading.Lock()
        self.transmissions       = []
    
    def send(self,fromMote,toMote,packet):
        with self.dataLock:
            self.transmissions  += [(fromMote,toMote,packet)]
    
    def propagate(self):
        
        with self.dataLock:
            for (fromMote,toMote,packet) in self.transmissions:
                
                # indicate to destination is received a packet
                toMote.receiveIndication(fromMote,packet)
                
                # indicate to source transmission was successful
                fromMote.txDone(toMote,packet)
                
            # clear all outstanding transmissions
            self.transmissions    = []
