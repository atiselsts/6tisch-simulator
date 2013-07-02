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
        self.collisions         = []
        self.numcollisions      = 0
    
    def startRx(self,mote,channel):
        ''' add a mote as listener on a channel'''
        with self.dataLock:
            self.receivers += [{
                'mote':          mote,
                'channel':       channel,
            }]
    
    def startTx(self,channel,type,smac,dmac,payload):
        ''' add a mote as using a ch. for tx'''
        
        
        with self.dataLock:
            collision = False
            remove = None
            #check that there is no transmission on that ch.
            for trans in self.transmissions:
                if trans['channel'] == channel:
                    collision= True
                    self.numcollisions = self.numcollisions + 1
                    #print "tx collision!"
                    if trans not in self.collisions:
                        #add it only once
                        self.collisions += [trans]
                        remove = trans #keep a pointer to the element colliding in transmission so it can be removed
                    #add the new tx into collision list
                    self.collisions += [{
                         'channel':        channel,
                         'type':           type,
                         'smac':           smac,
                         'dmac':           dmac,
                         'payload':        payload,
                          }] 
                    
            if not collision:
                self.transmissions  += [{
                    'channel':        channel,
                    'type':           type,
                    'smac':           smac,
                    'dmac':           dmac,
                    'payload':        payload,
                }]
            else:
                #remove the colliding element from the transmission list
                if remove != None:
                     self.transmissions.remove(remove)
                
    
    def propagate(self):
        ''' simulate the propagation of pkts in a slot.
            for each of the transmitters do:
            for all motes listening on a channel notify them (no propagation model yet). 
            Notify the rest with No packet so they can know that nothing happen in that slot. 
        '''
        
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
            
            for c in self.collisions:
                c['smac'].txDone(False)
                
            # clear all outstanding transmissions
            self.transmissions     = []
            self.receivers         = []
            self.collisions       = []
            self.numcollisions    = 0
