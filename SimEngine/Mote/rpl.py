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

    #======================== public ==========================================

    # getters/setters

    def setRank(self, newVal):
        self.rank = newVal
    def getRank(self):
        return self.rank
    def getDagRank(self):
        return int(self.rank/d.RPL_MIN_HOP_RANK_INCREASE)
    
    def addParentChildfromDAOs(self, parent_id, child_id):
        assert type(parent_id)==int
        assert type(child_id) ==int
        self.parentChildfromDAOs[child_id] = parent_id

    def getPreferredParent(self):
        return self.preferredParent
    def setPreferredParent(self, newVal):
        assert type(newVal)==int
        self.preferredParent = newVal

    def getOldPreferredParent(self):
        return self.oldPreferredParent
    def setOldPreferredParent(self, newVal):
        assert type(newVal)==int
        self.oldPreferredParent = newVal

    # admin

    def activate(self):
        """
        Initialize the RPL layer
        """

        # start sending DAOs
        self._schedule_sendDAO(firstDAO=True)
    
    # === DIO
    
    def _create_DIO(self):
        newDIO = {
            'type':          d.PKT_TYPE_DIO,
            'app': {
                'rank':      self.rank,
            },
            'net': {
                'srcIp':     self.mote.id,            # from mote
                'dstIp':     d.BROADCAST_ADDRESS,     # broadcast (in reality "all RPL routers")
            },
            'mac': {
                'srcMac':    self.mote.id,            # from mote
                'dstMac':    d.BROADCAST_ADDRESS,     # broadcast
            }
        }
        
        return newDIO
    
    def action_receiveDIO(self, packet):
        
        assert packet['type'] == d.PKT_TYPE_DIO
        
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
                "_mote_id":  self.mote.id,
                "source":    packet['mac']['srcMac'],
            }
        )
        
        # don't update poor link
        if self._calcRankIncrease(packet['mac']['srcMac']) > d.RPL_MAX_RANK_INCREASE:
            return

        # update rank/DAGrank with sender
        self.neighborRank[packet['mac']['srcMac']]    = packet['app']['rank']

        # trigger RPL housekeeping
        self._housekeeping()

    # === DAO
    
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
                self.preferredParent!=None
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
            
            # log
            self.log(
                SimEngine.SimLog.LOG_RPL_DAO_TX,
                {
                    "_mote_id": self.mote.id
                }
            )
            
            # create new packet
            newDAO = {
                'type':           d.PKT_TYPE_DAO,
                'app': {
                    'child_id':   self.mote.id,
                    'parent_id':  self.preferredParent,
                },
                'net': {
                    'srcIp':      self.mote.id,            # from mote
                    'dstIp':      self.mote.dagRootId,     # to DAGroot
                },
            }
            
            # remove other possible DAOs from the queue
            self.mote.tsch.removeTypeFromQueue(d.PKT_TYPE_DAO)
            
            # send the DAO via sixlowpan
            self.mote.sixlowpan.sendPacket(newDAO)
    
    def action_receiveDAO(self, packet):
        """
        DAGroot receives DAO, store parent/child relationship for source route calculation.
        """

        assert self.mote.dagRoot
        
        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DAO_RX,
            {
                "source": packet['mac']['srcMac']
            }
        )

        # store parent/child relationship for source route calculation
        self.addParentChildfromDAOs(
            parent_id   = packet['app']['parent_id'],
            child_id    = packet['app']['child_id'],
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

    def findNextHopId(self, packet):
        """
        Determines the next hop and writes that in the packet's 'nextHop' field.
        """
        assert packet['net']['dstIp'] != self.mote.id
        
        if    packet['net']['dstIp'] == d.BROADCAST_ADDRESS:
            # broadcast packet
            
            # broadcast next hop
            nextHopId = d.BROADCAST_ADDRESS
        
        elif 'sourceRoute' in packet['net']:
            # unicast source routed downstream packet
            
            # nextHopId is the first item in the source route 
            nextHopId = self.engine.motes[packet['net']['sourceRoute'].pop(0)].id
            
        else:
            # unicast upstream packet
            
            if self.preferredParent==None:
                # no preferred parent
                
                nextHopId =  None
            else:
                if   packet['net']['dstIp'] == self.mote.dagRootId:
                    # common upstream packet
                    
                    # send to preferred parent
                    nextHopId = self.preferredParent
                elif packet['net']['dstIp'] in self.mote._myNeighbors():
                    # packet to a neighbor
                    
                    # nexhop is that neighbor
                    nextHopId = dstIpId
                else:
                    raise SystemError()
        
        return nextHopId

    #======================== private ==========================================
    
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
            if (rankIncrease is not None) and (rankIncrease <= min([d.RPL_MAX_RANK_INCREASE, d.RPL_MAX_TOTAL_RANK-neighborRank])):
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
            oldParentSet = set(self.parentSet)

            (newPreferredParent, newrank) = sorted_potentialRanks[0]

            # compare a current preferred parent with new one
            if (self.preferredParent!=None) and (newPreferredParent!=self.preferredParent):
                for (mote, rank) in sorted_potentialRanks[:d.RPL_PARENT_SET_SIZE]:
                    if mote == self.preferredParent:
                        # switch preferred parent only when rank difference is large enough
                        if rank-newrank < d.RPL_PARENT_SWITCH_THRESHOLD:
                            (newPreferredParent, newrank) = (mote, rank)

            # log
            if self.rank and newrank != self.rank:
                self.log(
                    SimEngine.SimLog.LOG_RPL_CHURN_RANK,
                    {
                        "old_rank": self.rank,
                        "new_rank": newrank
                    }
                )
            
            if (self.preferredParent==None) and (newPreferredParent is not None):
                # if we selected a parent for the first time, add one cell to it
                # upon successful join, the reservation request is scheduled explicitly
                self.mote.sf.schedule_parent_change(self.mote)
            elif self.preferredParent != newPreferredParent:
                # log
                self.log(
                    SimEngine.SimLog.LOG_RPL_CHURN_PREF_PARENT,
                    {
                        "old_parent": self.preferredParent,
                        "new_parent": newPreferredParent
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
        
    def _calcRankIncrease(self, neighbor):
        """
        calculate the RPL rank increase with a particular neighbor.
        """
        
        assert type(neighbor)==int
        
        # estimate the ETX to that neighbor
        etx = self._estimateETX(neighbor)
        
        # return if that failed
        if not etx:
            return

        # per draft-ietf-6tisch-minimal, rank increase is (3*ETX-2)*d.RPL_MIN_HOP_RANK_INCREASE
        return int(((3*etx) - 2)*d.RPL_MIN_HOP_RANK_INCREASE)

    def _estimateETX(self, neighbor):
        
        assert type(neighbor)==int
        
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
