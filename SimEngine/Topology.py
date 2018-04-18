"""
\Brief Wireless network topology creator module

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
"""

# =========================== imports =========================================

from abc import ABCMeta, abstractmethod
import logging
import math
import random

from k7 import k7

import SimSettings
import Propagation
import Mote

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

# =========================== logging =========================================

log = logging.getLogger('Topology')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

# =========================== defines =========================================

TOP_TYPE_ALL = ['linear', 'twoBranch', 'random']

# =========================== body ============================================

class Topology(object):

    def __new__(cls, motes):
        settings = SimSettings.SimSettings()
        if   settings.top_type == 'linear':
            return LinearTopology(motes)
        elif settings.top_type == 'twoBranch':
            return TwoBranchTopology(motes)
        elif settings.top_type == 'trace':
            return TraceTopology(motes, settings.prop_trace)
        elif settings.top_type == 'random':
            return RandomTopology(motes)
        else:
            raise SystemError()

    @classmethod
    def rssiToPdr(cls, rssi):
        settings = SimSettings.SimSettings()
        if   settings.top_type   == 'linear':
            return LinearTopology.rssiToPdr(rssi)
        elif settings.top_type == 'twoBranch':
            return TwoBranchTopology.rssiToPdr(rssi)
        elif settings.top_type == 'random':
            return RandomTopology.rssiToPdr(rssi)
        else:
            raise SystemError()


class TopologyCreator:

    __metaclass__ = ABCMeta

    PISTER_HACK_LOWER_SHIFT = 40   # dB
    TWO_DOT_FOUR_GHZ = 2400000000  # Hz
    SPEED_OF_LIGHT = 299792458     # m/s

    @abstractmethod
    def __init__(self, motes):
        pass

    @abstractmethod
    def createTopology(self):
        pass

    @abstractmethod
    def rssiToPdr(cls, rssi):
        pass

    def _computeRSSI(self, mote, neighbor):
        """
        computes RSSI between any two nodes (not only neighbors)
        according to the Pister-hack model.
        """

        # distance in m
        distance = self._computeDistance(mote, neighbor)

        # sqrt and inverse of the free space path loss
        fspl = (self.SPEED_OF_LIGHT/(4*math.pi*distance*self.TWO_DOT_FOUR_GHZ))

        # simple friis equation in Pr=Pt+Gt+Gr+20log10(c/4piR)
        pr = (mote.txPower + mote.antennaGain + neighbor.antennaGain +
              (20 * math.log10(fspl)))

        # according to the receiver power (RSSI) we can apply the Pister hack
        # model.
        mu = pr - self.PISTER_HACK_LOWER_SHIFT / 2  # chosing the "mean" value

        # the receiver will receive the packet with an rssi uniformly
        # distributed between friis and friis -40
        rssi = (mu +
                random.uniform(-self.PISTER_HACK_LOWER_SHIFT/2,
                               self.PISTER_HACK_LOWER_SHIFT/2))

        return rssi

    def _computePDR(self, mote, neighbor):
        """computes pdr to neighbor according to RSSI"""

        rssi = mote.getRSSI(neighbor)
        return self.rssiToPdr(rssi)

    def _computeDistance(self, mote, neighbor):
        """
        mote.x and mote.y are in km. This function returns the distance in m.
        """

        return 1000*math.sqrt((mote.x - neighbor.x)**2 +
                              (mote.y - neighbor.y)**2)


