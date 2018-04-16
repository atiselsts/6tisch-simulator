"""
This Module contains the scheduling functions and helpers to install
static schedules
"""

# =========================== imports =========================================

import math
import random
from abc import abstractmethod

import SimEngine
import Mote
import MoteDefines as d

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('sf')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

SF_TYPE_ALL = ['MSF', 'SSF-symmetric', 'SSF-cascading']

# =========================== helpers =========================================

def init(topology, scheduling_function):
    """ This function initiate the scheduling function
    :param Topology topology:
    :param str scheduling_function:
    :return: None
    """
    if scheduling_function == 'SSF-cascading':
        if topology.shape == 'linear':
            _ssf_linear_cascading_schedule(topology)
        elif topology.shape == 'twoBranch':
            _ssf_twobranch_cascading_schedule(topology)
    elif scheduling_function == 'SSF-symmetric':
        if topology.shape == 'linear':
            _ssf_linear_symmetric_schedule(topology)
        elif topology.shape == 'twoBranch':
            _ssf_twobranch_symmetric_schedule(topology)

    if scheduling_function in ['SSF-cascading', 'SSF-symmetric']:
        # make all the motes synchronized
        for mote in topology.motes:
            mote.timeCorrectedSlot = 0

#--- private helpers

def _alloc_cell(transmitter, receiver, slot_offset, channel_offset):
    """
    Allocate cells between two motes
    :param Mote transmitter:
    :param Mote receiver:
    :param int slot_offset:
    :param int channel_offset:
    :return: None
    """

    # cell structure: (slot_offset, channel_offset, direction)
    transmitter._tsch_addCells(receiver,
                               [(slot_offset,
                                 channel_offset,
                                 d.DIR_TX)])
    if receiver not in transmitter.numCellsToNeighbors:
        transmitter.numCellsToNeighbors[receiver] = 1
    else:
        transmitter.numCellsToNeighbors[receiver] += 1

    receiver._tsch_addCells(transmitter,
                            [(slot_offset,
                              channel_offset,
                              d.DIR_RX)])
    if transmitter not in receiver.numCellsFromNeighbors:
        receiver.numCellsFromNeighbors[transmitter] = 1
    else:
        receiver.numCellsFromNeighbors[transmitter] += 1

def _ssf_linear_cascading_schedule(topology):
    alloc_pointer = 1  # start allocating with slot-1

    for mote in topology.motes[::-1]:  # loop in the reverse order
        child = mote
        while child and child.preferredParent:
            _alloc_cell(child, child.preferredParent, alloc_pointer, 0)
            alloc_pointer += 1
            child = child.preferredParent

def _ssf_linear_symmetric_schedule(topology):
    # find the edge node in the given linear topology
    depth = len(topology.motes)
    for mote in topology.motes:
        if mote.preferredParent:
            _alloc_cell(mote, mote.preferredParent, depth - mote.id, 0)

def _ssf_twobranch_symmetric_schedule(topology):
    # allocate TX cells for each node to its parent, which has the same
    # channel offset, 0.

    for mote in topology.motes:
        if mote.preferredParent:
            if mote.id == 1:
                slot_offset = len(topology.motes) - 1
            elif mote.id < topology.switch_to_right_branch:
                slot_offset = (topology.depth - mote.id) * 2 + 1
            elif len(topology.motes) % 2 == 0:  # even branches
                slot_offset = (topology.depth +
                               topology.switch_to_right_branch -
                               1 - mote.id) * 2
            else:
                slot_offset = (topology.depth - 1 +
                               topology.switch_to_right_branch - 1 -
                               mote.id) * 2

            _alloc_cell(mote, mote.preferredParent, int(slot_offset), 0)

