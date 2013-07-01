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
        self.receivers           = []
        self.transmissions       = []
    
    def startRx(self,mote,channel):
        with self.dataLock:
            self.receivers += [{
                'mote':          mote,
                'channel':       channel,
            }]
    
    def startTx(self,channel,type,smac,dmac,payload):
        with self.dataLock:
            self.transmissions  += [{
                'channel':        channel,
                'type':           type,
                'smac':           smac,
                'dmac':           dmac,
                'payload':        payload,
            }]
    
    def propagate(self):
        
        with self.dataLock:
            
            for transmission in self.transmissions:
                
                # find matching receivers
                i = 0
                while i<len(self.receivers):
                    if self.receivers[i]['channel']==['channel']:
                        self.receivers[i]['mote'].rxDone(
                            type       = transmission['type'],
                            smac       = transmission['smac'],
                            dmac       = transmission['dmac'],
                            payload    = transmission['payload']
                        )
                        del self.receivers[i]
                    else:
                        i   += 1
                
                # indicate to source packet was sent
                transmission['smac'].txDone(True)
            
            # indicate no packet received from remaining receivers
            for r in self.receivers:
                r['mote'].rxDone()
            
            # clear all outstanding transmissions
            self.transmissions     = []
            self.receivers         = []
