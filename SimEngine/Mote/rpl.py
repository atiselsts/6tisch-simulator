""" RPL Implementation
references:
- IETF RFC 6550
- IETF RFC 6552
- IETF RFC 6553
- IETF RFC 8180

note:
- global/local repair is not supported
"""

# =========================== imports =========================================

import random
import math

import netaddr

# Mote sub-modules

# Simulator-wide modules
import SimEngine
import MoteDefines as d
from trickle_timer import TrickleTimer

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Rpl(object):

    DEFAULT_DIO_INTERVAL_MIN = 14
    DEFAULT_DIO_INTERVAL_DOUBLINGS = 9
    DEFAULT_DIO_REDUNDANCY_CONSTANT = 3

    # locally-defined constants
    DEFAULT_DIS_INTERVAL_SECONDS = 60

    def __init__(self, mote):

        # store params
        self.mote                      = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()
        self.log                       = SimEngine.SimLog.SimLog().log

        # local variables
        self.dodagId                   = None
        self.of                        = RplOF0(self)
        self.trickle_timer             = TrickleTimer(
            i_min    = pow(2, self.DEFAULT_DIO_INTERVAL_MIN),
            i_max    = self.DEFAULT_DIO_INTERVAL_DOUBLINGS,
            k        = self.DEFAULT_DIO_REDUNDANCY_CONSTANT,
            callback = self._send_DIO
        )
        self.parentChildfromDAOs       = {}      # dictionary containing parents of each node
        self._tx_stat                  = {}      # indexed by mote_id
        self.dis_mode = self._get_dis_mode()

    #======================== public ==========================================

    # getters/setters

    def get_rank(self):
        return self.of.rank

    def getDagRank(self):
        if self.of.rank is None:
            return None
        else:
            return int(self.of.rank / d.RPL_MINHOPRANKINCREASE)

    def addParentChildfromDAOs(self, parent_addr, child_addr):
        self.parentChildfromDAOs[child_addr] = parent_addr

    def getPreferredParent(self):
        # FIXME: when we implement IPv6 address or MAC address, we should
        # define the return type of this method. Currently, this method can
        # return a node ID, a MAC address, or an IPv6 address since they are
        # all the same value for a certain mote.
        return self.of.get_preferred_parent()

    # admin

    def start(self):
        if self.mote.dagRoot:
            self.dodagId = self.mote.get_ipv6_global_addr()
            self.of = RplOFNone(self)
            self.of.set_rank(d.RPL_MINHOPRANKINCREASE)
            self.trickle_timer.start()
            # now start a new RPL instance; reset the timer as per Section 8.3 of
            # RFC 6550
            self.trickle_timer.reset()
        else:
            # start sending DIS
            self.send_DIS()

    def indicate_tx(self, cell, dstMac, isACKed):
        self.of.update_etx(cell, dstMac, isACKed)

    def indicate_preferred_parent_change(self, old_preferred, new_preferred):
        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_CHURN,
            {
                "_mote_id":        self.mote.id,
                "rank":            self.of.rank,
                "preferredParent": new_preferred
            }
        )

        # trigger DAO
        self._schedule_sendDAO(firstDAO=True)

        # use the new parent as our clock source
        self.mote.tsch.clock.sync(new_preferred)

        # trigger 6P ADD if parent changed
        self.mote.sf.indication_parent_change(old_preferred, new_preferred)

        # reset trickle timer to inform new rank quickly
        self.trickle_timer.reset()

    def local_repair(self):
        assert (
            (self.of.rank is None)
            or
            (self.of.rank == d.RPL_INFINITE_RANK)
        )
        self.log(
            SimEngine.SimLog.LOG_RPL_LOCAL_REPAIR,
            {
                "_mote_id":        self.mote.id
            }
        )
        self._send_DIO() # sending a DIO with the infinite rank
        self.dodagId = None
        self.trickle_timer.stop()
        self.mote.tsch.stopSendingEBs()

    # === DIS

    def action_receiveDIS(self, packet):
        if   self.mote.is_my_ipv6_addr(packet['net']['dstIp']):
            # unicast DIS; send unicast DIO back to the source
            self._send_DIO(packet['net']['srcIp'])
        elif packet['net']['dstIp'] == d.IPV6_ALL_RPL_NODES_ADDRESS:
            # broadcast DIS
            self.trickle_timer.reset()
        else:
            # shouldn't happen
            assert False

    def _get_dis_mode(self):
        if   'dis_unicast' in self.settings.rpl_extensions:
            assert 'dis_broadcast' not in self.settings.rpl_extensions
            return 'dis_unicast'
        elif 'dis_broadcast' in self.settings.rpl_extensions:
            assert 'dis_unicast' not in self.settings.rpl_extensions
            return 'dis_broadcast'
        else:
            return 'disabled'

    def _start_dis_timer(self):
        self.engine.scheduleIn(
            delay          = self.DEFAULT_DIS_INTERVAL_SECONDS,
            cb             = self.send_DIS,
            uniqueTag      = str(self.mote.id) + 'dis',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS
        )

    def _stop_dis_timer(self):
        self.engine.removeFutureEvent(str(self.mote.id) + 'dis')

    def send_DIS(self, dstIp=None):

        if dstIp is None:
            if   self.dis_mode == 'dis_unicast':
                # join_proxy is a possible parent
                dstIp = str(self.mote.tsch.join_proxy.ipv6_link_local())
            elif self.dis_mode == 'dis_broadcast':
                dstIp = d.IPV6_ALL_RPL_NODES_ADDRESS
            elif self.dis_mode == 'disabled':
                return

        dis = {
            'type': d.PKT_TYPE_DIS,
            'net' : {
                'srcIp':         str(self.mote.get_ipv6_link_local_addr()),
                'dstIp':         dstIp,
                'packet_length': d.PKT_LEN_DIS
            },
            'app' : {}
        }

        self.mote.sixlowpan.sendPacket(dis)
        self._start_dis_timer()

    # === DIO

    def _send_DIO(self, dstIp=None):
        assert self.dodagId is not None

        dio = self._create_DIO(dstIp)

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_TX,
            {
                "_mote_id":  self.mote.id,
                "packet":    dio,
            }
        )

        self.mote.sixlowpan.sendPacket(dio)

    def _create_DIO(self, dstIp=None):

        assert self.dodagId is not None

        if dstIp is None:
            dstIp = d.IPV6_ALL_RPL_NODES_ADDRESS

        if self.of.rank is None:
            rank = d.RPL_INFINITE_RANK
        else:
            rank = self.of.rank

        # create
        newDIO = {
            'type':              d.PKT_TYPE_DIO,
            'app': {
                'rank':          rank,
                'dodagId':       self.dodagId,
            },
            'net': {
                'srcIp':         self.mote.get_ipv6_link_local_addr(),
                'dstIp':         dstIp,
                'packet_length': d.PKT_LEN_DIO
            }
        }

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

        # handle the infinite rank
        if packet['app']['rank'] == d.RPL_INFINITE_RANK:
            if self.dodagId is None:
                # ignore this DIO
                return
            else:
                # if the DIO has the infinite rank, reset the Trickle timer
                self.trickle_timer.reset()

        # feed our OF with the received DIO
        self.of.update(packet)

        # record dodagId
        if (
                (self.dodagId is None)
                and
                (self.getPreferredParent() is not None)
            ):
            # join the RPL network
            self.dodagId = packet['app']['dodagId']
            self.mote.add_ipv6_prefix(d.IPV6_DEFAULT_PREFIX)
            self.trickle_timer.start()
            self.trickle_timer.reset()
            self._stop_dis_timer()


    # === DAO

    def _schedule_sendDAO(self, firstDAO=False):
        """
        Schedule to send a DAO sometimes in the future.
        """

        assert self.mote.dagRoot is False

        # abort if DAO disabled
        if self.settings.rpl_daoPeriod == 0:
           # secjoin never completes if downward traffic is not supported by
            # DAO
            assert self.settings.secjoin_enabled is False

            # start sending EBs and application packets.
            self.mote.tsch.startSendingEBs()
            self.mote.app.startSendingData()
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

        if self.of.get_preferred_parent() is None:
            # stop sending DAO
            return

        # enqueue
        self._action_enqueueDAO()

        # the root now knows a source route to me
        # I can serve as join proxy: start sending DIOs and EBs
        # I can send data back-and-forth with an app
        self.mote.tsch.startSendingEBs()    # mote
        self.mote.app.startSendingData()    # mote

        # schedule next DAO
        self._schedule_sendDAO()

    def _action_enqueueDAO(self):
        """
        enqueue a DAO into TSCH queue
        """

        assert not self.mote.dagRoot
        assert self.dodagId!=None

        # abort if not ready yet
        if self.mote.clear_to_send_EBs_DATA()==False:
            return

        parent_mac_addr = netaddr.EUI(self.of.get_preferred_parent())
        prefix = netaddr.IPAddress(d.IPV6_DEFAULT_PREFIX)
        parent_ipv6_addr = str(parent_mac_addr.ipv6(prefix))

        # create
        newDAO = {
            'type':                d.PKT_TYPE_DAO,
            'app': {
                'parent_addr':     parent_ipv6_addr,
            },
            'net': {
                'srcIp':           self.mote.get_ipv6_global_addr(),
                'dstIp':           self.dodagId,       # to DAGroot
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
        self.mote.tsch.remove_packets_in_tx_queue(type=d.PKT_TYPE_DAO)

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
            parent_addr   = packet['app']['parent_addr'],
            child_addr    = packet['net']['srcIp']
        )

    # source route

    def computeSourceRoute(self, dst_addr):
        assert self.mote.dagRoot
        try:
            sourceRoute = []
            cur_addr = dst_addr
            while self.mote.is_my_ipv6_addr(cur_addr) is False:
                sourceRoute += [cur_addr]
                cur_addr     = self.parentChildfromDAOs[cur_addr]
                if cur_addr in sourceRoute:
                    # routing loop is detected; cannot return an effective
                    # source-routing header
                    returnVal = None
                    break
        except KeyError:
            returnVal = None
        else:
            # reverse (so goes from source to destination)
            sourceRoute.reverse()

            returnVal = sourceRoute

        return returnVal


class RplOFNone(object):

    def __init__(self, rpl):
        self.rpl = rpl
        self.rank = None
        self.preferred_parent = None

    def update(self, dio):
        # do nothing on the root
        pass

    def set_rank(self, new_rank):
        self.rank = new_rank

    def set_preferred_parent(self, new_preferred_parent):
        self.preferred_parent = new_preferred_parent

    def get_preferred_parent(self):
        return self.preferred_parent

    def update_etx(self, cell, mac_addr, isACKed):
        # do nothing
        pass


class RplOF0(object):

    # Constants defined in RFC 6550
    INFINITE_RANK = 65535

    # Constants defined in RFC 8180
    UPPER_LIMIT_OF_ACCEPTABLE_ETX = 3
    MINIMUM_STEP_OF_RANK = 1
    MAXIMUM_STEP_OF_RANK = 9

    ETX_DEFAULT = UPPER_LIMIT_OF_ACCEPTABLE_ETX
    # if we have a "good" link to the parent, stay with the parent even if the
    # rank of the parent is worse than the best neighbor by more than
    # PARENT_SWITCH_RANK_THRESHOLD. rank_increase is computed as per Section
    # 5.1.1. of RFC 8180.
    ETX_GOOD_LINK = 2
    PARENT_SWITCH_RANK_INCREASE_THRESHOLD = (
        ((3 * ETX_GOOD_LINK) - 2) * d.RPL_MINHOPRANKINCREASE
    )

    def __init__(self, rpl):
        self.rpl = rpl
        self.neighbors = []
        self.rank = None
        self.preferred_parent = None

    @property
    def parents(self):
        # a parent should have a lower rank than us by MinHopRankIncrease at
        # least. See section 3.5.1 of RFC 6550:
        #    "MinHopRankIncrease is the minimum increase in Rank between a node
        #     and any of its DODAG parents."
        _parents = []
        for neighbor in self.neighbors:
            if self._calculate_rank(neighbor) is None:
                # skip this one
                continue

            if (
                    (self.rank is None)
                    or
                    (
                        d.RPL_MINHOPRANKINCREASE <=
                        self.rank - neighbor['advertised_rank']
                    )
                ):
                _parents.append(neighbor)

        return _parents

    def update(self, dio):
        mac_addr = dio['mac']['srcMac']
        rank = dio['app']['rank']

        # update neighbor's rank
        neighbor = self._find_neighbor(mac_addr)
        if neighbor is None:
            neighbor = self._add_neighbor(mac_addr)
        self._update_neighbor_rank(neighbor, rank)

        # if we received the infinite rank from our preferred parent,
        # invalidate our rank
        if (
                (self.preferred_parent == neighbor)
                and
                (rank == d.RPL_INFINITE_RANK)
            ):
            self.rank = None

        # change preferred parent if necessary
        self._update_preferred_parent()

    def get_preferred_parent(self):
        if self.preferred_parent is None:
            return None
        else:
            return self.preferred_parent['mac_addr']

    def update_etx(self, cell, mac_addr, isACKed):
        neighbor = self._find_neighbor(mac_addr)
        if neighbor is None:
            # we've not received DIOs from this neighbor; ignore the neighbor
            return
        elif (
                (cell.mac_addr == mac_addr)
                and
                (d.CELLOPTION_TX in cell.options)
                and
                (d.CELLOPTION_SHARED not in cell.options)
            ):
            neighbor['numTx'] += 1
            if isACKed is True:
                neighbor['numTxAck'] += 1
            self._update_neighbor_rank_increase(neighbor)
            self._update_preferred_parent()

    def _add_neighbor(self, mac_addr):
        assert self._find_neighbor(mac_addr) is None

        neighbor = {
            'mac_addr': mac_addr,
            'advertised_rank': None,
            'rank_increase': None,
            'numTx': 0,
            'numTxAck': 0
        }
        self.neighbors.append(neighbor)
        self._update_neighbor_rank_increase(neighbor)
        return neighbor

    def _find_neighbor(self, mac_addr):
        for neighbor in self.neighbors:
            if neighbor['mac_addr'] == mac_addr:
                return neighbor
        return None

    def _update_neighbor_rank(self, neighbor, new_advertised_rank):
        neighbor['advertised_rank'] = new_advertised_rank

    def _update_neighbor_rank_increase(self, neighbor):
        if neighbor['numTxAck'] == 0:
            # ETX is not available
            etx = None
        else:
            etx = float(neighbor['numTx']) / neighbor['numTxAck']

        if etx is None:
            etx = self.ETX_DEFAULT

        if etx > self.UPPER_LIMIT_OF_ACCEPTABLE_ETX:
            step_of_rank = None
        else:
            step_of_rank = (3 * etx) - 2
        if step_of_rank is None:
            # this neighbor will not be considered as a parent
            neighbor['rank_increase'] = None
        else:
            assert self.MINIMUM_STEP_OF_RANK <= step_of_rank
            # step_of_rank never exceeds 7 because the upper limit of acceptable
            # ETX is 3, which is defined in Section 5.1.1 of RFC 8180
            assert step_of_rank <= self.MAXIMUM_STEP_OF_RANK
            neighbor['rank_increase'] = step_of_rank * d.RPL_MINHOPRANKINCREASE

            if neighbor == self.preferred_parent:
                self.rank = self._calculate_rank(self.preferred_parent)

    def _calculate_rank(self, neighbor):
        if (
                (neighbor is None)
                or
                (neighbor['advertised_rank'] is None)
                or
                (neighbor['rank_increase'] is None)
            ):
            return None
        elif neighbor['advertised_rank'] == self.INFINITE_RANK:
            # this neighbor should be ignored
            return None
        else:
            rank = neighbor['advertised_rank'] + neighbor['rank_increase']

            if rank > self.INFINITE_RANK:
                return self.INFINITE_RANK
            else:
                return rank

    def _update_preferred_parent(self):
        if (
                (self.preferred_parent is not None)
                and
                (self.preferred_parent['advertised_rank'] is not None)
                and
                (self.rank is not None)
                and
                (
                    (self.preferred_parent['advertised_rank'] - self.rank) <
                    d.RPL_PARENT_SWITCH_RANK_THRESHOLD
                )
                and
                (
                    self.preferred_parent['rank_increase'] <
                    self.PARENT_SWITCH_RANK_INCREASE_THRESHOLD
                )
            ):
            # stay with the current parent. the link to the parent is
            # good. but, if the parent rank is higher than us and the
            # difference is more than d.RPL_PARENT_SWITCH_RANK_THRESHOLD, we dump
            # the parent. otherwise, we may create a routing loop.
            return

        try:
            candidate = min(self.parents, key=self._calculate_rank)
            new_rank = self._calculate_rank(candidate)
        except ValueError:
            # self.parents is empty
            candidate = None
            new_rank = None

        if new_rank is None:
            # we don't have any available parent
            new_parent = None
        elif self.rank is None:
            new_parent = candidate
            self.rank = new_rank
        else:
            # (new_rank is not None) and (self.rank is None)
            rank_difference = self.rank - new_rank

            # Section 6.4, RFC 8180
            #
            #   Per [RFC6552] and [RFC6719], the specification RECOMMENDS the
            #   use of a boundary value (PARENT_SWITCH_RANK_THRESHOLD) to avoid
            #   constant changes of the parent when ranks are compared.  When
            #   evaluating a parent that belongs to a smaller path cost than
            #   the current minimum path, the candidate node is selected as the
            #   new parent only if the difference between the new path and the
            #   current path is greater than the defined
            #   PARENT_SWITCH_RANK_THRESHOLD.

            if rank_difference is not None:
                if d.RPL_PARENT_SWITCH_RANK_THRESHOLD < rank_difference:
                    new_parent = candidate
                    self.rank = new_rank
                else:
                    # no change on preferred parent
                    new_parent = self.preferred_parent

        if (
                (new_parent is not None)
                and
                (new_parent != self.preferred_parent)
            ):
            # change to the new preferred parent

            if self.preferred_parent is None:
                old_parent_mac_addr = None
            else:
                old_parent_mac_addr = self.preferred_parent['mac_addr']

            self.preferred_parent = new_parent
            if new_parent is None:
                new_parent_mac_addr = None
            else:
                new_parent_mac_addr = self.preferred_parent['mac_addr']

            self.rpl.indicate_preferred_parent_change(
                old_preferred = old_parent_mac_addr,
                new_preferred = new_parent_mac_addr
            )

            # reset Trickle Timer
            self.rpl.trickle_timer.reset()
        elif (
                (new_parent is None)
                and
                (self.preferred_parent is not None)
            ):
            old_parent_mac_addr = self.preferred_parent['mac_addr']
            self.neighbors = []
            self.preferred_parent = None
            self.rank = None
            self.rpl.indicate_preferred_parent_change(
                old_preferred = old_parent_mac_addr,
                new_preferred = None
            )
            self.rpl.local_repair()
        else:
            # do nothing
            pass
