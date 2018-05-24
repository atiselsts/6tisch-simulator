
# =========================== imports =========================================

import random
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

    @abstractmethod
    def recvPacket(self, packet):
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

    def recvPacket(self, packet):
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
        assert old_parent != new_parent

        # count number of dedicated cell with old preferred parent
        num_cells = len(self.mote.tsch.getDedicatedCells(old_parent))

        # create celllist
        cell_list = []
        for _ in range(num_cells):
            slotOffset = 0
            if len(self.mote.tsch.getSchedule()) == self.settings.tsch_slotframeLength:
                # FIXME
                #raise ScheduleFullError()
                raise Exception()
            while slotOffset in self.mote.tsch.getSchedule():
                slotOffset = random.randint(1, self.settings.tsch_slotframeLength)
            channelOffset = random.randint(0, self.settings.phy_numChans-1)
            cell_list += [
                {
                    'slotOffset':    slotOffset,
                    'channelOffset': channelOffset,
                    'numTx':         0,
                    'numTxAck':      0
                }
            ]

        # trigger 6P ADD command to add cell with new parent
        self.mote.sixp.issue_ADD_REQUEST(
            neighborid   = new_parent,
            num_cells    = num_cells,
            cell_options = [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED],
            cell_list    = cell_list
        )

        # trigger 6P CLEAR command to old preferred parent
        if old_parent:
            self.mote.sixp.issue_CLEAR_REQUEST(old_parent)

    def recvPacket(self, packet):
        if   packet['type'] == d.PKT_TYPE_SIXP_ADD_REQUEST:
            self._receive_ADD_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_ADD_RESPONSE:
            self._receive_ADD_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_DELETE_REQUEST:
            self._receive_DELETE_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_DELETE_RESPONSE:
            self._receive_DELETE_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_CLEAR_REQUEST:
            self._receive_CLEAR_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_CLEAR_RESPONSE:
            self._receive_CLEAR_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_RELOCATE_REQUEST:
            self._receive_RELOCATE_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_RELOCATE_RESPONSE:
            self._receive_RELOCATE_RESPONSE(packet)
        else:
            raise SystemError()

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
                # FIXME: this is duplicate code (copy-and-paste)
                # FIXME: cell_list could have more than one cell even in this case
                cell_list = []

                for _ in range(1):
                    slotOffset = 0
                    if len(self.mote.tsch.getSchedule()) == self.settings.tsch_slotframeLength:
                        # FIXME
                        #raise ScheduleFullError()
                        raise Exception()
                    while slotOffset in self.mote.tsch.getSchedule():
                        slotOffset = random.randint(1, self.settings.tsch_slotframeLength)
                    channelOffset = random.randint(0, self.settings.phy_numChans-1)
                    cell_list += [
                        {
                            'slotOffset':    slotOffset,
                            'channelOffset': channelOffset,
                            'numTx':         0,
                            'numTxAck':      0
                        }
                    ]

                    # trigger 6P to add a single cell to the preferred parent
                    self.mote.sixp.issue_ADD_REQUEST(
                        neighborid   =  neighbor_id,
                        num_cells    =  1,
                        cell_options = [d.CELLOPTION_TX],
                        cell_list    =  cell_list
                    )

            # delete cell
            elif self.num_cells_used / float(self.num_cells_passed) < d.MSF_LIM_NUMCELLSUSED_LOW:
                if len(self.mote.tsch.getTxCells()) > 1: # only delete if more than 1 cell exists

                    # create cell_list
                    cell_list = []
                    for (slotOffset, cell) in self.mote.tsch.getTxCells(neighbor_id).items():
                        assert cell['neighbor'] == neighbor_id
                        cell_list.append(
                            {
                                'slotOffset':    slotOffset,
                                'channelOffset': cell['channelOffset'],
                            }
                        )
                    assert cell_list

                    # trigger 6P to remove a single cell to the preferred parent
                    self.mote.sixp.issue_DELETE_REQUEST(
                        neighbor_id = neighbor_id,
                        num_cells   = 1,
                        cell_list   = cell_list
                    )

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

    def _receive_ADD_REQUEST(self, addRequest):

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   addRequest,
            }
        )

        # look for cell that works in celllist
        added_slotOffset    = None
        added_channelOffset = None
        for cell in addRequest['app']['CellList']:
            if cell['slotOffset'] not in self.mote.tsch.getSchedule():

                # remember what I added
                added_slotOffset       = cell['slotOffset']
                added_channelOffset    = cell['channelOffset']

                # add to my schedule
                self.mote.tsch.addCell(
                    slotOffset         = cell['slotOffset'],
                    channelOffset      = cell['channelOffset'],
                    neighbor           = addRequest['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_RX],
                )

                break

        # make sure I could use at least one of the cell
        if added_slotOffset is None or added_channelOffset is None:
            code = d.SIXP_RC_ERR
        else:
            code = d.SIXP_RC_SUCCESS

        # create ADD response
        celllist = []
        if added_slotOffset is not None:
            celllist += [
                {
                    'slotOffset':      added_slotOffset,
                    'channelOffset':   added_channelOffset,
                }
            ]
        addResponse = {
            'type':                    d.PKT_TYPE_SIXP_ADD_RESPONSE,
            'app': {
                'Code':                code,
                'SeqNum':              addRequest['app']['SeqNum'],
                'CellList':            celllist,
            },
            'mac': {
                'srcMac':              self.mote.id,
                'dstMac':              addRequest['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_RESPONSE_TX,
            {
                '_mote_id':            self.mote.id,
                'packet':              addResponse,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(addResponse)

    def _receive_ADD_RESPONSE(self, response):
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_RESPONSE_RX,
            {
                '_mote_id':  self.mote.id,
                'packet':    response,
            }
        )

        # add cell from celllist
        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            cell = response['app']['CellList'][0]
            self.mote.tsch.addCell(
                slotOffset         = cell['slotOffset'],
                channelOffset      = cell['channelOffset'],
                neighbor           = response['mac']['srcMac'],
                cellOptions        = [d.CELLOPTION_TX],
            )
    def _receive_DELETE_REQUEST(self, deleteRequest):

        assert len(deleteRequest['app']['CellList']) > 0

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteRequest,
            }
        )

        # delete a cell taken at random in the celllist
        cell_to_delete = random.choice(deleteRequest['app']['CellList'])
        code = d.SIXP_RC_ERR
        for (slotOffcet, cell) in self.mote.tsch.getRxCells(deleteRequest['mac']['srcMac']).items():
            if (
                    cell_to_delete['slotOffset'] == slotOffcet and
                    cell_to_delete['channelOffset'] == cell['channelOffset'] and
                    deleteRequest['mac']['srcMac'] == cell['neighbor']
            ):
                code = d.SIXP_RC_SUCCESS
                self.mote.tsch.deleteCell(
                    slotOffset         = cell_to_delete['slotOffset'],
                    channelOffset      = cell_to_delete['channelOffset'],
                    neighbor           = deleteRequest['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_RX],
                )

        # create DELETE response
        deleteResponse = {
            'type':                     d.PKT_TYPE_SIXP_DELETE_RESPONSE,
            'app': {
                'Code':                 code,
                'SeqNum':               deleteRequest['app']['SeqNum'],
                'CellList':             [
                    {
                        'slotOffset':   cell_to_delete['slotOffset'],
                        'channelOffset':cell_to_delete['channelOffset'],
                    },
                ],
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               deleteRequest['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteResponse,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(deleteResponse)

    def _receive_DELETE_RESPONSE(self, deleteResponse):

        if deleteResponse['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in deleteResponse['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset         = cell['slotOffset'],
                    channelOffset      = cell['channelOffset'],
                    neighbor           = deleteResponse['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteResponse,
            }
        )

    def _receive_CLEAR_REQUEST(self, request):
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet': request,
            }
        )

        # remove all cells with the neighbor
        for cell in request['app']['CellList']:
            self.mote.tsch.deleteCell(
                slotOffset      = cell['slotOffset'],
                channelOffset   = cell['channelOffset'],
                neighbor        = request['mac']['srcMac'],
                cellOptions     = [d.CELLOPTION_RX],
            )

        # create CLEAR response
        response = {
            'type': d.PKT_TYPE_SIXP_CLEAR_RESPONSE,
            'app': {
                'Code': d.SIXP_RC_SUCCESS,
                'SeqNum': request['app']['SeqNum'],
                'CellList': request['app']['CellList'],
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': request['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(response)

    def _receive_CLEAR_RESPONSE(self, response):

        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in response['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset      = cell['slotOffset'],
                    channelOffset   = cell['channelOffset'],
                    neighbor        = response['mac']['srcMac'],
                    cellOptions     = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

    def _receive_RELOCATE_REQUEST(self, request):

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet': request,
            }
        )

        if len(request['app']['CellList']) < 1:
            code = d.SIXP_RC_ERR_CELLLIST
        else:
            code = d.SIXP_RC_SUCCESS
            # remove all cells with the neighbor
            for cell in request['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset=cell['slotOffset'],
                    channelOffset=cell['channelOffset'],
                    neighbor=request['mac']['srcMac'],
                    cellOptions=[d.CELLOPTION_RX],
                )

        # create CLEAR response
        response = {
            'type': d.PKT_TYPE_SIXP_RELOCATE_RESPONSE,
            'app': {
                'Code': code,
                'SeqNum': request['app']['SeqNum'],
                'CellList': request['app']['CellList'],
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': request['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(response)

    def _receive_RELOCATE_RESPONSE(self, response):

        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in response['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset      = cell['slotOffset'],
                    channelOffset   = cell['channelOffset'],
                    neighbor        = response['mac']['srcMac'],
                    cellOptions     = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )
