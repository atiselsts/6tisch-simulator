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
        return self.of.get_rank()

    def getDagRank(self):
        return int(self.of.get_rank() / d.RPL_MINHOPRANKINCREASE)

    def addParentChildfromDAOs(self, parent_id, child_id):
        assert type(parent_id) is int
        assert type(child_id)  is int
        self.parentChildfromDAOs[child_id] = parent_id

    def getPreferredParent(self):
        # FIXME: when we implement IPv6 address or MAC address, we should
        # define the return type of this method. Currently, this method can
        # return a node ID, a MAC address, or an IPv6 address since they are
        # all the same value for a certain mote.
        return self.of.get_preferred_parent()

    # admin

    def start(self):
        if self.mote.dagRoot:
            self.of = RplOFNone(self)
            self.of.set_rank(d.RPL_MINHOPRANKINCREASE)
            self.trickle_timer.start()
            # now start a new RPL instance; reset the timer as per Section 8.3 of
            # RFC 6550
            self.trickle_timer.reset()
        else:
            # start sending DIS
            self._send_DIS()

    def indicate_tx(self, cell, dstMac, isACKed):
        self.of.update_etx(cell, dstMac, isACKed)

    def indicate_preferred_parent_change(self, old_preferred, new_preferred):
        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_CHURN,
            {
                "_mote_id":        self.mote.id,
                "rank":            self.of.get_rank(),
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

    # === DIS

    def action_receiveDIS(self, packet):
        if   packet['net']['dstIp'] == self.mote.id:
            # unicast DIS; send unicast DIO back to the source
            self._send_DIO(packet['net']['srcIp'])
        elif packet['net']['dstIp'] == d.BROADCAST_ADDRESS:
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
            cb             = self._send_DIS,
            uniqueTag      = str(self.mote.id) + 'dis',
            intraSlotOrder = d.INTRASLOTORDER_STACKTASKS
        )

    def _stop_dis_timer(self):
        self.engine.removeFutureEvent(str(self.mote.id) + 'dis')

    def _send_DIS(self):

        if   self.dis_mode == 'dis_unicast':
            dstIp = self.mote.tsch.join_proxy # possible parent
        elif self.dis_mode == 'dis_broadcast':
            dstIp = d.BROADCAST_ADDRESS
        elif self.dis_mode == 'disabled':
            return

        dis = {
            'type': d.PKT_TYPE_DIS,
            'net' : {
                'srcIp':         self.mote.id,
                'dstIp':         dstIp,
                'packet_length': d.PKT_LEN_DIS
            },
            'app' : {}
        }

        self.mote.sixlowpan.sendPacket(dis, link_local=True)
        self._start_dis_timer()

    # === DIO

    def _send_DIO(self, dstIp=None):
        dio = self._create_DIO(dstIp)

        # log
        self.log(
            SimEngine.SimLog.LOG_RPL_DIO_TX,
            {
                "_mote_id":  self.mote.id,
                "packet":    dio,
            }
        )

        self.mote.sixlowpan.sendPacket(dio, link_local=True)

    def _create_DIO(self, dstIp=None):

        assert self.mote.dodagId is not None

        if dstIp is None:
            dstIp = d.BROADCAST_ADDRESS

        # create
        newDIO = {
            'type':              d.PKT_TYPE_DIO,
            'app': {
                'rank':          self.of.get_rank(),
                'dodagId':       self.mote.dodagId,
            },
            'net': {
                'srcIp':         self.mote.id,  # from mote
                'dstIp':         dstIp,         # broadcast (in reality "all RPL routers")
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

        # record dodagId
        if self.mote.dodagId is None:
            # join the RPL network
            self.mote.dodagId = packet['app']['dodagId']
            self.trickle_timer.start()
            self.trickle_timer.reset()
            self._stop_dis_timer()

        # feed our OF with the received DIO
        self.of.update(packet)

    # === DAO

    def _schedule_sendDAO(self, firstDAO=False):
        """
        Schedule to send a DAO sometimes in the future.
        """

        assert self.mote.dagRoot is False

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
        if self.mote.clear_to_send_EBs_DATA()==False:
            return

        # create
        newDAO = {
            'type':                d.PKT_TYPE_DAO,
            'app': {
                'child_id':        self.mote.id,
                'parent_id':       self.of.get_preferred_parent()
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
        assert type(dest_id) is int

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

    def get_rank(self):
        return self.rank

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
    DEFAULT_STEP_OF_RANK = 3
    MINIMUM_STEP_OF_RANK = 1
    MAXIMUM_STEP_OF_RANK = 9
    PARENT_SWITCH_THRESHOLD = 640

    def __init__(self, rpl):
        self.rpl = rpl
        self.neighbors = []
        self.rank = None
        self.preferred_parent = None

    def update(self, dio):
        mac_addr = dio['mac']['srcMac']
        ip_addr = dio['net']['srcIp']
        rank = dio['app']['rank']

        # update neighbor's rank
        neighbor = self._find_neighbor_by_ip_addr(ip_addr)
        if neighbor is None:
            neighbor = self._add_neighbor(ip_addr, mac_addr)
        self._update_neighbor_rank(neighbor, rank)

        # change preferred parent if necessary
        self._update_preferred_parent()

    def get_rank(self):
        return self._calculate_rank(self.preferred_parent)

    def get_preferred_parent(self):
        if self.preferred_parent is None:
            return None
        else:
            # XXX: returning the IPv6 address of the preferred parent here is no
            # problem now since the value of an IPv6 address is the same as its
            # node ID.
            return self.preferred_parent['ip_addr']

    def update_etx(self, cell, mac_addr, isACKed):
        neighbor = self._find_neighbor_by_mac_addr(mac_addr)
        if neighbor is None:
            # we've not received DIOs from this neighbor; ignore the neighbor
            return
        elif (
                (cell['neighbor'] == mac_addr)
                and
                (d.CELLOPTION_TX in cell['cellOptions'])
                and
                (d.CELLOPTION_SHARED not in cell['cellOptions'])
            ):
            neighbor['numTx'] += 1
            if isACKed is True:
                neighbor['numTxAck'] += 1
            self._update_neighbor_rank_increase(neighbor)
            self._update_preferred_parent()

    def _add_neighbor(self, ip_addr, mac_addr):
        assert self._find_neighbor_by_ip_addr(ip_addr) is None
        assert self._find_neighbor_by_mac_addr(mac_addr) is None

        neighbor = {
            'ip_addr': ip_addr,
            'mac_addr': mac_addr,
            'advertised_rank': None,
            'rank_increase': None,
            'numTx': 0,
            'numTxAck': 0
        }
        self.neighbors.append(neighbor)
        self._update_neighbor_rank_increase(neighbor)
        return neighbor

    def _find_neighbor_by_ip_addr(self, ip_addr):
        for neighbor in self.neighbors:
            if neighbor['ip_addr'] == ip_addr:
                return neighbor
        return None

    def _find_neighbor_by_mac_addr(self, mac_addr):
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
            step_of_rank = self.DEFAULT_STEP_OF_RANK
        elif etx > self.UPPER_LIMIT_OF_ACCEPTABLE_ETX:
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

    def _calculate_rank(self, neighbor):
        if (
                (neighbor is None)
                or
                (neighbor['advertised_rank'] is None)
                or
                (neighbor['rank_increase'] is None)
            ):
            return self.INFINITE_RANK
        else:
            return neighbor['advertised_rank'] + neighbor['rank_increase']

    def _update_preferred_parent(self):
        candidate = min(self.neighbors, key=self._calculate_rank)
        rank_difference = self.get_rank() - self._calculate_rank(candidate)
        assert rank_difference >= 0

        # Section 6.4, RFC 8180
        #
        #   Per [RFC6552] and [RFC6719], the specification RECOMMENDS the use
        #   of a boundary value (PARENT_SWITCH_THRESHOLD) to avoid constant
        #   changes of the parent when ranks are compared.  When evaluating a
        #   parent that belongs to a smaller path cost than the current minimum
        #   path, the candidate node is selected as the new parent only if the
        #   difference between the new path and the current path is greater
        #   than the defined PARENT_SWITCH_THRESHOLD.
        if self.PARENT_SWITCH_THRESHOLD < rank_difference:
            # change to the new preferred parent
            if self.preferred_parent is None:
                old_parent_mac_addr = None
            else:
                old_parent_mac_addr = self.preferred_parent['mac_addr']
            self.preferred_parent = candidate
            self.rpl.indicate_preferred_parent_change(
                old_preferred = old_parent_mac_addr,
                new_preferred = self.preferred_parent['mac_addr']
            )
