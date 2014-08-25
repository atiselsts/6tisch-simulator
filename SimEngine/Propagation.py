#!/usr/bin/python
'''
\brief Wireless propagation model.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
'''

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Propagation')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

#============================ imports =========================================

import threading
import random
import math

import Topology

#============================ defines =========================================

#============================ body ============================================

class Propagation(object):
    
    #===== start singleton
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Propagation,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton
    
    def __init__(self):
        
        #===== start singleton
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        #===== end singleton
        
        # store params
        
        # variables
        self.dataLock                  = threading.Lock()
        self.receivers                 = [] # motes with radios currently on listening
        self.transmissions             = [] # ongoing transmissions
    
    def destroy(self):
        self._instance                 = None
        self._init                     = False
    
    #======================== public ==========================================
    
    #===== communication
    
    def startRx(self,mote,channel):
        ''' add a mote as listener on a channel'''
        with self.dataLock:
            self.receivers += [{
                'mote':                mote,
                'channel':             channel,
            }]
    
    def startTx(self,channel,type,smac,dmac,payload):
        ''' add a mote as using a ch. for tx'''
        with self.dataLock:
            self.transmissions  += [{
                'channel':             channel,
                'type':                type,
                'smac':                smac,
                'dmac':                dmac,
                'payload':             payload,
            }]
    
    def propagate(self):
        ''' Simulate the propagation of pkts in a slot. '''
        
        with self.dataLock:
            
            arrivalTime = {}
            # store arrival times of transmission packets 
            for transmission in self.transmissions:
                arrivalTime[transmission['smac']] = transmission['smac'].calcTime()
                        
            for transmission in self.transmissions:
                
                i           = 0
                isACKed     = False
                isNACKed    = False
                
                while i<len(self.receivers):
                    
                    if self.receivers[i]['channel']==transmission['channel']:
                        # this receiver is listening on the right channel
                        
                        if self.receivers[i]['mote']==transmission['dmac']:
                            # this packet is destined for this mote
                            
                            #''' ============= for evaluation with interference=================
                             
                            # other transmissions on the same channel?
                            interferers = [t['smac'] for t in self.transmissions if (t!=transmission) and (t['channel']==transmission['channel'])]
                            
                            lockOn = transmission['smac']
                            for itfr in interferers:
                                if arrivalTime[itfr] < arrivalTime[transmission['smac']] and transmission['dmac'].getRSSI(itfr)>transmission['dmac'].sensitivity:
                                    # lock on interference
                                    lockOn = itfr
                                    break
                            
                            if lockOn == transmission['smac']:
                                # calculate pdr, including interference
                                sinr  = self._computeSINR(transmission['smac'],transmission['dmac'],interferers)
                                pdr   = self._computePdrFromSINR(sinr, transmission['dmac'])
                            else:
                                # fail due to locking on interference
                                pdr   = 0.0
                            # ========================== '''
                            
                            ''' ============= for evaluation without interference=================
                            
                            interferers = []
                            # calculate pdr with no interference
                            sinr  = self._computeSINR(transmission['smac'],transmission['dmac'],interferers)
                            pdr   = self._computePdrFromSINR(sinr, transmission['dmac'])
                            ========================== ''' 
                            
                            # pick a random number
                            failure = random.random()
                            
                            if (pdr>=failure):
                                # packet is received correctly
                                
                                # this mote is delivered the packet
                                isACKed, isNACKed = self.receivers[i]['mote'].rxDone(
                                    type       = transmission['type'],
                                    smac       = transmission['smac'],
                                    dmac       = transmission['dmac'],
                                    payload    = transmission['payload']
                                )
                                
                                # this mote stops listening
                                del self.receivers[i]
                                
                            else:
                                # packet is NOT received correctly
                                
                                # move to the next receiver
                                i += 1
                            
                        else:
                            # this packet is NOT destined for this mote
                            
                            # move to the next receiver
                            i += 1
                    
                    else:
                        # this receiver is NOT listening on the right channel
                        
                        # move to the next receiver
                        i += 1
                
                # indicate to source packet was sent
                transmission['smac'].txDone(isACKed, isNACKed)
            
            # to all receivers still listening, indicate no packet received
            for r in self.receivers:
                r['mote'].rxDone()
            
            # clear all outstanding transmissions
            self.transmissions              = []
            self.receivers                  = []
    
    #======================== private =========================================
    
    def _computeSINR(self,source,destination,interferers):
        ''' compute SINR  '''
        
        noise = self._dBmTomW(destination.noisepower)
        # S = RSSI - N
        signal = self._dBmTomW(source.getRSSI(destination)) - noise
        if signal < 0.0:
            # RSSI has not to be below noise level. If this happens, return very low SINR (-10.0dB)
            return -10.0
        
        totalInterference = 0.0
        for interferer in interferers:
            # I = RSSI - N
            interference = self._dBmTomW(interferer.getRSSI(destination)) - noise
            if interference < 0.0:
                # RSSI has not to be below noise level. If this happens, set interference 0.0
                interference = 0.0
            totalInterference += interference
        
        sinr = signal/(totalInterference + noise)
        
        return self._mWTodBm(sinr)
    
    def _computePdrFromSINR(self, sinr, destination):
        ''' compute PDR from SINR  '''
        
        equivalentRSSI  = self._mWTodBm(
            self._dBmTomW(sinr+destination.noisepower) + self._dBmTomW(destination.noisepower)
        )
        
        pdr             = Topology.Topology.rssiToPdr(equivalentRSSI,destination.sensitivity)
        
        return pdr
    
    def _dBmTomW(self, dBm):
        ''' translate dBm to mW '''
        return math.pow(10.0, dBm/10.0)
    
    def _mWTodBm(self, mW):
        ''' translate dBm to mW '''
        return 10*math.log10(mW)
