
# =========================== imports =========================================

import sys
import math
import random
from abc import abstractmethod

import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SchedulingFunction(object):
    
    def __init__(self, mote):
        
        # store params
        self.mote            = mote
        
        # singletons (to access quicker than recreate every time)
        self.settings        = SimEngine.SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine.SimEngine()
        self.log             = SimEngine.SimLog.SimLog().log
        
        # local variables
        self.numCellsElapsed = 0
        self.numCellsUsed    = 0

    def activate(self):
        self.housekeeping()

    @classmethod
    def get_sf(cls, mote):
        settings = SimEngine.SimSettings.SimSettings()
        return getattr(sys.modules[__name__], settings.sf_type)(mote)

    @abstractmethod
    def schedule_parent_change(self, mote):
        raise NotImplementedError()

    @abstractmethod
    def signal_cell_elapsed(self, mote, neighbor, direction):
        raise NotImplementedError()

    @abstractmethod
    def signal_cell_used(self, mote, neighbor, cellOptions, direction=None, celltype=None):
        raise NotImplementedError()

    @abstractmethod
    def housekeeping(self):
        raise NotImplementedError()

class SFNone(SchedulingFunction):
    
    def __init__(self, mote):
        super(SFNone, self).__init__(mote)

    def schedule_parent_change(self, mote):
        pass

    def signal_cell_elapsed(self, mote, neighbor, direction):
        pass

    def signal_cell_used(self, mote, neighbor, cellOptions, direction=None, celltype=None):
        pass

    def housekeeping(self):
        pass