def _ssf_twobranch_cascading_schedule(self):
    # allocate TX cells and RX cells in a cascading bandwidth manner.

    alloc_pointer = 0
    for mote in self.motes[::-1]:  # loop in the reverse order
        child = mote
        while child and child.preferredParent:
            if self.settings.sf_ssf_initMethod == 'random-pick':
                if 'alloc_table' not in locals():
                    alloc_table = set()

                if len(alloc_table) >= self.settings.tsch_slotframeLength:
                    raise ValueError('slotframe is too small')

                while True:
                    # we don't use slot-0 since it's designated for a shared cell
                    alloc_pointer = random.randint(1, self.settings.tsch_slotframeLength - 1)
                    if alloc_pointer not in alloc_table:
                        alloc_table.add(alloc_pointer)
                        break
            else:
                alloc_pointer += 1

                if alloc_pointer > self.settings.tsch_slotframeLength:
                    raise ValueError('slotframe is too small')

            _alloc_cell(child, child.preferredParent, alloc_pointer, 0)
            child = child.preferredParent

# =========================== body ============================================

class SchedulingFunction(object):
    """
    This class is instantiated by each mote.
    """

    def __init__(self):

        self.settings = SimEngine.SimSettings.SimSettings()
        self.engine = SimEngine.SimEngine.SimEngine()

    @classmethod
    def get_sf(cls, scheduling_function):
        if scheduling_function == "SSF-cascading":
            return Static()
        elif scheduling_function == "SSF-symmetric":
            return Static()
        else:
            return MSF()

    @abstractmethod
    def schedule_parent_change(self, mote):
        """ Schedule parent change
        :param Mote mote:
        """
        raise NotImplementedError

    @abstractmethod
    def signal_cell_elapsed(self, mote, neighbor, direction):
        """
        :param Mote mote:
        :param Mote neighbor:
        :param direction:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    def signal_cell_used(self, mote, neighbor, cellOptions, direction=None, celltype=None):
        """
        :param Mote mote:
        :param Mote neighbor:
        :param cellOptions:
        :param direction:
        :param celltype:
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    def housekeeping(self, mote):
        raise NotImplementedError

