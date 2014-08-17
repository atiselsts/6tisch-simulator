#!/usr/bin/python
'''
\brief Wireless network topology creator.

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
log = logging.getLogger('Topology')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import random
import math

#============================ defines =========================================

#============================ body ============================================

class Topology(object):
    
    TWO_DOT_FOUR_GHZ         = 2400000000   # Hz
    PISTER_HACK_LOWER_SHIFT  = 40           # -40 dB
    SPEED_OF_LIGHT           = 299792458    # m/s
    
    MIN_RSSI                 = -93          # dBm, corresponds to PDR = 0.5
    
    def __init__(self, motes):
        
        # store params
        self.motes           = motes
    
    #======================== public ==========================================
    
    def createTopology(self):
        '''
        Create a topology in which all nodes have at least one path with enough
        RSSI to DAG root.
        If the mote does not have a link with enough RSSI, reset the location
        of the mote.
        '''
        
        # find DAG root
        dagRoot = None
        for mote in self.motes:
            if mote.dagRoot==True:
                dagRoot = mote
        assert dagRoot
        
        # reposition each mote until it is connected
        connectedMotes = [dagRoot]
        for mote in self.motes:
            if mote in connectedMotes:
                continue
            
            connected = False
            while not connected:
                # pick a random location
                mote.setLocation()
                
                # make sure it is connected to at least one mote
                for cm in connectedMotes:
                    
                    rssi = self._computeRSSI(mote, cm)
                    mote.setRSSI(cm, rssi)
                    cm.setRSSI(mote, rssi)
                    
                    if rssi>self.MIN_RSSI:
                        connected = True
            
            connectedMotes += [mote]
        
        # for each mote, compute PDR to each neighbors
        for mote in self.motes:
            for m in self.motes:
                if mote==m:
                    continue
                if mote.getRSSI(m)>mote.radioSensitivity:
                    pdr = self._computePDR(mote,m)
                    mote.setPDR(m,pdr)
                    m.setPDR(mote,pdr)
        
        # print topology information
        '''
        for mote in self.motes:
            for neighbor in self.motes:
                try:
                    distance = self._computeDistance(mote,neighbor)
                    rssi     = mote.getRSSI(neighbor)
                    pdr      = mote.getPDR(neighbor)
                except KeyError:
                    pass
                else:
                    print "mote = {0}, neighbor = {1:<3}, distance = {2:>4}m, rssi = {3:>4}dBm, pdr = {4:>3}%".format(
                        mote.id,
                        neighbor.id,
                        int(distance),
                        int(rssi),
                        int(pdr)
                    )
        '''
    
    #======================== private =========================================
    
    def _computeRSSI(self,mote,neighbor):
        ''' computes RSSI between any two nodes (not only neighbor) according to Pister hack model'''
        
        # distance in m
        distance = self._computeDistance(mote,neighbor)
        
        # sqrt and inverse of the free space path loss
        fspl = (self.SPEED_OF_LIGHT/(4*math.pi*distance*self.TWO_DOT_FOUR_GHZ))
        
        # simple friis equation in Pr=Pt+Gt+Gr+20log10(c/4piR)
        pr = mote.txPower + mote.antennaGain + neighbor.antennaGain + (20*math.log10(fspl))
        
        # according to the receiver power (RSSI) we can apply the Pister hack model.
        mu = pr-self.PISTER_HACK_LOWER_SHIFT/2 #chosing the "mean" value
    
        # the receiver will receive the packet with an rssi distributed in a gaussian between friis and friis -40
        #rssi=random.gauss(mu,self.PISTER_HACK_LOWER_SHIFT/2)
    
        # the receiver will receive the packet with an rssi uniformly distributed between friis and friis -40
        rssi = mu + random.uniform(-self.PISTER_HACK_LOWER_SHIFT/2, self.PISTER_HACK_LOWER_SHIFT/2)
        
        return rssi
    
    def _computePDR(self,mote,neighbor):
        ''' computes pdr to neighbor according to RSSI'''
        
        distance   = self._computeDistance(mote,neighbor)
        
        rssi       = mote.getRSSI(neighbor)
        if   rssi<=neighbor.radioSensitivity:
            pdr    = 0.0
        elif neighbor.radioSensitivity<rssi and rssi< -85:
            pdr    = (rssi-neighbor.radioSensitivity)*6.25
        elif rssi>-85:
            pdr    = 100.0
        
        return pdr
    
    def _computeDistance(self,mote,neighbor):
        
        return 1000*math.sqrt(
            (mote.x - neighbor.x)**2 +
            (mote.y - neighbor.y)**2
        )
