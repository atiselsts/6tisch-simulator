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
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

import threading
import random


class Propagation(object):
    
     #======================== singleton pattern ===============================
    _instance      = None
    _init          = False
    RADIO_SENSITIVITY = -101
    
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
        self.notransmissions     = []
        self.collisions          = []        
        self.rxFailures          = []
        self.numTxTrialcollisions = 0 # Tx trial in schedule collision cells         
        self.numPktcollisions     = 0 # Packet collision
        self.numAccumTxTrialcollisions = 0
        self.numAccumPktcollisions = 0
        
    def initStats(self):
        ''' initialize stats at each cycle'''
        with self.dataLock:
            self.numAccumTxTrialcollisions = 0
            self.numAccumPktcollisions = 0
         
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
            self.transmissions  += [{
                'channel':        channel,
                'type':           type,
                'smac':           smac,
                'dmac':           dmac,
                'payload':        payload,
                 }]
                    
    def noTx(self,channel,smac,dmac):
        ''' add a tx mote without data (for debug puropose) '''        
        with self.dataLock:
            
            self.notransmissions  += [{
                'channel':        channel,
                'smac':           smac,
                'dmac':           dmac,
            }]
    
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
                success = True # success in packet delivery
                scheduleCollision = False
                pktCollision = False

                num_receivers_ch = 0
                while i<len(self.receivers):
                    if self.receivers[i]['channel'] == transmission['channel']:
                        num_receivers_ch += 1
                         
                        #check this is a real link --
                        if self.receivers[i]['mote'].id == transmission['dmac'].id:
                            
                            # Check schedule collision and packet collision
                            for otherPacket in self.transmissions:
                                if (otherPacket != transmission) and (otherPacket['channel'] == transmission['channel']):                                    
                                    if scheduleCollision == False:
                                        # increase only 1 at each schedule collided transmission
                                        self.numTxTrialcollisions += 1
                                        scheduleCollision = True
                                    
                                    if otherPacket['smac'].getRSSI(transmission['dmac'].id) > self.RADIO_SENSITIVITY:
                                        if pktCollision == False:
                                            pktCollision = True
                                            success = False
                                            self.numPktcollisions += 1                                            
                                            self.rxFailures += [self.receivers[i]]
                                            del self.receivers[i]                                            
                                            self.collisions += [transmission] # store collided packet for debug purpose
                                            break

                            if pktCollision == False:                                                            
                                # test whether a packet can be delivered                                        
                                # pick a random number
                                failure = random.randint(0,100)
                                # get pdr to that neighbor
                                pdr = transmission['smac'].getPDR(transmission['dmac'])                                
                                # if we are lucky the packet is sent
                                if (pdr>=failure):
                                    success = True                                                
                                    log.debug("send with pdr {0},{1}".format(pdr,failure))
                                    self.receivers[i]['mote'].rxDone(
                                        type       = transmission['type'],
                                        smac       = transmission['smac'],
                                        dmac       = transmission['dmac'],
                                        payload    = transmission['payload']
                                    )
                                    del self.receivers[i]
                                else:
                                    success = False
                                    log.debug( "failed to send from {2},{3} due to pdr {0},{1}".format(pdr, failure, transmission['smac'].id, self.receivers[i]['mote'].id))  
                                    self.rxFailures += [self.receivers[i]]
                                    del self.receivers[i]                                         
                                    # increment of i does not needed because of del self.receivers[i] 
                        else: # different id                           
                            # not a neighbor, this is a listening terminal on that channel which is not neihbour -- this happens also when broadcasting
                            # TODO if we add broadcast, it will be processed here
                            i += 1  
                    
                    else: # different channel
                        i += 1
                
                # indicate to source packet was sent
                log.debug(" num listeners per transmitter {0}".format(num_receivers_ch))
                transmission['smac'].txDone(success)
            
            # indicate collision
            for r in self.rxFailures:
                r['mote'].rxDone(failure=True)

            # indicate no packet received
            for r in self.receivers:
                r['mote'].rxDone()
                        
            # update at each slot, clear at the end of slotframe
            self.numAccumTxTrialcollisions += self.numTxTrialcollisions
            self.numAccumPktcollisions += self.numPktcollisions
            
            # clear all outstanding transmissions
            self.transmissions     = []
            self.notransmissions   = []
            self.receivers         = []
            self.collisions        = []
            self.rxFailures        = []
            self.numPktcollisions  = 0
            self.numTxTrialcollisions = 0
            
