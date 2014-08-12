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
import math

#import SimEngine

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
        
        # for schedule collision cells
        self.numPktAtSC                = 0 
        self.numNoPktAtSC              = 0 # No Packet at schedule collision cells
        self.numSuccessAtSC            = 0
        
        # for schedule collision free cells
        self.numPktAtNSC               = 0 # packets at non schedule collision cells
        self.numNoPktAtNSC             = 0 # no packets at non schedule collision cells
        self.numSuccessAtNSC           = 0 # success transmissions at both NSC and SC 
        
        self.numAccumPktAtSC           = 0
        self.numAccumNoPktAtSC         = 0 
        self.numAccumSuccessAtSC       = 0
         
        self.numAccumPktAtNSC          = 0 
        self.numAccumNoPktAtNSC        = 0 
        self.numAccumSuccessAtNSC      = 0
        
        # for debug
        # self.engine          = SimEngine.SimEngine()
        
    def initStats(self):
        ''' initialize stats at each cycle'''
        with self.dataLock:

            self.numAccumPktAtSC           = 0
            self.numAccumNoPktAtSC         = 0 
            self.numAccumSuccessAtSC       = 0
             
            self.numAccumPktAtNSC          = 0 
            self.numAccumNoPktAtNSC        = 0 
            self.numAccumSuccessAtNSC      = 0

            
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

    def dBmTomW(self, dBm):
        ''' translate dBm to mW '''        
        return math.pow(10.0, dBm/10.0)

    def mWTodBm(self, mW):
        ''' translate dBm to mW '''        
        return 10*math.log10(mW)

    def computeSINR(self, smac, dmac, interferers):
        ''' compute SINR  '''        
        noise = self.dBmTomW(dmac.noisepower)
        # S = RSSI - N
        signal = self.dBmTomW(smac.getRSSI(dmac.id)) - noise
        if signal < 0.0:
            # RSSI has not to be below noise level. If this happens, return very low SINR (-10.0dB) 
            return -10.0
        
        totalInterference = 0.0
        for interferer in interferers:
            # I = RSSI - N
            interference = self.dBmTomW(interferer.getRSSI(dmac.id)) - noise
            if interference < 0.0:
                # RSSI has not to be below noise level. If this happens, set interference 0.0 
                interference = 0.0
            totalInterference += interference
        
        sinr = signal/(totalInterference + noise)
        
        return self.mWTodBm(sinr)
            
    def computePdrFromSINR(self, sinr, dmac):
        ''' compute PDR from SINR  '''        

        # equivalent RSSI means RSSI which has same SNR as input SINR
        equivalentRSSI = self.mWTodBm(self.dBmTomW(sinr + dmac.noisepower) + self.dBmTomW(dmac.noisepower))
            
        # TODO these values are tentative. Need to check datasheet for RSSI vs PDR relationship. 
        if equivalentRSSI < -85 and equivalentRSSI > dmac.radioSensitivity:
            pdr=(equivalentRSSI - dmac.radioSensitivity)*6.25
        elif equivalentRSSI <= dmac.radioSensitivity:
            pdr=0.0
        elif equivalentRSSI > -85:
            pdr=100.0
            
        return pdr 
            
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
                scheduleCollision = False
                
                num_receivers_ch = 0
                while i<len(self.receivers):
                    if self.receivers[i]['channel'] == transmission['channel']:
                        num_receivers_ch += 1
                         
                        #check this is a real link --
                        if self.receivers[i]['mote'].id == transmission['dmac'].id:
                            
                            # Check schedule collision and concurrent transmission 
                            interferers = []
                            for otherPacket in self.transmissions:
                                if (otherPacket != transmission) and (otherPacket['channel'] == transmission['channel']):                                    
                                    if scheduleCollision == False:
                                        scheduleCollision = True
                                        scheduleCollisionChs.add(transmission['channel'])
                                    interferers.append(otherPacket['smac'])

                            # Check schedule collision between Tx and no Tx
                            if scheduleCollision == False: 
                                for noTx in self.notransmissions:
                                    if noTx['channel'] == transmission['channel']:
                                        scheduleCollision = True
                                        scheduleCollisionChs.add(transmission['channel'])
                                        break
                            
                            if scheduleCollision == False:
                                self.numPktAtNSC += 1
                            else:
                                self.numPktAtSC += 1
                                
                                
                            # test whether a packet can be delivered   
                            # get SINR to that neighbor and translate it to PDR
                            sinr = self.computeSINR(transmission['smac'], transmission['dmac'], interferers)
                            pdr = self.computePdrFromSINR(sinr, transmission['dmac'])
                            pdr_debug = transmission['smac'].getPDR(transmission['dmac'])                                

                            # pick a random number
                            failure = random.randint(0,100)

                            # if we are lucky the packet is sent
                            if (pdr>=failure):
                                success = True
                                if scheduleCollision == True:
                                    self.numSuccessAtSC += 1
                                else:
                                    self.numSuccessAtNSC += 1

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
            
            # indicate packet error
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
            
            self.numAccumPktAtSC           += self.numPktAtSC
            self.numAccumNoPktAtSC         += self.numNoPktAtSC 
            self.numAccumSuccessAtSC       += self.numSuccessAtSC
             
            self.numAccumPktAtNSC          += self.numPktAtNSC 
            self.numAccumNoPktAtNSC        += self.numNoPktAtNSC 
            self.numAccumSuccessAtNSC      += self.numSuccessAtNSC

            # clear all outstanding transmissions
            self.transmissions      = []
            self.notransmissions    = []
            self.receivers          = []
            self.collisions         = []
            self.rxFailures         = []

            self.numPktAtSC                = 0
            self.numNoPktAtSC              = 0
            self.numSuccessAtSC            = 0
    
            self.numPktAtNSC               = 0
            self.numNoPktAtNSC             = 0
            self.numSuccessAtNSC           = 0

