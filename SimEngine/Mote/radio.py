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
        self.stats = {
            'last_updated'  : 0,
            'idle_listen'   : 0,
            'tx_data_rx_ack': 0,
            'tx_data'       : 0,
            'rx_data_tx_ack': 0,
            'rx_data'       : 0,
            'sleep'         : 0,
        }
        self.log_stats_interval_asn = int(
            float(self.settings.radio_stats_log_period_s) /
            self.settings.tsch_slotDuration
        )
        if self.log_stats_interval_asn > 0:
            self._schedule_log_stats()

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
            if onGoingBroadcast:
                # no ACK expected (link-layer bcast)
                self._update_stats('tx_data')
            else:
                # ACK expected; radio needs to be in RX mode
                self._update_stats('tx_data_rx_ack')

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
                self._update_stats('idle_listen')
            elif packet['mac']['dstMac'] == self.mote.get_mac_addr():
                # unicast frame for me, I sent an ACK
                self._update_stats('rx_data_tx_ack')
            else:
                # either not for me, or broadcast. In any case, I didn't send an ACK
                self._update_stats('rx_data')

        # inform upper layer (TSCH)
        is_acked = self.mote.tsch.rxDone(packet, self.channel)

        # reset the channel
        self.channel = None

        # return whether the frame is acknowledged or not
        return is_acked

    def _update_stats(self, stats_type):
        self.stats['sleep'] += (
            self.engine.getAsn() - self.stats['last_updated'] - 1
        )
        self.stats[stats_type] += 1
        self.stats['last_updated'] = self.engine.getAsn()

    def _schedule_log_stats(self):
        next_log_asn = self.engine.getAsn() + self.log_stats_interval_asn
        self.engine.scheduleAtAsn(
            asn = next_log_asn,
            cb = self._log_stats,
            uniqueTag = (self.mote.id, 'log_radio_stats'),
            intraSlotOrder = d.INTRASLOTORDER_ADMINTASKS,
        )

    def _log_stats(self):
        self.log(
            SimEngine.SimLog.LOG_RADIO_STATS,
            {
                '_mote_id'      : self.mote.id,
                'idle_listen'   : self.stats['idle_listen'],
                'tx_data_rx_ack': self.stats['tx_data_rx_ack'],
                'tx_data'       : self.stats['tx_data'],
                'rx_data_tx_ack': self.stats['rx_data_tx_ack'],
                'rx_data'       : self.stats['rx_data'],
                'sleep'         : self.stats['sleep']
            }
        )

        # schedule next
        self._schedule_log_stats()
