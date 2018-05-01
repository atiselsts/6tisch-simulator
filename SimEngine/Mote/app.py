"""
An application lives on each node, except the root.
It sends (data) packets to the root
"""

# =========================== imports =========================================

import random

# Mote sub-modules
import sf

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class App(object):

    def __init__(self, mote):

        # store params
        self.mote            = mote

        # singletons (to access quicker than recreate every time)
        self.engine          = SimEngine.SimEngine.SimEngine()
        self.settings        = SimEngine.SimSettings.SimSettings()
        self.log             = SimEngine.SimLog.SimLog().log

        # local variables

    #======================== public ==========================================

    def schedule_mote_sendSinglePacketToDAGroot(self, firstPacket=False):
        """
        schedule an event to send a single packet
        """

        # disable app app_pkPeriod is zero
        if self.settings.app_pkPeriod == 0:
            return

        # compute how long before transmission
        if firstPacket:
            # compute initial time within the range of [next asn, next asn+app_pkPeriod]
            delay            = self.settings.tsch_slotDuration + self.settings.app_pkPeriod*random.random()
        else:
            # compute random delay
            delay            = self.settings.app_pkPeriod*(1+random.uniform(-self.settings.app_pkPeriodVar, self.settings.app_pkPeriodVar))
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

    #=== [TX] mote -> root

    def _action_mote_sendSinglePacketToDAGroot(self,appcounter=0):
        """
        send a single packet, and reschedule next one
        """
        
        # mote
        self.log(
            SimEngine.SimLog.LOG_APP_TX,
            {
                '_mote_id':       self.mote.id,
                'destination':    self.mote.dagRootAddress.id,
                'appcounter':     appcounter,
            }
        )
        
        # enqueue data
        self._action_mote_enqueueDataForDAGroot(appcounter)

        # schedule sending next packet
        self.schedule_mote_sendSinglePacketToDAGroot()
    
    def _action_mote_enqueueDataForDAGroot(self,appcounter):
        """
        enqueue data packet to the DAGroot
        """

        assert not self.mote.dagRoot

        # only send data if I have a preferred parent and dedicated cells to that parent in case of MSF
        if  (
                self.mote.rpl.getPreferredParent()
                and
                (
                    (
                        type(self.mote.sf)==sf.MSF
                        and
                        self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) > 0
                    )
                    or
                    (
                        type(self.mote.sf)!=sf.MSF
                    )
                )
            ):
            
            # create new data packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.APP_TYPE_DATA,
                'code':           None,
                'payload':        { # payload overloaded is to calculate packet stats
                    'asn_at_source':   self.engine.getAsn(),    # ASN, used to calculate e2e latency
                    'hops':            1,                       # number of hops, used to calculate empirical hop count
                    'length':          self.settings.app_pkLength,
                    'appcounter':      appcounter,
                },
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self.mote,                    # from mote
                'dstIp':          self.mote.dagRootAddress,     # to DAGroot
                'sourceRoute':    [],
            }

            # update mote stats
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_TX['type'])

            self.mote.sixlowpan.send(newPacket)
    
    #=== [TX] root -> mote
    
    def _action_root_sendSinglePacketToMote(self,dest_mote,appcounter=0):
        """
        send a single packet
        """
        
        assert self.mote.dagRoot
        
        # mote
        self.log(
            SimEngine.SimLog.LOG_APP_TX,
            {
                '_mote_id':       self.mote.id,
                'destination':    dest_mote.id,
                'appcounter':     appcounter,
            }
        )
        
        # compute source route
        sourceRoute = self.mote.rpl.computeSourceRoute(dest_mote.id)
        
        # create DATA packet
        newPacket = {
            'asn':             self.engine.getAsn(),
            'type':            d.APP_TYPE_DATA,
            'code':            None,
            'payload': { # payload overloaded is to calculate packet stats
                'asn_at_source':   self.engine.getAsn(),    # ASN, used to calculate e2e latency
                'hops':            1,                       # number of hops, used to calculate empirical hop count
                'length':          self.settings.app_pkLength,
                'appcounter':      appcounter,
            },
            'retriesLeft':     d.TSCH_MAXTXRETRIES,
            'srcIp':           self.mote,   # from DAGroot
            'dstIp':           dest_mote,   # to mote
            'sourceRoute':     sourceRoute
        }

        # enqueue packet in TSCH queue
        if not self.mote.tsch.enqueue(newPacket):
            self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_ACK_FAIL_ENQUEUE['type'])
    
    #=== [RX]
    
    def _action_receivePacket(self, srcIp, payload, timestamp):
        """
        Receive a data packet (both DAGroot and mote)
        """

        # FIXME: srcIp is not an address instance but a mote instance
        self.log(
            SimEngine.SimLog.LOG_APP_RX,
            {
                '_mote_id':       self.mote.id,
                'source':         srcIp.id,
                'appcounter':     payload['appcounter'],
            }
        )

        # update mote stats
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RX['type'])

        # log end-to-end latency
        self.mote._stats_logLatencyStat(timestamp - payload['asn_at_source']) # payload[0] is the ASN when sent

        # log the number of hops
        self.mote._stats_logHopsStat(payload['hops'])

        # send end-to-end ACK back to mote, if applicable
        if self.settings.app_e2eAck:

            destination = srcIp
            sourceRoute = self.mote.rpl.computeSourceRoute([destination.id])

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
    