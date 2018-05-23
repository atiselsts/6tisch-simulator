
# =========================== imports =========================================

import sys
from abc import abstractmethod

import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SchedulingFunction(object):
    def __new__(cls, mote):
        settings    = SimEngine.SimSettings.SimSettings()
        class_name  = 'SchedulingFunction{0}'.format(settings.sf_class)
        return getattr(sys.modules[__name__], class_name)(mote)

class SchedulingFunctionBase(object):

    def __init__(self, mote):

        # store params
        self.mote            = mote

        # singletons (quicker access, instead of recreating every time)
        self.settings        = SimEngine.SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine.SimEngine()
        self.log             = SimEngine.SimLog.SimLog().log

    # ======================= public ==========================================

    # === admin

    @abstractmethod
    def startMonitoring(self):
        """
        tells SF when should start working
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def stopMonitoring(self):
        '''
        tells SF when should stop working
        '''
        raise NotImplementedError() # abstractmethod

    # === indications from other layers

    @abstractmethod
    def indication_neighbor_added(self,neighbor_id):
        """
        [from TSCH] just added a neighbor.
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def indication_neighbor_deleted(self,neighbor_id):
        """
        [from TSCH] just deleted a neighbor.
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def indication_dedicated_tx_cell_elapsed(self,cell,used):
        """
        [from TSCH] just passed a dedicated TX cell. used=False means we didn't use it.
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def indication_parent_change(self, old_parent, new_parent):
        """
        [from RPL] decided to change parents.
        """
        raise NotImplementedError() # abstractmethod

class SchedulingFunctionSFNone(SchedulingFunctionBase):

    def __init__(self, mote):
        super(SchedulingFunctionSFNone, self).__init__(mote)

    def startMonitoring(self):
        pass # do nothing

    def stopMonitoring(self):
        pass # do nothing

    def indication_neighbor_added(self,neighbor_id):
        pass # do nothing

    def indication_neighbor_deleted(self,neighbor_id):
        pass # do nothing

    def indication_dedicated_tx_cell_elapsed(self,cell,used):
        pass # do nothing

    def indication_parent_change(self, old_parent, new_parent):
        pass # do nothing

class SchedulingFunctionMSF(SchedulingFunctionBase):

    def __init__(self, mote):
        # initialize parent class
        super(SchedulingFunctionMSF, self).__init__(mote)

        # (additional) local variables
        self.num_cells_passed = 0  # number of dedicated cells passed
        self.num_cells_used   = 0  # number of dedicated cells used

    # ======================= public ==========================================

    # === admin

    def startMonitoring(self):
        self._housekeeping_collision()

    def stopMonitoring(self):
        self.engine.removeFutureEvent('_housekeeping_collision')

    # === indications from other layers

    def indication_neighbor_added(self, neighbor_id):
        pass

    def indication_neighbor_deleted(self, neighbor_id):
        pass

    def indication_dedicated_tx_cell_elapsed(self, cell, used):
        assert cell['neighbor'] is not None

        preferred_parent = self.mote.rpl.getPreferredParent()
        if cell['neighbor'] == preferred_parent:
            # increment cell passed counter
            self.num_cells_passed += 1

            # increment cell used counter
            if used:
                self.num_cells_used += 1

            # adapt number of cells if necessary
            self._adapt_to_traffic(preferred_parent)

    def indication_parent_change(self, old_parent, new_parent):
        # count number of dedicated cell with old preferred parent
        num_cells = len(self.mote.tsch.getDedicatedCells(old_parent))

        # trigger 6P ADD command to add cell with new parent
        self.mote.sixp.issue_ADD_REQUEST(new_parent, num_cells)

        # trigger 6P CLEAR command to old preferred parent
        self.mote.sixp.issue_CLEAR_REQUEST(old_parent)

    # ======================= private ==========================================

    def _adapt_to_traffic(self, neighbor_id):
        """
        Check the cells counters and trigger 6P commands if cells need to be
        added or removed.

        :param int neighbor_id:
        :return:
        """
        if self.num_cells_passed >= d.MSF_MAX_NUMCELLS:
            # add cells
            if self.num_cells_used / float(self.num_cells_passed) > d.MSF_LIM_NUMCELLSUSED_HIGH:
                # trigger 6P to add a single cell to the preferred parent
                self.mote.sixp.issue_ADD_REQUEST(neighbor_id)

            # delete cell
            elif self.num_cells_used / float(self.num_cells_passed) < d.MSF_LIM_NUMCELLSUSED_LOW:
                if len(self.mote.tsch.getTxCells()) > 1: # only delete if more than 1 cell exists
                    # trigger 6P to remove a single cell to the preferred parent
                    self.mote.sixp.issue_DELETE_REQUEST(neighbor_id)

            # reset counters
            self.num_cells_passed = 0
            self.num_cells_used   = 0

    def _housekeeping_collision(self):
        """
        Identify cells where schedule collisions occur.
        draft-chang-6tisch-msf-01:
            The key for detecting a schedule collision is that, if a node has
            several cells to the same preferred parent, all cells should exhibit
            the same PDR.  A cell which exhibits a PDR significantly lower than
            the others indicates than there are collisions on that cell.
        :return:
        """

        # get preferred parent and TX cells to that preferred parent
        preferred_parent = self.mote.rpl.getPreferredParent()
        cell_list = self.mote.tsch.getTxCells(preferred_parent)

        # compute PDR for each cell with preferred parent
        max_pdr = 0
        max_pdr_cell = None

        for (slotOffset, cell) in cell_list.items():
            # skip cell if number of numTx not significant enough
            if cell['numTx'] < d.MSF_MIN_NUM_TX:
                continue

            # calculate PDR
            cell['pdr'] = cell['numTxAck'] / float(cell['numTx'])

            # identify cell with the highest PDR
            if max_pdr < cell['pdr']:
                max_pdr = cell['pdr']

        # compare cells against cell with highest PDR
        for (slotOffset, cell) in cell_list.items():
            if cell != max_pdr_cell:
                if 'pdr' in cell and cell['pdr'] < d.MSF_RELOCATE_PDRTHRES:
                    # trigger 6P RELOCATE command
                    self.mote.sixp.issue_RELOCATE_REQUEST(preferred_parent)

        # schedule next housekeeping
        self.engine.scheduleAtAsn(
            asn=self.engine.asn + d.MSF_HOUSEKEEPINGCOLLISION_PERIOD,
            cb=self._housekeeping_collision,
            uniqueTag=('SimEngine', '_housekeeping_collision'),
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS,
        )