class RandomTopology(TopologyCreator):

    # dBm, corresponds to PDR = 0.5 (see rssiPdrTable below)
    STABLE_RSSI = -93.6
    STABLE_NEIGHBORS = 3
    # (hack) small value to speed up the construction of fully-meshed topology
    FULLY_MESHED_SQUARE_SIDE = 0.005

    def __init__(self, motes):
        # store params
        self.motes = motes
        self.shape = 'random'

        # local variables
        self.settings = SimSettings.SimSettings()

        # if top_fullyMeshed is enabled, create a topology where each node has N-1
        # stable neighbors
        if self.settings.top_fullyMeshed:
            self.stable_neighbors = len(self.motes) - 1
            self.squareSide = self.FULLY_MESHED_SQUARE_SIDE
        else:
            self.stable_neighbors = self.STABLE_NEIGHBORS
            self.squareSide = self.settings.top_squareSide

    def createTopology(self):
        """
        Create a topology in which all nodes have at least
        stable_neighbors link with enough RSSI.
        If the mote does not have stable_neighbors links with enough RSSI,
        reset the location of the mote.
        """

        # find DAG root
        dagRoot = None
        for mote in self.motes:
            if mote.id == 0:
                mote.role_setDagRoot()
                dagRoot = mote
        assert dagRoot

        # put DAG root at center of area
        dagRoot.setLocation(x=self.squareSide/2,
                            y=self.squareSide/2)

        # reposition each mote until it is connected
        connectedMotes = [dagRoot]
        for mote in self.motes:
            if mote in connectedMotes:
                continue

            connected = False
            while not connected:
                # pick a random location
                mote.setLocation(x=self.squareSide*random.random(),
                                 y=self.squareSide*random.random())

                numStableNeighbors = 0

                # count number of neighbors with sufficient RSSI
                for cm in connectedMotes:

                    rssi = self._computeRSSI(mote, cm)
                    mote.setRSSI(cm, rssi)
                    cm.setRSSI(mote, rssi)

                    if rssi > self.STABLE_RSSI:
                        numStableNeighbors += 1

                # make sure it is connected to at least stable_neighbors motes
                # or connected to all the currently deployed motes when the
                # number of deployed motes are smaller than stable_neighbors
                if (numStableNeighbors >= self.stable_neighbors or
                   numStableNeighbors == len(connectedMotes)):
                    connected = True

            connectedMotes += [mote]

        # for each mote, compute PDR to each neighbors
        for mote in self.motes:
            for m in self.motes:
                if mote == m:
                    continue
                if mote.getRSSI(m) > mote.propagation.minRssi:
                    pdr = self._computePDR(mote, m)
                    mote.setPDR(m, pdr)
                    m.setPDR(mote, pdr)

    @classmethod
    def rssiToPdr(cls, rssi):
        """

        rssi and pdr relationship obtained by experiment below
        http://wsn.eecs.berkeley.edu/connectivity/?dataset=dust

        :param rssi:
        :return:
        :rtype: float
        """

        rssiPdrTable = {
            -97:    0.0000,  # this value is not from experiment
            -96:    0.1494,
            -95:    0.2340,
            -94:    0.4071,
            # <-- 50% PDR is here, at RSSI=-93.6
            -93:    0.6359,
            -92:    0.6866,
            -91:    0.7476,
            -90:    0.8603,
            -89:    0.8702,
            -88:    0.9324,
            -87:    0.9427,
            -86:    0.9562,
            -85:    0.9611,
            -84:    0.9739,
            -83:    0.9745,
            -82:    0.9844,
            -81:    0.9854,
            -80:    0.9903,
            -79:    1.0000,  # this value is not from experiment
        }

        minRssi = min(rssiPdrTable.keys())
        maxRssi = max(rssiPdrTable.keys())

        if  rssi < minRssi:
            pdr = 0.0
        elif rssi > maxRssi:
            pdr = 1.0
        else:
            floorRssi = int(math.floor(rssi))
            pdrLow    = rssiPdrTable[floorRssi]
            pdrHigh   = rssiPdrTable[floorRssi+1]
            # linear interpolation
            pdr       = (pdrHigh - pdrLow) * (rssi - float(floorRssi)) + pdrLow

        assert pdr >= 0.0
        assert pdr <= 1.0

        return pdr

