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

        # singletons (quicker access, instead of recreating every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self.onGoingTransmission            = None    # ongoing transmission (used by propagate)
        self.txPower                        = 0       # dBm
        self.antennaGain                    = 0       # dBi
        self.noisepower                     = -105    # dBm
        self.state                          = d.RADIO_STATE_OFF
        self.channel                        = None

    # ======================= public ==========================================

    # TX

    def startTx(self, channel, packet):

        assert self.onGoingTransmission is None
        assert 'type' in packet
        assert 'mac'  in packet

        # record the state of the radio
        self.state   = d.RADIO_STATE_TX
        self.channel = channel

        # record ongoing, for propagation model
        self.onGoingTransmission = {
            'channel': channel,
            'packet':  packet,
        }

    def txDone(self, isACKed):
        """end of tx slot"""
        self.state = d.RADIO_STATE_OFF

        assert self.onGoingTransmission

        onGoingBroadcast = (self.onGoingTransmission['packet']['mac']['dstMac']==d.BROADCAST_ADDRESS)

        # log charge consumed
        if self.mote.tsch.getIsSync():
            if   isACKed:
                # ACK received
                self.mote.batt.logChargeConsumed(d.CHARGE_TxDataRxAck_uC)
            elif onGoingBroadcast:
                # no ACK expected (link-layer bcast)
                self.mote.batt.logChargeConsumed(d.CHARGE_TxData_uC)
            else:
                # ACK expected, but not received
                self.mote.batt.logChargeConsumed(d.CHARGE_TxDataRxAckNone_uC)

        # nothing ongoing anymore
        self.onGoingTransmission = None

        # inform upper layer (TSCH)
        self.mote.tsch.txDone(isACKed, self.channel)

        # reset the channel
        self.channel = None

    # RX

    def startRx(self, channel):
        assert channel in d.TSCH_HOPPING_SEQUENCE
        assert self.state != d.RADIO_STATE_RX
        self.state = d.RADIO_STATE_RX
        self.channel = channel

    def rxDone(self, packet):
        """end of RX radio activity"""

        # switch radio state
        self.state   = d.RADIO_STATE_OFF

        # log charge consumed
        if self.mote.tsch.getIsSync():
            if not packet:
                # didn't receive any frame (idle listen)
                self.mote.batt.logChargeConsumed(d.CHARGE_Idle_uC)
            elif packet['mac']['dstMac'] == self.mote.get_mac_addr():
                # unicast frame for me, I sent an ACK
                self.mote.batt.logChargeConsumed(d.CHARGE_RxDataTxAck_uC)
            else:
                # either not for me, or broadcast. In any case, I didn't send an ACK
                self.mote.batt.logChargeConsumed(d.CHARGE_RxData_uC)

        # inform upper layer (TSCH)
        is_acked = self.mote.tsch.rxDone(packet, self.channel)

        # reset the channel
        self.channel = None

        # return whether the frame is acknowledged or not
        return is_acked
