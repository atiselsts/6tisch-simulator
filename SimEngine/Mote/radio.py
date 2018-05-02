"""
Called by TSCH, links with propagation model.

Also accounts for charge consumed.
"""

# =========================== imports =========================================

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

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
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self.onGoingBroadcast               = None
        self.onGoingTransmission            = None    # ongoing transmission (used by propagate)
        self.txPower                        = 0       # dBm
        self.antennaGain                    = 0       # dBi
        self.noisepower                     = -105    # dBm
        self.state                          = d.RADIO_STATE_IDLE  # idle, tx or rx
        self.channel                        = None

    # ======================= public ==========================================

    # TX

    def startTx(self, channel, packet):
        
        assert self.onGoingBroadcast    is None
        assert self.onGoingTransmission is None
        assert set(['type','mac']).issubset(set(packet.keys()))

        # record the state of the radio
        self.state   = d.RADIO_STATE_TX
        self.channel = channel
        
        # record ongoing, for propagation model
        self.onGoingTransmission = {
            'channel': channel,
            'packet':  packet,
        }

        # remember whether frame is broadcast
        self.onGoingBroadcast = (packet['mac']['dstMac']==d.BROADCAST_ADDRESS)

    def txDone(self, isACKed):
        """end of tx slot"""
        self.state = d.RADIO_STATE_IDLE
        self.channel = None

        assert self.onGoingBroadcast in [True, False]
        assert self.onGoingTransmission

        # log charge consumed
        if   isACKed:
            # ACK received
            self.mote.batt.logChargeConsumed(d.CHARGE_TxDataRxAck_uC)
        elif self.onGoingBroadcast:
            # no ACK expected (link-layer bcast)
            self.mote.batt.logChargeConsumed(d.CHARGE_TxData_uC)
        else:
            # ACK expected, but not received
            self.mote.batt.logChargeConsumed(d.CHARGE_TxDataRxAckNone_uC)

        # nothing ongoing anymore
        self.onGoingBroadcast = None
        self.onGoingTransmission = None

        # inform upper layer (TSCH)
        self.mote.tsch.txDone(isACKed)

    # RX

    def startRx(self, channel):
        self.state = d.RADIO_STATE_RX
        self.channel = channel

    def rxDone(self, packet):
        """end of RX radio activity"""
        
        # switch radio state
        self.state   = d.RADIO_STATE_IDLE
        self.channel = None

        # log charge consumed
        if not packet:
            # didn't receive any frame (idle listen)
            self.mote.batt.logChargeConsumed(d.CHARGE_Idle_uC)
        elif packet['mac']['dstMac'] == self.mote.id:
            # unicast frame for me, I sent an ACK
            self.mote.batt.logChargeConsumed(d.CHARGE_RxDataTxAck_uC)
        else:
            # either not for me, or broadcast. In any case, I didn't send an ACK
            self.mote.batt.logChargeConsumed(d.CHARGE_RxData_uC)

        # inform upper layer (TSCH)
        return self.mote.tsch.rxDone(packet)

    # dropping

    def drop_packet(self, pkt, reason):
        
        # log
        self.log(
            SimEngine.SimLog.LOG_RADIO_PKT_DROPPED,
            {
                "_mote_id":  self.mote.id,
                "type":      pkt['type'],
                "reason":    reason,
            }
        )
        
        # remove all the element of pkt so that it won't be processed further
        for k in pkt.keys():
            del pkt[k]
