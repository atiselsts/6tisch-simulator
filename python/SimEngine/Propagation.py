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
log = logging.getLogger('Propagation')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import threading
import random


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
        self.collisions          = []
        self.rxcollisions        = []
        self.numTxcollisions     = 0
        self.numRxcollisions     = 0
    
    def startRx(self,mote,channel):
        ''' add a mote as listener on a channel'''
        with self.dataLock:
            #note that we don't prevent collisions as we want to enable broadcast ch.        
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
                    self.numTxcollisions = self.numTxcollisions + 1
                    #print "tx collision! ch: {0} type: {1}, src mote id {2}, dest mote id {3}".format(channel,type,smac.id, dmac.id)
                    log.debug("tx collision! ch: {0} type: {1}, src mote id {2}, dest mote id {3}".format(channel,type,smac.id, dmac.id))
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
                success = True
                num_receivers_ch=0
                while i<len(self.receivers):
                    if self.receivers[i]['channel']==transmission['channel']:
                        num_receivers_ch+=1
                         
                        #check this is a real link --
                        if (transmission['dmac'].id==self.receivers[i]['mote'].id):
                            #pick a random number
                            failure = random.randint(0,100)
                            #get pdr to that neighbor
                            pdr = transmission['smac'].getPDR(self.receivers[i]['mote'])
                            #if we are lucky the packet is sent
                            if (pdr>failure):
                                log.debug("send with pdr {0},{1}".format(pdr,failure))
                                self.receivers[i]['mote'].rxDone(
                                    type       = transmission['type'],
                                    smac       = transmission['smac'],
                                    dmac       = transmission['dmac'],
                                    payload    = transmission['payload']
                                )
                                del self.receivers[i]
                                success=True
                            else:
                                success=False   
                                log.debug( "failed to send from {2},{3} due to pdr {0},{1}".format(pdr,failure,transmission['smac'].id,self.receivers[i]['mote'].id))
                                i   += 1   
                        else:
                            #not a neighbor, this is a listening terminal on that channel which is not neihbour -- this happens also when broadcasting
                            log.debug("rx collision {0},{1}, sender {2}".format(transmission['dmac'].id,self.receivers[i]['mote'].id,transmission['smac'].id))
                            self.numRxcollisions+=1
                            self.rxcollisions+=[self.receivers[i]] #add it to rx collisions
                            del self.receivers[i] 
                            #count as rx collision and notify failure.
                    else:
                        i   += 1
                
                # indicate to source packet was sent
                log.debug(" num listeners per transmitter {0}".format(num_receivers_ch))
                transmission['smac'].txDone(success)
            
            # indicate no packet received from remaining receivers
            for r in self.receivers:
                r['mote'].rxDone()
            
            for c in self.collisions:
                c['smac'].txDone(False)
            
            #notify rx collisions
            for c in self.rxcollisions:
                c['mote'].rxDone(collision=True)
            # clear all outstanding transmissions
            self.transmissions     = []
            self.receivers         = []
            self.collisions        = []
            self.rxcollisions      = []
            self.numTxcollisions   = 0
            self.numRxcollisions   = 0
