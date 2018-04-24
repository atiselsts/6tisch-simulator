"""
Called by TSCH, links with propagation model.

Also accounts for charge consumed.
"""

# =========================== imports =========================================

import random
import threading
import copy

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('radio')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Radio(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote
        
        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.propagation                    = SimEngine.Propagation.Propagation()
        
        # local variables
        self.onGoingBroadcast               = None
        self.txPower                        = 0       # dBm
        self.antennaGain                    = 0       # dBi
        self.noisepower                     = -105    # dBm

    #======================== public ==========================================
    
    # TX
    
    def startTx(self, channel, type, code, smac, dmac, srcIp, dstIp, srcRoute, payload):
        
        assert self.onGoingBroadcast==None
        
        # send to propagation model
        self.propagation.startTx(
            channel   = channel,
            type      = type,
            code      = code,
            smac      = smac,
            dmac      = dmac,
            srcIp     = srcIp,
            dstIp     = dstIp,
            srcRoute  = srcRoute,
            payload   = payload,
        )
        
        # remember whether frame is broadcast
        self.onGoingBroadcast = (dmac==d.BROADCAST_ADDRESS)
    
    def txDone(self, isACKed, isNACKed):
        """end of tx slot"""
        
        assert self.onGoingBroadcast in [True,False]
        
        # log charge consumed
        if   isACKed or isNACKed:
            # ACK of NACK received (both consume same amount of charge)
            self.mote._logChargeConsumed(d.CHARGE_TxDataRxAck_uC)
        elif self.onGoingBroadcast:
            # no ACK expected (link-layer bcast)
            self.mote._logChargeConsumed(d.CHARGE_TxData_uC)
        else:
            # ACK expected, but not received
            self.mote._logChargeConsumed(d.CHARGE_TxDataRxAckNone_uC)
        
        # nothing ongoing anymore
        self.onGoingBroadcast = None
        
        # inform upper layer (TSCH)
        self.mote.tsch.txDone(  isACKed, isNACKed)
    
    # RX
    
    def startRx(self,channel):
        
        # send to propagation model
        self.propagation.startRx(
            mote          = self.mote,
            channel       = channel,
        )
    
    def rxDone(self,      type=None, code=None, smac=None, dmac=None, srcIp=None, dstIp=None, srcRoute=None, payload=None):
        """end of RX radio activity"""
        
        # log charge consumed
        if type==None:
            # didn't receive any frame (idle listen)
            self.mote._logChargeConsumed(d.CHARGE_Idle_uC)
        elif dmac == [self.mote]:
            # unicast frame for me, I sent an ACK
            self.mote._logChargeConsumed(d.CHARGE_RxDataTxAck_uC)
        else:
            # either not for me, or broadcast. In any case, I didn't send an ACK
            self.mote._logChargeConsumed(d.CHARGE_RxData_uC)
        
        # inform upper layer (TSCH)
        return self.mote.tsch.rxDone(type, code, smac, dmac, srcIp, dstIp, srcRoute, payload)
    
    # dropping
    
    def drop_packet(self, pkt, reason):
        # remove all the element of pkt so that it won't be processed further
        for k in pkt.keys():
            del pkt[k]

        # increment mote stat
        self.mote._stats_incrementMoteStats(reason)
