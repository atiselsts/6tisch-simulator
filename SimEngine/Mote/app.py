"""
An application lives on each node, except the root.
It sends (data) packets to the root
"""

# =========================== imports =========================================

import random

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class App(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self.pkPeriod                       = self.settings.app_pkPeriod
        self.pkLength                       = self.settings.app_pkLength

    #======================== public ==========================================

    def schedule_mote_sendSinglePacketToDAGroot(self, firstPacket=False):
        """
        schedule an event to send a single packet
        """

        # disable app pkPeriod is zero
        if self.pkPeriod == 0:
            return

        # compute how long before transmission
        if firstPacket:
            # compute initial time within the range of [next asn, next asn+pkPeriod]
            delay            = self.settings.tsch_slotDuration + self.pkPeriod*random.random()
        else:
            # compute random delay
            delay            = self.pkPeriod*(1+random.uniform(-self.settings.app_pkPeriodVar, self.settings.app_pkPeriodVar))
        assert delay > 0

        # schedule
        self.engine.scheduleIn(
            delay            = delay,
            cb               = self._action_mote_sendSinglePacketToDAGroot,
            uniqueTag        = (self.mote.id, '_action_mote_sendSinglePacketToDAGroot'),
            intraSlotOrder   = 2,
        )

    def schedule_mote_sendPacketBurstToDAGroot(self):
        """
        schedule an event to send a single burst of data (NOT periodic)
        """

        # schedule app_burstNumPackets packets at app_burstTimestamp
        for i in xrange(self.settings.app_burstNumPackets):
            self.engine.scheduleIn(
                delay             = self.settings.app_burstTimestamp,
                cb                = self._action_mote_enqueueDataForDAGroot,
                uniqueTag         = (self.mote.id, '_app_action_enqueueData_burst_{0}'.format(i)),
                intraSlotOrder    = 2,
            )

    def action_mote_receiveE2EAck(self, srcIp, payload, timestamp):
        """
        mote receives end-to-end ACK from the DAGroot
        """

        assert not self.mote.dagRoot


    #======================== private ==========================================

    # app that periodically sends a single packet

    def _action_mote_sendSinglePacketToDAGroot(self):
        """
        send a single packet, and reschedule next one
        """

        # enqueue data
        self._action_mote_enqueueDataForDAGroot()

        # schedule sending next packet
        self.schedule_mote_sendSinglePacketToDAGroot()

    def _action_dagroot_receivePacketFromMote(self, srcIp, payload, timestamp):
        """
        dagroot received data packet
        """

        assert self.mote.dagRoot

        # FIXME: srcIp is not an address instance but a mote instance
        self.log(
            SimEngine.SimLog.LOG_APP_REACHES_DAGROOT,
            {
                'mote_id': srcIp.id,
            }
        )

        # update mote stats
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_REACHES_DAGROOT['type'])

        # log end-to-end latency
        self.mote._stats_logLatencyStat(timestamp - payload['asn_at_source']) # payload[0] is the ASN when sent

        # log the number of hops
        self.mote._stats_logHopsStat(payload['hops'])

        # send end-to-end ACK back to mote, if applicable
        if self.settings.app_e2eAck:

            destination = srcIp
            sourceRoute = self.mote.rpl.getSourceRoute([destination.id])

            if sourceRoute:

                # create e2e ACK
                newPacket = {
                    'asn':             self.engine.getAsn(),
                    'type':            d.APP_TYPE_ACK,
                    'code':            None,
                    'payload':         {},
                    'retriesLeft':     d.TSCH_MAXTXRETRIES,
                    'srcIp':           self.mote,     # from DAGroot
                    'dstIp':           destination,   # to mote
                    'sourceRoute':     sourceRoute
                }

                # enqueue packet in TSCH queue
                if not self.mote.tsch.enqueue(newPacket):
                    self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_ACK_FAIL_ENQUEUE['type'])

    def _action_mote_enqueueDataForDAGroot(self):
        """
        enqueue data packet to the DAGroot
        """

        assert not self.mote.dagRoot

        # only send data if I have a preferred parent and dedicated cells to that parent
        if self.mote.rpl.getPreferredParent() and self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) > 0:

            # create new data packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.APP_TYPE_DATA,
                'code':           None,
                'payload':        { # payload overloaded is to calculate packet stats
                    'asn_at_source':   self.engine.getAsn(),    # ASN, used to calculate e2e latency
                    'hops':            1,                       # number of hops, used to calculate empirical hop count
                    'length':          self.pkLength,
                },
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self.mote,                    # from mote
                'dstIp':          self.mote.dagRootAddress,     # to DAGroot
                'sourceRoute':    [],
            }

            # update mote stats
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_GENERATED['type'])

            self.mote.sixlowpan.send(newPacket)
