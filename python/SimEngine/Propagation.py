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

import SimEngine

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
        
        self.numPktCollisions          = 0 # Packet collision at schedule collision cells
        self.numNoPktCollisions        = 0 # No Packet collision at schedule collision cells
        self.numNoPktAtSC              = 0 # No Packet at schedule collision cells

        self.numPktAtNSC               = 0 # packets at non schedule collision cells
        self.numNoPktAtNSC             = 0 # no packets at non schedule collision cells
        self.numSuccess                = 0 # success transmissions at both NSC and SC 
        
        self.numAccumPktCollisions     = 0
        self.numAccumNoPktCollisions   = 0 
        self.numAccumNoPktAtSC         = 0 

        self.numAccumPktAtNSC          = 0 
        self.numAccumNoPktAtNSC        = 0 
        self.numAccumSuccess           = 0
        
        # for debug
        self.engine          = SimEngine.SimEngine()
        
    def initStats(self):
        ''' initialize stats at each cycle'''
        with self.dataLock:
            self.numAccumPktCollisions     = 0
            self.numAccumNoPktCollisions   = 0 
            self.numAccumNoPktAtSC         = 0
            self.numAccumPktAtNSC          = 0 
            self.numAccumNoPktAtNSC        = 0
            self.numAccumSuccess           = 0


            
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
        ''' add a tx mote without data (for debug purpose) '''        
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
            
            scheduleCollisionChs = set()
            
            for transmission in self.transmissions:
                
                # find matching receivers
                i = 0
                success = True # success in packet delivery
                pktCollision = False
                scheduleCollision = False
                
                num_receivers_ch = 0
                while i<len(self.receivers):
                    if self.receivers[i]['channel'] == transmission['channel']:
                        num_receivers_ch += 1
                         
                        #check this is a real link --
                        if self.receivers[i]['mote'].id == transmission['dmac'].id:
                            
                            # Check packet collision and schedule collision with other packets
                            for otherPacket in self.transmissions:
                                if (otherPacket != transmission) and (otherPacket['channel'] == transmission['channel']):                                    
                                    if scheduleCollision == False:
                                        scheduleCollision = True
                                        scheduleCollisionChs.add(transmission['channel'])
                                    
                                    if otherPacket['smac'].getRSSI(transmission['dmac'].id) > self.RADIO_SENSITIVITY:
                                        if pktCollision == False:
                                            pktCollision = True
                                            success = False
                                            self.rxFailures += [self.receivers[i]]
                                            del self.receivers[i]                                            
                                            self.collisions += [transmission] # store collided packet for debug purpose
                                            break

                            # Check schedule collision between Tx and no Tx
                            if scheduleCollision == False: 
                                for noTx in self.notransmissions:
                                    if noTx['channel'] == transmission['channel']:
                                        scheduleCollision = True
                                        scheduleCollisionChs.add(transmission['channel'])
                                        break
                            
                            if scheduleCollision == False:
                                self.numPktAtNSC += 1

                            if scheduleCollision == True and pktCollision == True:
                                self.numPktCollisions += 1
                            
                            if scheduleCollision == True and pktCollision == False:
                                self.numNoPktCollisions += 1
                            
                            # test whether a packet can be delivered   
                            if pktCollision == False:                                                                                                                                
                                # pick a random number
                                failure = random.randint(0,100)
                                # get pdr to that neighbor
                                pdr = transmission['smac'].getPDR(transmission['dmac'])                                
                                # if we are lucky the packet is sent
                                if (pdr>=failure):
                                    success = True
                                    self.numSuccess += 1                                                
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
            
            # check schedule collision between no Txs and store channel
            for n in self.notransmissions:
                for otherNoTx in self.notransmissions:
                    if (otherNoTx != n) and (otherNoTx['channel'] == n['channel']):
                        scheduleCollisionChs.add(n['channel'])       
            
            # count no packets at both SC and NSC
            for n in self.notransmissions:
                if n['channel'] in scheduleCollisionChs:            
                    self.numNoPktAtSC  += 1
                else:
                    self.numNoPktAtNSC += 1                                                            

            
            # update at each slot, clear at the end of slotframe
            self.numAccumPktCollisions     += self.numPktCollisions
            self.numAccumNoPktCollisions   += self.numNoPktCollisions 
            self.numAccumNoPktAtSC         += self.numNoPktAtSC
            self.numAccumPktAtNSC          += self.numPktAtNSC
            self.numAccumNoPktAtNSC        += self.numNoPktAtNSC
            self.numAccumSuccess           += self.numSuccess
            
            # clear all outstanding transmissions
            self.transmissions      = []
            self.notransmissions    = []
            self.receivers          = []
            self.collisions         = []
            self.rxFailures         = []
            self.numPktCollisions   = 0
            self.numNoPktCollisions = 0
            self.numNoPktAtSC       = 0
            self.numPktAtNSC        = 0
            self.numNoPktAtNSC      = 0
            self.numSuccess         = 0
            