class MSF(SchedulingFunction):

    MIN_NUM_CELLS            = 5
    DEFAULT_TIMEOUT_EXP      = 1
    MAX_TIMEOUT_EXP          = 4
    DEFAULT_SIXTOP_TIMEOUT   = 15
    SIXP_TIMEOUT_SEC_FACTOR  = 3

    def __init__(self, mote):
        # intialize parent class
        super(MSF, self).__init__(mote)
        
        # (additional) local variables
        self.msfTimeoutExp = {}

    def schedule_parent_change(self, mote):
        
        self.engine.scheduleAtAsn(
            asn              = int(self.engine.asn + (1 + self.settings.tsch_slotframeLength * 16 * random.random())),
            cb               = self._action_parent_change,
            uniqueTag        = (mote.id, '_action_parent_change'),
            intraSlotOrder   = 4,
        )

    def _action_parent_change(self):
        
        return # FIXME: enable SIXP
        
        assert self.mote.rpl.getPreferredParent()!=None

        armTimeout = False

        celloptions = d.DIR_TXRX_SHARED

        if self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) == 0:

            timeout = self.get_sixtop_timeout(self.mote, self.mote.rpl.getPreferredParent())

            self.mote.sixp.issue_ADD_REQUEST(
                self.mote.rpl.getPreferredParent(),
                self.mote.numCellsToNeighbors.get(
                    self.mote.rpl.getOldPreferredParent(),
                    1, # request at least one cell
                ),
                celloptions,
                timeout,
            )

            armTimeout = True

        if self.mote.numCellsToNeighbors.get(self.mote.rpl.getOldPreferredParent(), 0) > 0 and \
                self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) > 0:

            timeout = self.get_sixtop_timeout(self.mote, self.mote.rpl.getOldPreferredParent())

            # log
            self.log(
                SimEngine.SimLog.LOG_6TOP_ADD_CELL,
                {
                    'cell_count': self.settings.sf_msf_numCellsToAddDelete,
                    'cell_options': celloptions,
                    'neighbor': self.mote.rpl.getOldPreferredParent().id,
                    'timeout': timeout
                }
            )

            self.mote.sixp.issue_DELETE_REQUEST(
                self.mote.rpl.getOldPreferredParent(),
                self.mote.numCellsToNeighbors.get(
                    self.mote.rpl.getOldPreferredParent(),
                    0),
                celloptions,
                timeout)

            armTimeout = True

        if armTimeout:
            self.engine.scheduleIn(
                delay             = 300,
                cb                = self._action_parent_change,
                uniqueTag         = (self.mote.id, 'action_parent_change_retransmission'),
                intraSlotOrder    = 4,
            )
        else:
            assert self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0)
            # upon success, invalidate old parent
            self.mote.rpl.setOldPreferredParent(None)

    def get_sixtop_timeout(self, mote, neighbor):
        """
          calculate the timeout to a neighbor according to MSF
        """
        cellPDR = []
        for (ts, cell) in mote.tsch.getSchedule().iteritems():
            if (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TX) or\
                    (cell['dir'] == d.DIR_TXRX_SHARED and cell['neighbor'] == neighbor):
                cellPDR.append(mote.getCellPDR(cell))

        # log
        self.log(
            SimEngine.SimLog.LOG_6TOP_TIMEOUT,
            {
                'cell_pdr': cellPDR
            }
        )

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
        if cellOptions == d.DIR_TXRX_SHARED and neighbor == mote.rpl.getPreferredParent():
            # log
            self.log(
                SimEngine.SimLog.LOG_6TOP_CELL_USED,
                {
                    'neighbor': neighbor.id,
                    'direction': direction,
                    'cell_type': celltype,
                    'prefered_parent': mote.rpl.getPreferredParent()
                }
            )
            mote.sf.numCellsUsed += 1

    def signal_cell_elapsed(self, mote, neighbor, direction):

        assert mote.sf.numCellsElapsed <= self.settings.sf_msf_maxNumCells
        assert direction in [d.DIR_TXRX_SHARED, d.DIR_TX, d.DIR_RX]

        # MSF: updating numCellsElapsed
        if direction == d.DIR_TXRX_SHARED and neighbor == mote.rpl.getPreferredParent():
            mote.sf.numCellsElapsed += 1

            if mote.sf.numCellsElapsed == self.settings.sf_msf_maxNumCells:
                # log
                self.log(
                    SimEngine.SimLog.LOG_6TOP_CELL_ELAPSED,
                    {
                        'cell_elapsed_count': mote.sf.numCellsElapsed,
                        'cell_used_count': mote.sf.numCellsUsed
                    }
                )

                if   mote.sf.numCellsUsed > self.settings.sf_msf_highUsageThres:
                    self.schedule_bandwidth_increment(mote)
                elif mote.sf.numCellsUsed < self.settings.sf_msf_lowUsageThres:
                    self.schedule_bandwidth_decrement(mote)
                self.reset_counters(mote)

    @staticmethod
    def reset_counters(mote):
        mote.sf.numCellsElapsed = 0
        mote.sf.numCellsUsed = 0

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
            asn              = int(self.engine.asn + 1),
            cb               = self.action_bandwidth_increment,
            uniqueTag        = (mote.id, 'action_bandwidth_increment'),
            intraSlotOrder   = 4,
        )

    def action_bandwidth_increment(self, mote):
        """
          Trigger SIXP to add self.settings.sf_msf_numCellsToAddDelete cells to preferred parent
        """
        timeout = self.get_sixtop_timeout(mote, mote.rpl.getPreferredParent())
        celloptions = d.DIR_TXRX_SHARED

        mote.sixp.issue_ADD_REQUEST(
            mote.rpl.getPreferredParent(),
            self.settings.sf_msf_numCellsToAddDelete,
            celloptions,
            timeout,
        )

    def schedule_bandwidth_decrement(self, mote):
        """
          Schedule MSF bandwidth decrement
        """
        self.engine.scheduleAtAsn(
            asn              = int(self.engine.asn + 1),
            cb               = self.action_bandwidth_decrement,
            uniqueTag        = (mote.id, 'action_bandwidth_decrement'),
            intraSlotOrder   = 4,
        )

    def action_bandwidth_decrement(self, mote):
        """
          Trigger SIXP to delete self.settings.sf_msf_numCellsToAddDelete cells from preferred parent
        """
        # ensure at least one dedicated cell is kept with preferred parent
        if mote.numCellsToNeighbors.get(mote.rpl.getPreferredParent(), 0) > 1:
            timeout = self.get_sixtop_timeout(mote, mote.rpl.getPreferredParent())
            celloptions = d.DIR_TXRX_SHARED

            # log
            self.log(
                SimEngine.SimLog.LOG_6TOP_DEL_CELL,
                {
                    'cell_count': self.settings.sf_msf_numCellsToAddDelete,
                    'cell_options': celloptions,
                    'neighbor': mote.rpl.getPreferredParent(),
                    'timeout': timeout
                }
            )

            # trigger SIXP to delete self.settings.sf_msf_numCellsToAddDelete cells
            mote.sixp.issue_DELETE_REQUEST(
                mote.rpl.getPreferredParent(),
                self.settings.sf_msf_numCellsToAddDelete,
                celloptions,
                timeout,
            )

    def housekeeping(self):

        self.engine.scheduleIn(
            delay            = self.settings.sf_msf_housekeepingPeriod*(0.9+0.2*random.random()),
            cb               = self.action_housekeeping,
            uniqueTag        = (self.mote.id, 'action_housekeeping'),
            intraSlotOrder   = 4,
        )

    def action_housekeeping(self):
        """
        MSF housekeeping: decides when to relocate cells
        """
        if self.mote.dagRoot:
            return

        # TODO MSF relocation algorithm

        # schedule next housekeeping
        self.housekeeping()