class MSF(SchedulingFunction):

    MIN_NUM_CELLS = 5
    DEFAULT_TIMEOUT_EXP = 1
    MAX_TIMEOUT_EXP = 4
    DEFAULT_SIXTOP_TIMEOUT = 15
    SIXP_TIMEOUT_SEC_FACTOR = 3

    def __init__(self):
        super(MSF, self).__init__()
        self.msfTimeoutExp = {}

    def schedule_parent_change(self, mote):
        """
          Schedule MSF parent change
        """
        self.engine.scheduleAtAsn(
            asn         = int(self.engine.asn + (1 + self.settings.tsch_slotframeLength * 16 * random.random())),
            cb          = self.action_parent_change,
            uniqueTag   = (mote.id, 'action_parent_change'),
            priority    = 4,
            kwargs      = {'mote': mote}
        )

    def action_parent_change(self, mote):
        """
          Trigger MSF parent change:
              Add the same number of cells to the new parent as we had with the old one.
          In the case of bootstrap, add one cell to the preferred parent.
        """

        assert mote.preferredParent

        armTimeout = False

        celloptions = d.DIR_TXRX_SHARED

        if mote.numCellsToNeighbors.get(mote.preferredParent, 0) == 0:

            timeout = self.get_sixtop_timeout(mote, mote.preferredParent)

            log.info("[msf] triggering 6P ADD of {0} cells, dir {1}, to mote {2}, 6P timeout {3}".format(
                        self.settings.sf_msf_numCellsToAddRemove, celloptions,
                        mote.preferredParent.id, timeout))

            mote.sixtop_ADD_REQUEST(
                mote.preferredParent,
                mote.numCellsToNeighbors.get(
                    mote.oldPreferredParent,
                    1),  # request at least one cell
                celloptions,
                timeout)

            armTimeout = True

        if mote.numCellsToNeighbors.get(mote.oldPreferredParent, 0) > 0 and \
                mote.numCellsToNeighbors.get(mote.preferredParent, 0) > 0:

            timeout = self.get_sixtop_timeout(mote, mote.oldPreferredParent)

            log.info("[msf] triggering 6P ADD of {0} cells, dir {1}, to mote {2}, 6P timeout {3}".format(
                        self.settings.sf_msf_numCellsToAddRemove, celloptions, mote.oldPreferredParent.id, timeout))

            mote.sixtop_DELETE_REQUEST(
                mote.oldPreferredParent,
                mote.numCellsToNeighbors.get(
                    mote.oldPreferredParent,
                    0),
                celloptions,
                timeout)

            armTimeout = True

        if armTimeout:
            self.engine.scheduleIn(
                delay       = 300,
                cb          = self.action_parent_change,
                uniqueTag   = (mote.id, 'action_parent_change_retransmission'),
                priority    = 4,
                kwargs      = {'mote': mote}
            )
        else:
            assert mote.numCellsToNeighbors.get(mote.preferredParent, 0)
            # upon success, invalidate old parent
            mote.oldPreferredParent = None

    def get_sixtop_timeout(self, mote, neighbor):
        """
          calculate the timeout to a neighbor according to MSF
        """
        cellPDR = []
        for (ts, cell) in mote.schedule.iteritems():
            if (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TX) or\
                    (cell['dir'] == d.DIR_TXRX_SHARED and cell['neighbor'] == neighbor):
                cellPDR.append(mote.getCellPDR(cell))

        log.info('[sixtop] timeout() cellPDR = {0}'.format(cellPDR))

        if len(cellPDR) > 0:
            meanPDR = sum(cellPDR) / float(len(cellPDR))
            assert meanPDR <= 1.0
            timeout = math.ceil((
                float(mote.settings.tsch_slotframeLength * mote.settings.tsch_slotDuration) /
                float(len(cellPDR))) * (float(1 / meanPDR)) * self.SIXP_TIMEOUT_SEC_FACTOR)
            return timeout
        else:
            return self.DEFAULT_SIXTOP_TIMEOUT

    def signal_cell_used(self, mote, neighbor, cellOptions, direction=None, celltype=None):
        assert cellOptions in [d.DIR_TXRX_SHARED, d.DIR_TX, d.DIR_RX]
        assert direction in [d.DIR_TX, d.DIR_RX]
        assert celltype is not None

        # MSF: updating numCellsUsed
        if cellOptions == d.DIR_TXRX_SHARED and neighbor == mote.preferredParent:
            log.info('[msf] signal_cell_used: neighbor {0} direction {1} type {2} preferredParent = {3}'.format(
                        neighbor.id, direction, celltype, mote.preferredParent.id))
            mote.numCellsUsed += 1

    def signal_cell_elapsed(self, mote, neighbor, direction):

        assert mote.numCellsElapsed <= self.settings.sf_msf_maxNumCells
        assert direction in [d.DIR_TXRX_SHARED, d.DIR_TX, d.DIR_RX]

        # MSF: updating numCellsElapsed
        if direction == d.DIR_TXRX_SHARED and neighbor == mote.preferredParent:
            mote.numCellsElapsed += 1

            if mote.numCellsElapsed == self.settings.sf_msf_maxNumCells:
                log.info('[msf] signal_cell_elapsed: numCellsElapsed = {0}, numCellsUsed = {1}'.format(
                             mote.numCellsElapsed, mote.numCellsUsed))

                if   mote.numCellsUsed > self.settings.sf_msf_highUsageThres:
                    self.schedule_bandwidth_increment(mote)
                elif mote.numCellsUsed < self.settings.sf_msf_lowUsageThres:
                    self.schedule_bandwidth_decrement(mote)
                self.reset_counters(mote)

    @staticmethod
    def reset_counters(mote):
        mote.numCellsElapsed = 0
        mote.numCellsUsed = 0

    def reset_timeout_exponent(self, neighborId, firstTime):
        """
          reset current exponent according to MSF
          it can be reset or doubled
        """
        if firstTime:
            self.msfTimeoutExp[neighborId] = self.MAX_TIMEOUT_EXP-1
        else:
            self.msfTimeoutExp[neighborId] = self.DEFAULT_TIMEOUT_EXP

    def increase_timeout_exponent(self, neighborId):
        """
          update current exponent according to MSF
          it can be reset or doubled
        """
        if self.msfTimeoutExp[neighborId] < self.MAX_TIMEOUT_EXP:
            self.msfTimeoutExp[neighborId] += 1

    def schedule_bandwidth_increment(self, mote):
        """
          Schedule MSF bandwidth increment
        """
        self.engine.scheduleAtAsn(
            asn         = int(self.engine.asn + 1),
            cb          = self.action_bandwidth_increment,
            uniqueTag   = (mote.id, 'action_bandwidth_increment'),
            priority    = 4,
            kwargs      = {'mote': mote}
        )

    def action_bandwidth_increment(self, mote):
        """
          Trigger 6P to add self.settings.sf_msf_numCellsToAddRemove cells to preferred parent
        """
        timeout = self.get_sixtop_timeout(mote, mote.preferredParent)
        celloptions = d.DIR_TXRX_SHARED
        log.info("[msf] triggering 6P ADD of {0} cells, dir {1}, to mote {2}, 6P timeout {3}".format(
                 self.settings.sf_msf_numCellsToAddRemove, d.DIR_TXRX_SHARED, mote.preferredParent.id, timeout))
        mote.sixtop_ADD_REQUEST(mote.preferredParent,
                                              self.settings.sf_msf_numCellsToAddRemove,
                                              celloptions,
                                              timeout)

    def schedule_bandwidth_decrement(self, mote):
        """
          Schedule MSF bandwidth decrement
        """
        self.engine.scheduleAtAsn(
            asn         = int(self.engine.asn + 1),
            cb          = self.action_bandwidth_decrement,
            uniqueTag   = (mote.id, 'action_bandwidth_decrement'),
            priority    = 4,
            kwargs      = {'mote': mote}
        )

    def action_bandwidth_decrement(self, mote):
        """
          Trigger 6P to remove self.settings.sf_msf_numCellsToAddRemove cells from preferred parent
        """
        # ensure at least one dedicated cell is kept with preferred parent
        if mote.numCellsToNeighbors.get(mote.preferredParent, 0) > 1:
            timeout = self.get_sixtop_timeout(mote, mote.preferredParent)
            celloptions = d.DIR_TXRX_SHARED
            log.info("[msf] triggering 6P REMOVE of {0} cells, dir {1}, to mote {2}, 6P timeout {3}".format(
                        self.settings.sf_msf_numCellsToAddRemove,
                        d.DIR_TXRX_SHARED, mote.preferredParent.id, timeout))

            # trigger 6p to remove self.settings.sf_msf_numCellsToAddRemove cells
            mote.sixtop_DELETE_REQUEST(mote.preferredParent,
                                     self.settings.sf_msf_numCellsToAddRemove,
                                     celloptions,
                                     timeout)

    def housekeeping(self, mote):

        self.engine.scheduleIn(
            delay       = self.settings.sf_msf_housekeepingPeriod*(0.9+0.2*random.random()),
            cb          = self.action_housekeeping,
            uniqueTag   = (mote.id, 'action_housekeeping'),
            priority    = 4,
            kwargs      = {'mote': mote}
        )

    def action_housekeeping(self, mote):
        """
        MSF housekeeping: decides when to relocate cells
        """
        if mote.dagRoot:
            return

        # TODO MSF relocation algorithm

        # schedule next housekeeping
        self.housekeeping(mote)

class Static(SchedulingFunction):
    def __init__(self):
        super(Static, self).__init__()

    def schedule_parent_change(self, mote):
        pass

    def signal_cell_elapsed(self, mote, neighbor, direction):
        # ignore signal
        pass

    def signal_cell_used(self, mote, neighbor, cellOptions, direction=None, celltype=None):
        # ignore signal
        pass

    def housekeeping(self, mote):
        # ignore housekeeping
        pass