class LinearTopology(TopologyCreator):

    COMM_RANGE_RADIUS = 50

    def __init__(self, motes):

        self.motes = motes
        self.shape = 'linear'
        self.settings = SimSettings.SimSettings()

    def createTopology(self):

        # place motes on a line at every 30m
        # coordinate of mote is expressed in km
        gap = 0.030
        for m in self.motes:
            if m.id == 0:
                m.role_setDagRoot()
            m.x = gap * m.id
            m.y = 0

        for mote in self.motes:

            # clear RSSI and PDR table; we may need clearRSSI and clear PDR
            # methods
            mote.RSSI = {}
            mote.PDR = {}

            for neighbor in self.motes:
                if mote == neighbor:
                    continue
                mote.setRSSI(neighbor, self._computeRSSI(mote, neighbor))
                pdr = self._computePDR(mote, neighbor)
                if(pdr > 0):
                    mote.setPDR(neighbor, pdr)

        if not self.settings.secjoin_enabled:
            self._build_rpl_tree()

    @classmethod
    def rssiToPdr(cls, rssi):
        # This is for test purpose; PDR is 1.0 for -93 and above, otherwise PDR
        # is 0.0.
        rssiPdrTable = {
            -95: 0.0,
            -94: 1.0,
        }

        minRssi = min(rssiPdrTable.keys())
        maxRssi = max(rssiPdrTable.keys())

        if rssi < minRssi:
            pdr = 0.0
        elif rssi > maxRssi:
            pdr = 1.0
        else:
            pdr = rssiPdrTable[int(math.floor(rssi))]

        assert pdr >= 0.0
        assert pdr <= 1.0

        return pdr

    def _computeRSSI(self, mote, neighbor):
        if self._computeDistance(mote, neighbor) < self.COMM_RANGE_RADIUS:
            return -80
        else:
            return -100

    def _computePDR(self, mote, neighbor):
        return self.rssiToPdr(self._computeRSSI(mote, neighbor))

    def _build_rpl_tree(self):
        root = None
        for mote in self.motes:
            if mote.id == 0:
                mote.role_setDagRoot()
                root = mote
                mote.rank = Mote.Mote.RPL_MIN_HOP_RANK_INCREASE
            else:
                # mote with smaller ID becomes its preferred parent
                for neighbor in mote.PDR:
                    if ((not mote.preferredParent) or
                       (neighbor.id < mote.preferredParent.id)):
                        mote.preferredParent = neighbor
                root.parents.update({tuple([mote.id]):
                                     [[mote.preferredParent.id]]})
                mote.rank = (7 * Mote.Mote.RPL_MIN_HOP_RANK_INCREASE +
                             mote.preferredParent.rank)

            mote.dagRank = mote.rank / Mote.Mote.RPL_MIN_HOP_RANK_INCREASE

class TwoBranchTopology(TopologyCreator):

    COMM_RANGE_RADIUS = 50

    def __init__(self, motes):
        self.motes = motes
        self.shape = 'twoBranch'
        self.settings = SimSettings.SimSettings()
        self.depth = int(math.ceil((float(len(self.motes)) - 2) / 2) + 1)
        if len(self.motes) < 2:
            self.switch_to_right_branch = 2
        else:
            self.switch_to_right_branch = self.depth + 1

    def createTopology(self):
        # place motes on a line at every 30m
        # coordinate of mote is expressed in km
        gap = 0.030

        for m in self.motes:
            if m.id == 0:
                m.role_setDagRoot()

            if m.id < self.switch_to_right_branch:
                m.x = gap * m.id
            else:
                m.x = gap * (m.id - self.switch_to_right_branch + 2)

            if m.id < 2:
                m.y = 0
            elif m.id < self.switch_to_right_branch:
                m.y = -0.03
            else:
                m.y = 0.03

        for mote in self.motes:
            # clear RSSI and PDR table; we may need clearRSSI and clearPDR methods
            mote.RSSI = {}
            mote.PDR = {}

            for neighbor in self.motes:
                if mote == neighbor:
                    continue
                mote.setRSSI(neighbor, self._computeRSSI(mote, neighbor))
                pdr = self._computePDR(mote, neighbor)
                if(pdr > 0):
                    mote.setPDR(neighbor, pdr)

        if not self.settings.secjoin_enabled:
            self._build_rpl_tree()

    @classmethod
    def rssiToPdr(cls, rssi):
        # This is for test purpose; PDR is 1.0 for -93 and above, otherwise PDR
        # is 0.0.
        rssiPdrTable = {
            -95: 0.0,
            -94: 1.0,
        }

        minRssi = min(rssiPdrTable.keys())
        maxRssi = max(rssiPdrTable.keys())

        if rssi < minRssi:
            pdr = 0.0
        elif rssi > maxRssi:
            pdr = 1.0
        else:
            pdr = rssiPdrTable[int(math.floor(rssi))]

        assert pdr >= 0.0
        assert pdr <= 1.0

        return pdr

    def _computeRSSI(self, mote, neighbor):
        if self._computeDistance(mote, neighbor) < self.COMM_RANGE_RADIUS:
            return -80
        else:
            return -100

    def _computePDR(self, mote, neighbor):
        """

        :param Mote mote:
        :param Mote neighbor:
        :return:
        :rtype: float
        """
        return self.rssiToPdr(self._computeRSSI(mote, neighbor))

    def _build_rpl_tree(self):
        root = None
        for mote in self.motes:
            if mote.id == 0:
                mote.role_setDagRoot()
                root = mote
            else:
                # mote with smaller ID becomes its preferred parent
                for neighbor in mote.PDR:
                    if (not mote.preferredParent or
                       neighbor.id < mote.preferredParent.id):
                        mote.preferredParent = neighbor
                root.parents.update({tuple([mote.id]):
                                     [[mote.preferredParent.id]]})

            if mote.id == 0:
                mote.rank = Mote.Mote.RPL_MIN_HOP_RANK_INCREASE
            else:
                mote.rank = (7 * Mote.Mote.RPL_MIN_HOP_RANK_INCREASE +
                             mote.preferredParent.rank)
            mote.dagRank = mote.rank / Mote.Mote.RPL_MIN_HOP_RANK_INCREASE

    def _install_symmetric_schedule(self):
        # allocate TX cells for each node to its parent, which has the same
        # channel offset, 0.
        tx_alloc_factor = 1

        for mote in self.motes:
            if mote.preferredParent:
                if mote.id == 1:
                    slot_offset = len(self.motes) - 1
                elif mote.id < self.switch_to_right_branch:
                    slot_offset = (self.depth - mote.id) * 2 + 1
                elif len(self.motes) % 2 == 0: # even branches
                    slot_offset = (self.depth +
                                   self.switch_to_right_branch -
                                   1 - mote.id) * 2
                else:
                    slot_offset = (self.depth - 1 +
                                   self.switch_to_right_branch - 1 -
                                   mote.id) * 2

                Mote.sf.alloc_cell(mote,
                              mote.preferredParent,
                              int(slot_offset),
                              0)

    def _install_cascading_schedule(self):
        # allocate TX cells and RX cells in a cascading bandwidth manner.

        for mote in self.motes[::-1]: # loop in the reverse order
            child = mote
            while child and child.preferredParent:
                if self.settings.top_schedulingMode == 'random-pick':
                    if 'alloc_table' not in locals():
                        alloc_table = set()

                    if len(alloc_table) >= self.settings.tsch_slotframeLength:
                        raise ValueError('slotframe is too small')

                    while True:
                        # we don't use slot-0 since it's designated for a shared cell
                        alloc_pointer = random.randint(1,
                                                       self.settings.tsch_slotframeLength - 1)
                        if alloc_pointer not in alloc_table:
                            alloc_table.add(alloc_pointer)
                            break
                else:
                    if 'alloc_pointer' not in locals():
                        alloc_pointer = 1
                    else:
                        alloc_pointer += 1

                    if alloc_pointer > self.settings.tsch_slotframeLength:
                        raise ValueError('slotframe is too small')

                Mote.sf.alloc_cell(child,
                              child.preferredParent,
                              alloc_pointer,
                              0)
                child = child.preferredParent

