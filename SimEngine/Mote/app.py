"""
An application lives on each node
"""

# =========================== imports =========================================

from abc import abstractmethod
import random

# Mote sub-modules
import sf

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================


def App(mote):
    """factory method for application
    """

    settings = SimEngine.SimSettings.SimSettings()

    # use mote.id to determine whether it is the root or not instead of using
    # mote.dagRoot because mote.dagRoot is not initialized when application is
    # instantiated
    if mote.id == 0:
        return AppSink(mote)
    else:
        return globals()[settings.app](mote)


class AppBase(object):
    """Base class for Applications.
    """

    def __init__(self, mote, **kwargs):
        # local variables
        self.appcounter = 0

        # store params
        self.mote       = mote

        # singletons (to access quicker than recreate every time)
        self.engine     = SimEngine.SimEngine.SimEngine()
        self.settings   = SimEngine.SimSettings.SimSettings()
        self.log        = SimEngine.SimLog.SimLog().log

    #======================== public ==========================================

    @abstractmethod
    def activate(self):
        """Starts the application process.

        Typically, this methods schedules an event to send a packet to the root.
        """
        raise NotImplementedError()

    def recv(self, packet):
        """Receive a packet destined to this application
        """
        # log and mote stats
        self.log(
            SimEngine.SimLog.LOG_APP_RX,
            {
                'mote_id'    : self.mote.id,
                'source'     : packet['srcIp'].id,
                'packet_type': d.APP_TYPE_ACK
            }
        )
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RX['type'])

    #======================== private ==========================================

    def _generate_packet(self, dstIp, packet_type, packet_length):

        # FIXME: code and retriesLeft should be filled by other layers
        packet = {
            'asn':               self.engine.getAsn(),
            'type':              packet_type,
            'code':              None,
            'payload': {
                'asn_at_source': self.engine.getAsn(),    # ASN, used to calculate e2e latency
                'hops':          1,                       # number of hops, used to calculate empirical hop count
                'length':        packet_length
            },
            'retriesLeft':       d.TSCH_MAXTXRETRIES,
            'srcIp':             self.mote,
            'dstIp':             dstIp
        }
        # FIXME: sourceRoute should be inserted at the different layer
        if self.mote.dagRoot:
            packet['sourceRoute'] = self.mote.rpl.computeSourceRoute(dstIp.id)
        else:
            packet['sourceRoute'] = []

        return packet

    def _send_packet(self, packet_type, dstIp, packet_length):

        # log and update mote stats
        self.log(
            SimEngine.SimLog.LOG_APP_TX,
            {
                'mote_id'    : self.mote.id,
                'destination': dstIp.id,
                'packet_type': packet_type
            }
        )
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_TX['type'])

        # check whether the mote is ready to send a packet
        if self.mote.dagRoot:
            ready_to_send = True
        elif (
                (
                    self.mote.rpl.getPreferredParent()
                )
                and
                (
                    (
                        type(self.mote.sf) == sf.MSF
                        and
                        (self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) > 0)
                    )
                    or
                    (
                        type(self.mote.sf) != sf.MSF
                    )
                )
             ):
            # send a packet only if the mote has TSCH cells to its preferred parent
            ready_to_send = True
        else:
            ready_to_send = False

        if ready_to_send:
            self.mote.sixlowpan.sendPacket(
                self._generate_packet(
                    dstIp          = dstIp,
                    packet_type    = packet_type,
                    packet_length  = packet_length
                )
            )

class AppSink(AppBase):
    """Handle application packets from motes
    """

    # the payload length of application ACK
    APP_PK_LENGTH = 10

    def __init__(self, mote):
        super(AppSink, self).__init__(mote)

    #======================== public ==========================================

    def activate(self):
        # nothing to schedule
        pass

    def recv(self, packet):
        assert self.mote.dagRoot

        # log and update mote stats
        self.log(
            SimEngine.SimLog.LOG_APP_RX,
            {
                'mote_id'    : self.mote.id,
                'source'     : packet['srcIp'].id,
                'packet_type': packet['type']
            }
        )
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RX['type'])

        # log end-to-end latency
        self.mote._stats_logLatencyStat(
            self.engine.getAsn() - packet['payload']['asn_at_source']
        )

        # log the number of hops
        self.mote._stats_logHopsStat(packet['payload']['hops'])

        # send end-to-end ACK back to mote, if applicable
        if self.settings.app_e2eAck:
            self._send_ack(packet['srcIp'])

    #======================== private ==========================================
    def _send_ack(self, destination):
        self._send_packet(
            dstIp          = destination,
            packet_type    = d.APP_TYPE_ACK,
            packet_length  = self.APP_PK_LENGTH
        )


class AppPeriodic(AppBase):

    """Send a packet periodically

    Intervals are distributed uniformly between (pkPeriod-pkPeriodVar)
    and (pkPeriod+pkPeriodVar).

    The first timing to send a packet is randomly chosen between [next
    asn, (next asn + pkPeriod)].
    """

    def __init__(self, mote, **kwargs):
        super(AppPeriodic, self).__init__(mote)
        self.sending_first_packet = True

    #======================== public ==========================================

    def activate(self):
        self._schedule_transmission()

    #======================== public ==========================================

    def _schedule_transmission(self):
        assert self.settings.app_pkPeriod >= 0
        if self.settings.app_pkPeriod == 0:
            return

        if self.sending_first_packet:
            # compute initial time within the range of [next asn, next asn+pkPeriod]
            delay = self.settings.tsch_slotDuration + (self.settings.app_pkPeriod * random.random())
            self.sending_first_packet = False
        else:
            # compute random delay
            assert self.settings.app_pkPeriodVar < 1
            delay = self.settings.app_pkPeriod * (1 + random.uniform(-self.settings.app_pkPeriodVar, self.settings.app_pkPeriodVar))

        # schedule
        self.engine.scheduleIn(
            delay           = delay,
            cb              = self._event_handler,
            uniqueTag       = (
                'AppPeriodic',
                'scheduled_by_{0}'.format(self.mote.id)
            ),
            intraSlotOrder  = 2,
            )

    def _event_handler(self):
        self._send_packet(
            dstIp          = self.mote.dagRootAddress,
            packet_type    = d.APP_TYPE_DATA,
            packet_length  = self.settings.app_pkLength
        )
        # schedule the next transmission
        self._schedule_transmission()


class AppBurst(AppBase):
    """Generate burst traffic to the root at the specified time (only once)
    """

    #======================== public ==========================================

    def activate(self):
        # schedule app_burstNumPackets packets at pkScheduleAt
        self.engine.scheduleIn(
            delay           = self.settings.app_burstTimestamp,
            cb              = self._send_packets,
            uniqueTag       = (
                'AppBurst',
                'scheduled_by_{0}'.format(self.mote.id)
            ),
            intraSlotOrder  = 2,
        )

    #======================== private ==========================================

    def _send_packets(self):
        for _ in range(0, self.settings.app_burstNumPackets):
            self._send_packet(
                dstIp         = self.mote.dagRootAddress,
                packet_type   = d.APP_TYPE_DATA,
                packet_length = self.settings.app_pkLength
            )
