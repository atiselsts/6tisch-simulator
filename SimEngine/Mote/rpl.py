"""
"""

# =========================== imports =========================================

import random
import math

# Mote sub-modules
import sf

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

class NoSourceRouteError(Exception):
    pass

# =========================== helpers =========================================

# =========================== body ============================================

class Rpl(object):

    def __init__(self, mote):

        # store params
        self.mote                      = mote

        # singletons (to access quicker than recreate every time)
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()
        self.log                       = SimEngine.SimLog.SimLog().log

        # local variables
        self.rank                      = None
        self.parentSet                 = []
        self.preferredParent           = None
        self.oldPreferredParent        = None    # preserve old preferred parent upon a change
        self.parentChildfromDAOs       = {}      # dictionary containing parents of each node
        self.neighborRank              = {}      # indexed by neighbor
        self.neighborDagRank           = {}      # indexed by neighbor

    #======================== public ==========================================

    # getters/setters

    def setRank(self, newVal):
        self.rank = newVal
    def getRank(self):
        return self.rank
    def getDagRank(self):
        return self._rankToDagrank(self.rank)
    
    def addParentChildfromDAOs(self, parent_id, child_id):
        assert type(parent_id)==int
        assert type(child_id) ==int
        self.parentChildfromDAOs[child_id] = parent_id

    def getPreferredParent(self):
        return self.preferredParent
    def setPreferredParent(self, newVal):
        self.preferredParent = newVal

    def getOldPreferredParent(self):
        return self.oldPreferredParent
    def setOldPreferredParent(self, newVal):
        self.oldPreferredParent = newVal

    # admin

    def activate(self):
        """
        Initialize the RPL layer
        """

        # start sending DIOs and DAOs
        self._schedule_sendDIO()
        self._schedule_sendDAO(firstDAO=True)

    # DIO

    def action_receiveDIO(self, type, smac, payload):

        # abort if I'm the DAGroot
        if self.mote.dagRoot:
            return

        # abort if I'm not sync'ed
        if not self.mote.tsch.getIsSync():
            return

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_RX,
            {
                "source": smac.id
            }
        )

        # update my mote stats
        self.mote._stats_incrementMoteStats('statsNumRxDIO')
        
        # 'parse' the DIO
        rank = payload[0]

        # don't update poor link
        if self._calcRankIncrease(smac) > d.RPL_MAX_RANK_INCREASE:
            return

        # update rank/DAGrank with sender
        self.neighborRank[smac]         = rank
        self.neighborDagRank[smac]      = self._rankToDagrank(rank)

        # trigger RPL housekeeping
        self._housekeeping()

    # DAO

    def action_receiveDAO(self, type, smac, payload):
        """
        DAGroot receives DAO, store parent/child relationship for source route calculation.
        """

        assert self.mote.dagRoot
        
        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DAO_RX,
            {
                "source": smac.id
            }
        )

        # increment stats
        self.mote._stats_incrementMoteStats('rplRxDAO')
        
        # store parent/child relationship for source route calculation
        self.addParentChildfromDAOs(
            parent_id   = payload['parent_id'],
            child_id    = payload['child_id'],
        )

    # source route

    def computeSourceRoute(self, dest_id):
        """
        Compute the source route to a given mote.

        :param destAddr: [in] The EUI64 address of the final destination.

        :returns: The source route, a list of EUI64 address, ordered from
            destination to source.
        """
        assert type(dest_id)==int
        
        sourceRoute = []
        cur_id = dest_id
        while cur_id!=0:
            sourceRoute += [cur_id]
            try:
                cur_id = self.parentChildfromDAOs[cur_id]
            except KeyError:
                raise NoSourceRouteError()
        
        # reverse (so goes from source to destination)
        sourceRoute.reverse()
        
        return sourceRoute

    # forwarding

    def findNextHop(self, packet):
        """
        Determines the next hop and writes that in the packet's 'nextHop' field.
        """
        assert self != packet['dstIp']
        
        if ('sourceRoute' in packet) and (packet['sourceRoute']):
            # downstream packet (source routed)
            
            # nexthop is the first item in the source route 
            nextHop = [self.engine.motes[packet['sourceRoute'].pop(0)]]
            
        else:
            # upstream packet
            
            # abort if no preferred parent, or root
            if not (self.preferredParent or self.mote.dagRoot):
                return False

            nextHop = None

            if   packet['dstIp'] == d.BROADCAST_ADDRESS:
                nextHop = [d.BROADCAST_ADDRESS]
            elif packet['type'] == d.IANA_6TOP_TYPE_REQUEST or packet['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                # 6P packet: send directly to neighbor
                nextHop = [packet['dstIp']]
            elif packet['dstIp'] == self.mote.dagRootAddress:
                # upstream packet: send to preferred parent
                nextHop = [self.preferredParent]
            elif packet['sourceRoute']:
                # dowstream packet: next hop read from source route
                nextHopId = packet['sourceRoute'].pop()
                for nei in self.mote._myNeighbors():
                    if [nei.id] == nextHopId:
                        nextHop = [nei]
            elif packet['dstIp'] in self.mote._myNeighbors():
                nextHop = [packet['dstIp']]

        packet['nextHop'] = nextHop
        return True if nextHop else False

    #======================== private ==========================================

    # DIO

    def _schedule_sendDIO(self):
        """
        Send a DIO sometimes in the future.
        """

        # schedule to send a DIO every slotframe
        # _action_sendDIO() decides whether to actually send, based on probability
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn() + int(self.settings.tsch_slotframeLength),
            cb               = self._action_sendDIO,
            uniqueTag        = (self.mote.id, '_action_sendDIO'),
            intraSlotOrder   = 3,
        )

    def _action_sendDIO(self):
        """
        decide whether to enqueue a DIO, enqueue DIO, schedule next DIO.
        """

        # compute probability to send a DIO
        dioProb =   (                                                           \
                        float(self.settings.tsch_probBcast_dioProb)             \
                        /                                                       \
                        float(len(self.mote.secjoin.areAllNeighborsJoined()))   \
                    )                                                           \
                    if                                                          \
                    len(self.mote.secjoin.areAllNeighborsJoined())              \
                    else                                                        \
                    float(self.settings.tsch_probBcast_dioProb)
        sendDio =(random.random() < dioProb)

        # enqueue DIO, if appropriate
        if sendDio:
            # probability passes
            self._action_enqueueDIO()

        # schedule next DIO
        self._schedule_sendDIO()

    def _action_enqueueDIO(self):
        """
        enqueue DIO in TSCH queue
        """

        if self.mote.dagRoot or (self.preferredParent and self.mote.numCellsToNeighbors.get(self.preferredParent, 0) != 0):
            # I am the root, or I have a preferred parent with dedicated cells to it

            self.mote._stats_incrementMoteStats('rplTxDIO')
            
            # log
            self.log(
                SimEngine.SimLog.LOG_RPL_DIO_TX,
                {
                    "mote_id": self.mote.id
                }
            )
            
            # create new packet
            newDIO = {
                'type':           d.RPL_TYPE_DIO,
                'asn':            self.engine.getAsn(),
                'code':           None,
                'payload':        [self.rank], # the payload is the rpl rank
                'retriesLeft':    1,           # do not retransmit (broadcast)
                'srcIp':          self,
                'dstIp':          d.BROADCAST_ADDRESS,
                'sourceRoute':    []
            }

            # enqueue packet in TSCH queue
            if not self.mote.tsch.enqueue(newDIO):
                self.mote.radio.drop_packet(newDIO, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])

    # DAO

    def _schedule_sendDAO(self, firstDAO=False):
        """
        Schedule to send a DAO sometimes in the future.
        """

        # abort it I'm the root
        if self.mote.dagRoot:
            return

        # abort if DAO disabled
        if self.settings.rpl_daoPeriod == 0:
            return
        
        asnNow = self.engine.getAsn()

        if firstDAO:
            asnDiff = 1
        else:
            asnDiff = int(math.ceil(
                random.uniform(
                    0.8 * self.settings.rpl_daoPeriod,
                    1.2 * self.settings.rpl_daoPeriod
                ) / self.settings.tsch_slotDuration)
            )

        # schedule sending a DAO
        self.engine.scheduleAtAsn(
            asn              = asnNow + asnDiff,
            cb               = self._action_sendDAO,
            uniqueTag        = (self.mote.id, '_action_sendDAO'),
            intraSlotOrder   = 3,
        )

    def _action_sendDAO(self):
        """
        Enqueue a DAO and schedule next one.
        """
        
        # enqueue
        self._action_enqueueDAO()

        # schedule next DAO
        self._schedule_sendDAO()

    def _action_enqueueDAO(self):
        """
        enqueue a DAO into TSCH queue
        """

        assert not self.mote.dagRoot
        
        # only send DAOs if I have a preferred parent to which I have dedicated cells
        if  (
                self.preferredParent
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

            self.mote._stats_incrementMoteStats('rplTxDAO')
            
            # log
            self.log(
                SimEngine.SimLog.LOG_RPL_DAO_TX,
                {
                    "mote_id": self.mote.id
                }
            )
            
            # create new packet
            newDAO = {
                'type':           d.RPL_TYPE_DAO,
                'asn':            self.engine.getAsn(),
                'code':           None,
                'payload':        {
                    'child_id':   self.mote.id,
                    'parent_id':  self.preferredParent.id,
                },
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self,
                'dstIp':          self.mote.dagRootAddress,
                'sourceRoute':    [],
            }
            
            # enqueue packet in TSCH queue
            if not self.mote.tsch.enqueue(newDAO):
                self.mote.radio.drop_packet(newDAO, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])

    # misc

    def _housekeeping(self):
        """
        RPL housekeeping tasks.

        This routine refreshes
        - self.preferredParent
        - self.rank
        - self.parentSet
        """

        # calculate my potential rank with each of the motes I have heard a DIO from
        potentialRanks = {}
        for (neighbor, neighborRank) in self.neighborRank.items():
            # calculate the rank increase to that neighbor
            rankIncrease = self._calcRankIncrease(neighbor)
            if rankIncrease is not None and rankIncrease <= min([d.RPL_MAX_RANK_INCREASE, d.RPL_MAX_TOTAL_RANK-neighborRank]):
                # record this potential rank
                potentialRanks[neighbor] = neighborRank+rankIncrease

        # sort potential ranks
        sorted_potentialRanks = sorted(potentialRanks.iteritems(), key=lambda x: x[1])

        # switch parents only when rank difference is large enough
        for i in range(1, len(sorted_potentialRanks)):
            if sorted_potentialRanks[i][0] in self.parentSet:
                # compare the selected current parent with motes who have lower potential ranks
                # and who are not in the current parent set
                for j in range(i):
                    if sorted_potentialRanks[j][0] not in self.parentSet:
                        if sorted_potentialRanks[i][1]-sorted_potentialRanks[j][1] < d.RPL_PARENT_SWITCH_THRESHOLD:
                            mote_rank = sorted_potentialRanks.pop(i)
                            sorted_potentialRanks.insert(j, mote_rank)
                            break

        # pick my preferred parent and resulting rank
        if sorted_potentialRanks:
            oldParentSet = set([parent.id for parent in self.parentSet])

            (newPreferredParent, newrank) = sorted_potentialRanks[0]

            # compare a current preferred parent with new one
            if self.preferredParent and newPreferredParent != self.preferredParent:
                for (mote, rank) in sorted_potentialRanks[:d.RPL_PARENT_SET_SIZE]:
                    if mote == self.preferredParent:
                        # switch preferred parent only when rank difference is large enough
                        if rank-newrank < d.RPL_PARENT_SWITCH_THRESHOLD:
                            (newPreferredParent, newrank) = (mote, rank)

            # update mote stats
            if self.rank and newrank != self.rank:
                self.mote._stats_incrementMoteStats('rplChurnRank')
                # log
                self.log(
                    SimEngine.SimLog.LOG_RPL_CHURN_RANK,
                    {
                        "old_rank": self.rank,
                        "new_rank": newrank
                    }
                )
            if (self.preferredParent is None) and (newPreferredParent is not None):
                if not self.settings.secjoin_enabled:
                    # if we selected a parent for the first time, add one cell to it
                    # upon successful join, the reservation request is scheduled explicitly
                    self.mote.sf.schedule_parent_change(self.mote)
            elif self.preferredParent != newPreferredParent:
                # update mote stats
                self.mote._stats_incrementMoteStats('rplChurnPrefParent')

                # log
                self.log(
                    SimEngine.SimLog.LOG_RPL_CHURN_PREF_PARENT,
                    {
                        "old_parent": self.preferredParent.id,
                        "new_parent": newPreferredParent.id
                    }
                )
                # trigger 6P add to the new parent
                self.oldPreferredParent = self.preferredParent
                self.mote.sf.schedule_parent_change(self.mote)

            # store new preferred parent and rank
            (self.preferredParent, self.rank) = (newPreferredParent, newrank)

            # pick my parent set
            self.parentSet = [n for (n, _) in sorted_potentialRanks if self.neighborRank[n] < self.rank][:d.RPL_PARENT_SET_SIZE]
            assert self.preferredParent in self.parentSet

            if oldParentSet != set([parent.id for parent in self.parentSet]):
                self.mote._stats_incrementMoteStats('rplChurnParentSet')

    def _calcRankIncrease(self, neighbor):
        """
        calculate the RPL rank increase with a particular neighbor.
        """
        
        # estimate the ETX to that neighbor
        etx = self._estimateETX(neighbor)
        
        # return if that failed
        if not etx:
            return

        # per draft-ietf-6tisch-minimal, rank increase is (3*ETX-2)*d.RPL_MIN_HOP_RANK_INCREASE
        return int(((3*etx) - 2)*d.RPL_MIN_HOP_RANK_INCREASE)

    def _estimateETX(self, neighbor):

        # set initial values for numTx and numTxAck assuming PDR is exactly estimated
        pdr                   = self.mote.getPDR(neighbor)
        numTx                 = d.NUM_SUFFICIENT_TX
        numTxAck              = math.floor(pdr*numTx)
        
        for (_, cell) in self.mote.tsch.getSchedule().items():
            if  (                                          \
                    cell['neighbor'] == neighbor and       \
                    cell['dir'] == d.DIR_TX                \
                )                                          \
                or                                         \
                (                                          \
                    cell['neighbor'] == neighbor and       \
                    cell['dir'] == d.DIR_TXRX_SHARED       \
                ):
                numTx        += cell['numTx']
                numTxAck     += cell['numTxAck']
        
        # abort if about to divide by 0
        if not numTxAck:
            return

        # calculate ETX
        etx = float(numTx)/float(numTxAck)

        return etx
    
    def _rankToDagrank(self,r):
        return int(r/d.RPL_MIN_HOP_RANK_INCREASE)