class TraceTopology(TopologyCreator):

    def __init__(self, motes, trace):
        log.debug("Init Topology from trace file.")
        self.trace = trace
        self.shape = "trace"
        self.motes = motes
        self.settings = SimSettings.SimSettings()
        self.propagation = Propagation.Propagation()

    def createTopology(self):
        # read first transaction from trace
        header, trace = k7.read(self.trace)
        first_transaction = trace[(trace.transaction_id == trace.transaction_id.min()) &
                                  (trace.channels == "11-26") &
                                  (trace.pdr > 0)]

        # build graph
        nodes = list(set().union(first_transaction.src.unique(),
                                 first_transaction.dst.unique()))
        log.debug("Selected nodes: {0}".format(nodes))

        # set motes ids
        for i, mote in enumerate(self.motes):
            mote.id = nodes[i]  # replace mote id by trace id

        # select first mote as DagRoot
        self.motes[0].role_setDagRoot()
        log.debug("DagRoot selected, id: {0}".format(self.motes[0].id))

        # for each mote, compute PDR and RSSI to each neighbors
        for source in self.motes:
            # clear RSSI and PDR table; we may need clearRSSI and clear PDR
            # methods
            mote.RSSI = {}
            mote.PDR = {}

            for destination in self.motes:
                if source == destination:
                    continue
                # source -> destination
                pdr = self._computePDR(source, destination)
                source.setPDR(destination, pdr)
                rssi = self._computeRSSI(source, destination)
                source.setRSSI(destination, rssi)

        # randomly place motes
        for mote in self.motes:
            # pick a random location
            mote.setLocation(x=self.settings.top_squareSide * random.random(),
                             y=self.settings.top_squareSide * random.random())

        log.debug("Topology Created.")

    def _computePDR(self, source, destination):
        return self.propagation.get_pdr(source, destination)

    def _computeRSSI(self, source, destination):
        return self.propagation.get_rssi(source, destination)

    def rssiToPdr(cls, rssi):
        raise NotImplementedError
