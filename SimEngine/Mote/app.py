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
                'dest_id':        self.mote.dagRootId,
                'appcounter':     appcounter,
            }
        )
        
        # enqueue data
        self._action_mote_enqueueDataForDAGroot(appcounter)

        # schedule sending next packet
        self.schedule_mote_sendSinglePacketToDAGroot()
    
    def _action_mote_enqueueDataForDAGroot(self,appcounter=0):
        """
        enqueue data packet to the DAGroot
        """

        assert not self.mote.dagRoot

        # only send data if I have a preferred parent and dedicated cells to that parent in case of MSF
        if  (
                self.mote.rpl.getPreferredParent()!=None
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
            newUpstreamDataPacket = {
                'type':                     d.APP_TYPE_DATA,
                'app': {
                    'appcounter':           appcounter,
                },
                'net': {
                    'srcIp':                self.mote.id,              # from mote
                    'dstIp':                self.mote.dagRootId,       # to DAGroot
                    'packet_length':        self.settings.app_pkLength
                },
            }

            self.mote.sixlowpan.send(newUpstreamDataPacket)
    
    #=== [TX] root -> mote
    
    def _action_root_sendSinglePacketToMote(self,dest_id,appcounter=0):
        """
        send a single packet
        """
        
        assert type(dest_id)==int
        assert self.mote.dagRoot
        
        # mote
        self.log(
            SimEngine.SimLog.LOG_APP_TX,
            {
                '_mote_id':       self.mote.id,
                'dest_id':        dest_id,
                'appcounter':     appcounter,
            }
        )
        
        # compute source route
        sourceRoute = self.mote.rpl.computeSourceRoute(dest_id)
        
        # create DATA packet
        newDownstreamDataPacket = {
            'type':                     d.APP_TYPE_DATA,
            'app': {
                'appcounter':           appcounter,
            },
            'net': {
                'srcIp':                self.mote.id, # to DAGroot
                'dstIp':                dest_id,      # from mote
                'sourceRoute':          sourceRoute,
                'packet_length':        self.settings.app_pkLength
            },
        }
        
        # send a packet
        self.mote.sixlowpan.send(newDownstreamDataPacket)
    
    #=== [RX]
    
    def _action_receivePacket(self, packet):
        """
        Receive a data packet (both DAGroot and mote)
        """

        # FIXME: srcIp is not an address instance but a mote instance
        self.log(
            SimEngine.SimLog.LOG_APP_RX,
            {
                '_mote_id':       self.mote.id,
                'packet':         packet,
            }
        )
