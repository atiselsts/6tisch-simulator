"""
"""

# =========================== imports =========================================

import random
import math

# Mote sub-modules

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Rpl(object):

    def __init__(self, mote):

        # store params
        self.mote                      = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()
        self.log                       = SimEngine.SimLog.SimLog().log

        # local variables
        self.rank                      = None
        self.preferredParent           = None
        self.parentChildfromDAOs       = {}      # dictionary containing parents of each node
        self.iAmSendingDAOs            = False

    #======================== public ==========================================

    # getters/setters

    def setRank(self, newVal):
        self.rank = newVal
    def getRank(self):
        return self.rank
    def getDagRank(self):
        return int(self.rank/d.RPL_MINHOPRANKINCREASE)

    def addParentChildfromDAOs(self, parent_id, child_id):
        assert type(parent_id)==int
        assert type(child_id) ==int
        self.parentChildfromDAOs[child_id] = parent_id

    def getPreferredParent(self):
        return self.preferredParent
    def setPreferredParent(self, newVal):
        assert type(newVal)==int
        self.preferredParent = newVal

    # admin

    def startSendingDAOs(self):

        # abort if I'm already sending DAOs
        if self.iAmSendingDAOs:
            return

        # start sending DAOs
        self._schedule_sendDAO(firstDAO=True)

        # I am now sending DAOS
        self.iAmSendingDAOs = True

    # === DIO

    def _create_DIO(self):

        assert self.mote.dodagId!=None

        # create
        newDIO = {
            'type':          d.PKT_TYPE_DIO,
            'app': {
                'rank':      self.rank,
                'dodagId':   self.mote.dodagId,
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

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_TX,
            {
                "_mote_id":  self.mote.id,
                "packet":    newDIO,
            }
        )

        return newDIO

    def action_receiveDIO(self, packet):

        assert packet['type'] == d.PKT_TYPE_DIO

        # abort if I'm not sync'ed (I cannot decrypt the DIO)
        if not self.mote.tsch.getIsSync():
            return

        # abort if I'm not join'ed (I cannot decrypt the DIO)
        if not self.mote.secjoin.getIsJoined():
            return

        # abort if I'm the DAGroot (I don't need to parse a DIO)
        if self.mote.dagRoot:
            return

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_RX,
            {
                "_mote_id":  self.mote.id,
                "packet":    packet,
            }
        )

        # record dodagId
        self.mote.dodagId = packet['app']['dodagId']

        # update rank with sender's information
        self.mote.neighbors[packet['mac']['srcMac']]['rank']  = packet['app']['rank']

        # trigger RPL housekeeping
        self._updateMyRankAndPreferredParent()

        # start sending DAOs (do after my rank is acquired/updated)
        self.startSendingDAOs() # mote

    # === DAO

    def _schedule_sendDAO(self, firstDAO=False):
        """
        Schedule to send a DAO sometimes in the future.
        """

        assert self.mote.dagRoot==False

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
            intraSlotOrder   = d.INTRASLOTORDER_STACKTASKS,
        )

    def _action_sendDAO(self):
        """
        Enqueue a DAO and schedule next one.
        """

        # enqueue
        self._action_enqueueDAO()

        # the root now knows a source route to me
        # I can serve as join proxy: start sending DIOs and EBs
        # I can send data back-and-forth with an app
        self.mote.tsch.startSendingEBs()    # mote
        self.mote.tsch.startSendingDIOs()   # mote
        self.mote.app.startSendingData()    # mote

        # schedule next DAO
        self._schedule_sendDAO()

    def _action_enqueueDAO(self):
        """
        enqueue a DAO into TSCH queue
        """

        assert not self.mote.dagRoot
        assert self.mote.dodagId!=None

        # abort if not ready yet
        if self.mote.clear_to_send_EBs_DIOs_DATA()==False:
            return

        # create
        newDAO = {
            'type':                d.PKT_TYPE_DAO,
            'app': {
                'child_id':        self.mote.id,
                'parent_id':       self.preferredParent,
            },
            'net': {
                'srcIp':           self.mote.id,            # from mote
                'dstIp':           self.mote.dodagId,       # to DAGroot
                'packet_length':   d.PKT_LEN_DAO,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DAO_TX,
            {
                "_mote_id": self.mote.id,
                "packet":   newDAO,
            }
        )

        # remove other possible DAOs from the queue
        self.mote.tsch.remove_frame_from_tx_queue(type=d.PKT_TYPE_DAO)

        # send
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
                "_mote_id": self.mote.id,
                "packet":   packet,
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
            destination to source, or None
        """
        assert type(dest_id)==int

        try:
            sourceRoute = []
            cur_id = dest_id
            while cur_id!=0:
                sourceRoute += [cur_id]
                cur_id       = self.parentChildfromDAOs[cur_id]
        except KeyError:
            returnVal = None
        else:
            # reverse (so goes from source to destination)
            sourceRoute.reverse()

            returnVal = sourceRoute

        return returnVal

    # forwarding

    def findNextHopId(self, packet):
        assert packet['net']['dstIp'] != self.mote.id

        if    packet['net']['dstIp'] == d.BROADCAST_ADDRESS:
            # broadcast packet

            # next hop is broadcast address
            nextHopId = d.BROADCAST_ADDRESS

        elif 'sourceRoute' in packet['net']:
            # unicast source routed downstream packet

            # next hop is the first item in the source route
            nextHopId = self.engine.motes[packet['net']['sourceRoute'].pop(0)].id

        elif self.mote.dagRoot:
            # downstream packet to neighbors of the root
            # FIXME: this is a hack. We should maintain the IPv6 neighbor
            # cache table for on-link determination not only by the root but
            # also by other motes
            nextHopId = packet['net']['dstIp']

        else:
            if packet['net']['dstIp'] == self.mote.dodagId:
                # unicast upstream packet; send it to its preferred parent (default
                # route)
                if self.mote.dodagId is None:
                    # this mote has not been part of RPL network yet; use
                    # self.mote.tsch.join_proxy as its default route
                    # FIXME: in such a situation, the mote should send only
                    # link-local packets.
                    nextHopId = self.mote.tsch.join_proxy
                else:
                    nextHopId = self.preferredParent
            else:
                # unicast downstream packet; assume destination is on-link
                # FIXME: need IPv6 neighbor cache table
                nextHopId = packet['net']['dstIp']

        return nextHopId

    #======================== private ==========================================

    # misc

    def _updateMyRankAndPreferredParent(self):
        """
        RPL housekeeping tasks.

        This routine refreshes
        - self.rank
        - self.preferredParent
        """

        # calculate the rank I would have if choosing each of my neighbor as my preferred parent
        allPotentialRanks = {}
        for (nid, n) in self.mote.neighbors.items():
            if n['rank'] is None:
                # I haven't received a DIO from that neighbor yet, so I don't know its rank (normal)
                continue
            etx                        = self._estimateETX(nid)
            if etx is None: # FIXME
                etx = 16
            rank_increment             = (1*((3*etx)-2) + 0) * d.RPL_MINHOPRANKINCREASE # https://tools.ietf.org/html/rfc8180#section-5.1.1
            allPotentialRanks[nid]     = n['rank']+rank_increment

        # pick lowest potential rank
        (myPotentialParent, myPotentialRank) = sorted(allPotentialRanks.iteritems(), key=lambda x: x[1])[0]

        if (
                (myPotentialRank is not None)
                and
                (myPotentialParent is not None)
                and
                (self.rank != myPotentialRank)
            ):
            # my rank changes; update states
            old_parent           = self.preferredParent
            self.rank            = myPotentialRank
            self.preferredParent = myPotentialParent

            if self.preferredParent != old_parent:
                # log
                self.log(
                    SimEngine.SimLog.LOG_RPL_CHURN,
                    {
                        "_mote_id":        self.mote.id,
                        "rank":            self.rank,
                        "preferredParent": self.preferredParent,
                    }
                )

                # use the new parent as our clock source
                self.mote.tsch.clock.sync(self.preferredParent)

                # trigger 6P ADD if parent changed # FIXME: layer violation
                self.mote.sf.indication_parent_change(old_parent, self.preferredParent)
            else:
                # my rank changes without parent switch
                pass

    def _estimateETX(self, neighbor_id):

        assert type(neighbor_id)==int

        # set initial values for numTx and numTxAck assuming PDR is exactly estimated
        # FIXME
        pdr                   = self.mote.getPDR(neighbor_id)
        numTx                 = d.NUM_SUFFICIENT_TX
        numTxAck              = math.floor(pdr*numTx)

        for (_, cell) in self.mote.tsch.getSchedule().items():
            if  (
                    (cell['neighbor'] == neighbor_id)
                    and
                    (d.CELLOPTION_TX in cell['cellOptions'])
                ):
                numTx        += cell['numTx']
                numTxAck     += cell['numTxAck']

        # abort if about to divide by 0
        if not numTxAck:
            return

        # calculate ETX
        etx = float(numTx)/float(numTxAck)

        return etx
