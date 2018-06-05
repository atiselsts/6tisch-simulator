# =========================== imports =========================================

import random
import sys
from abc import abstractmethod

import SimEngine
import MoteDefines as d

# =========================== defines =========================================

class ScheduleFullError(Exception):
    pass

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
    def start(self):
        """
        tells SF when should start working
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def stop(self):
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
        """[from TSCH] just passed a dedicated TX cell. used=False means we didn't use it.

        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def indication_parent_change(self, old_parent, new_parent):
        """
        [from RPL] decided to change parents.
        """
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def detect_schedule_inconsistency(self, peerMac):
        raise NotImplementedError() # abstractmethod

    @abstractmethod
    def recv_request(self, packet):
        raise NotImplementedError() # abstractmethod


class SchedulingFunctionSFNone(SchedulingFunctionBase):

    def __init__(self, mote):
        super(SchedulingFunctionSFNone, self).__init__(mote)

    def start(self):
        pass # do nothing

    def stop(self):
        pass # do nothing

    def indication_neighbor_added(self,neighbor_id):
        pass # do nothing

    def indication_neighbor_deleted(self,neighbor_id):
        pass # do nothing

    def indication_dedicated_tx_cell_elapsed(self,cell,used):
        pass # do nothing

    def indication_parent_change(self, old_parent, new_parent):
        pass # do nothing

    def detect_schedule_inconsistency(self, peerMac):
        pass # do nothing

    def recv_request(self, packet):
        pass # do nothing


class SchedulingFunctionMSF(SchedulingFunctionBase):

    DEFAULT_CELL_LIST_LEN = 5
    TXRX_CELL_OPT = [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED]
    TX_CELL_OPT   = [d.CELLOPTION_TX]
    RX_CELL_OPT   = [d.CELLOPTION_RX]

    def __init__(self, mote):
        # initialize parent class
        super(SchedulingFunctionMSF, self).__init__(mote)

        # (additional) local variables
        self.num_cells_passed = 0      # number of dedicated cells passed
        self.num_cells_used   = 0      # number of dedicated cells used
        self.cell_utilization = 0

    # ======================= public ==========================================

    # === admin

    def start(self):
        if self.mote.dagRoot:
            # do nothing
            pass
        else:
            self._housekeeping_collision()

    def stop(self):
        # FIXME: need something before stopping the operation such as freeing
        # all the allocated cells
        if self.mote.dagRoot:
            # do nothing
            pass
        else:
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
            if d.MSF_MAX_NUMCELLS <= self.num_cells_passed:
                self._adapt_to_traffic(preferred_parent)
                self._reset_cell_counters()

    def indication_parent_change(self, old_parent, new_parent):
        assert old_parent != new_parent

        # allocate the same number of cells to the new parent as it has for the
        # old parent; note that there could be three types of cells:
        # (TX=1,RX=1,SHARED=1), (TX=1), and (RX=1)
        if old_parent is None:
            num_tx_cells = 0
            num_rx_cells = 0
        else:
            num_tx_cells = len(self.mote.tsch.getTxCells(old_parent))
            num_rx_cells = len(self.mote.tsch.getRxCells(old_parent))
        self._request_adding_cells(
            neighbor_id    = new_parent,
            num_txrx_cells = 1,
            num_tx_cells   = num_tx_cells,
            num_rx_cells   = num_rx_cells
        )

        # clear all the cells allocated for the old parent
        if old_parent is not None:
            self.mote.sixp.send_request(
                dstMac   = old_parent,
                command  = d.SIXP_CMD_CLEAR,
                callback = lambda event, packet: self._clear_cells(old_parent)
            )

    def detect_schedule_inconsistency(self, peerMac):
        # send a CLEAR request to the peer
        self.mote.sixp.send_request(
            dstMac   = peerMac,
            command  = d.SIXP_CMD_CLEAR,
            callback = lambda event, packet: self._clear_cells(peerMac)
        )

    def recv_request(self, packet):
        if   packet['app']['code'] == d.SIXP_CMD_ADD:
            self._receive_add_request(packet)
        elif packet['app']['code'] == d.SIXP_CMD_DELETE:
            self._receive_delete_request(packet)
        elif packet['app']['code'] == d.SIXP_CMD_CLEAR:
            self._receive_clear_request(packet)
        elif packet['type'] == d.SIXP_CMD_RELOCATE:
            self._receive_RELOCATE_request(packet)
        else:
            # not implemented or not supported
            # ignore this request
            pass

    # ======================= private ==========================================

    def _reset_cell_counters(self):
        self.num_cells_passed = 0
        self.num_cells_used   = 0

    def _adapt_to_traffic(self, neighbor_id):
        """
        Check the cells counters and trigger 6P commands if cells need to be
        added or removed.

        :param int neighbor_id:
        :return:
        """
        cell_utilization = self.num_cells_used / float(self.num_cells_passed)
        if cell_utilization != self.cell_utilization:
            self.log(
                SimEngine.SimLog.LOG_MSF_CELL_UTILIZATION,
                {
                    '_mote_id'    : self.mote.id,
                    'neighbor_id' : neighbor_id,
                    'value'       : '{0}% -> {1}%'.format(
                        int(self.cell_utilization * 100),
                        int(cell_utilization * 100)
                    )
                }
            )
            self.cell_utilization = cell_utilization
        if d.MSF_LIM_NUMCELLSUSED_HIGH < cell_utilization:
            # add one TX cell
            self._request_adding_cells(
                neighbor_id    = neighbor_id,
                num_tx_cells = 1
            )

        elif cell_utilization < d.MSF_LIM_NUMCELLSUSED_LOW:
            # delete one *TX* cell
            if len(self.mote.tsch.getTxCells(neighbor_id)) > 0:
                self._request_deleting_cells(
                    neighbor_id  = neighbor_id,
                    num_cells    = 1,
                    cell_options = self.TX_CELL_OPT
                )

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

        # for quick access; get preferred parent
        preferred_parent = self.mote.rpl.getPreferredParent()

        # collect TX cells which has enough numTX
        tx_cell_list = self.mote.tsch.getTxCells(preferred_parent)
        tx_cell_list = {
            slotOffset: cell for slotOffset, cell in tx_cell_list.items() if (
                d.MSF_MIN_NUM_TX < cell['numTx']
            )
        }

        # collect PDRs of the TX cells
        def pdr(cell):
            assert cell['numTx'] > 0
            return cell['numTxAck'] / float(cell['numTx'])
        pdr_list = {
            slotOffset: pdr(cell) for slotOffset, cell in tx_cell_list.items()
        }

        if len(pdr_list) > 0:
            # pick up TX cells whose PDRs are less than the higest PDR by
            # MSF_MIN_NUM_TX
            highest_pdr = max(pdr_list.values())
            relocation_cell_list = [
                {
                    'slotOffset'   : slotOffset,
                    'channelOffset': tx_cell_list[slotOffset]['channelOffset']
                } for slotOffset, pdr in pdr_list.items() if (
                    d.MSF_RELOCATE_PDRTHRES < (highest_pdr - pdr)
                )
            ]
            if len(relocation_cell_list) > 0:
                self._request_relocating_cells(
                    neighbor_id          = preferred_parent,
                    cell_options         = self.TX_CELL_OPT,
                    num_relocating_cells = len(relocation_cell_list),
                    cell_list            = relocation_cell_list
                )
        else:
            # we don't have any TX cell whose PDR is available; do nothing
            pass

        # schedule next housekeeping
        self.engine.scheduleAtAsn(
            asn=self.engine.asn + d.MSF_HOUSEKEEPINGCOLLISION_PERIOD,
            cb=self._housekeeping_collision,
            uniqueTag=('SimEngine', '_housekeeping_collision'),
            intraSlotOrder=d.INTRASLOTORDER_STACKTASKS,
        )

    # cell manipulation helpers
    def _add_cells(self, neighbor_id, cell_list, cell_options):
        try:
            for cell in cell_list:
                self.mote.tsch.addCell(
                    slotOffset         = cell['slotOffset'],
                    channelOffset      = cell['channelOffset'],
                    neighbor           = neighbor_id,
                    cellOptions        = cell_options
                )
        except Exception:
            # We may fail in adding cells since they could be allocated for
            # another peer. We need to have a locking or reservation mechanism
            # to avoid such a situation.
            raise

    def _delete_cells(self, neighbor_id, cell_list, cell_options):
        for cell in cell_list:
            self.mote.tsch.deleteCell(
                slotOffset    = cell['slotOffset'],
                channelOffset = cell['channelOffset'],
                neighbor      = neighbor_id,
                cellOptions   = cell_options
            )

    def _clear_cells(self, neighbor_id):
        cells = self.mote.tsch.getDedicatedCells(neighbor_id)
        for slotOffset, cell in cells.items():
            assert neighbor_id == cell['neighbor']
            self.mote.tsch.deleteCell(
                slotOffset    = slotOffset,
                channelOffset = cell['channelOffset'],
                neighbor      = cell['neighbor'],
                cellOptions   = cell['cellOptions']
            )

    def _relocate_cells(
            self,
            neighbor_id,
            src_cell_list,
            dst_cell_list,
            cell_options
        ):
        assert len(src_cell_list) == len(dst_cell_list)

        # relocation
        self._add_cells(neighbor_id, src_cell_list, cell_options)
        self._delete_cells(neighbor_id, src_cell_list, cell_options)

    def _create_available_cell_list(self, cell_list_len):
        slots_in_slotframe = set(range(0, self.settings.tsch_slotframeLength))
        slots_in_use       = set(self.mote.tsch.getSchedule().keys())
        available_slots    = list(slots_in_slotframe - slots_in_use)

        if len(available_slots) <= cell_list_len:
            raise ScheduleFullError()
        else:
            selected_slots = random.sample(available_slots, cell_list_len)

        cell_list = []
        for slot_offset in selected_slots:
            channel_offset = random.randint(0, self.settings.phy_numChans - 1)
            cell_list.append(
                {
                    'slotOffset'   : slot_offset,
                    'channelOffset': channel_offset
                }
            )
        return cell_list

    def _create_occupied_cell_list(
            self,
            neighbor_id,
            cell_options,
            cell_list_len
        ):

        if   cell_options == self.TX_CELL_OPT:
            occupied_cells = self.mote.tsch.getTxCells(neighbor_id)
        elif cell_options == self.RX_CELL_OPT:
            occupied_cells = self.mote.tsch.getRxCells(neighbor_id)
        elif cell_options == self.TXRX_CELL_OPT:
            occupied_cells = self.mote.tsch.getTxRxSharedCells(neighbor_id)

        cell_list = [
            {
                'slotOffset'   : slotOffset,
                'channelOffset': cell['channelOffset']
            } for slotOffset, cell in occupied_cells.items()
        ]

        if cell_list_len <= len(occupied_cells):
            cell_list = random.sample(cell_list, cell_list_len)

        return cell_list

    def _are_cells_allocated(
            self,
            peerMac,
            cell_list,
            cell_options
        ):

        # collect allocated cells
        assert cell_options in [self.TX_CELL_OPT, self.RX_CELL_OPT]
        if   cell_options == self.TX_CELL_OPT:
            allocated_cells = self.mote.tsch.getTxCells(peerMac)
        elif cell_options == self.RX_CELL_OPT:
            allocated_cells = self.mote.tsch.getRxCells(peerMac)

        # test all the cells in the cell list against the allocated cells
        ret_val = True
        for cell in cell_list:
            slotOffset    = cell['slotOffset']
            channelOffset = cell['channelOffset']
            if (
                    (slotOffset not in allocated_cells.keys())
                    or
                    (channelOffset != allocated_cells[slotOffset]['channelOffset'])
                ):
                ret_val = False
                break

        return ret_val

    # ADD command related stuff
    def _request_adding_cells(
            self,
            neighbor_id,
            num_txrx_cells = 0,
            num_tx_cells   = 0,
            num_rx_cells   = 0
        ):

        # determine num_cells and cell_options; update num_{txrx,tx,rx}_cells
        if   num_txrx_cells > 0:
            assert num_txrx_cells == 1
            cell_options   = self.TXRX_CELL_OPT
            num_cells      = num_txrx_cells
            num_txrx_cells = 0
        elif num_tx_cells > 0:
            cell_options   = self.TX_CELL_OPT
            if num_tx_cells < self.DEFAULT_CELL_LIST_LEN:
                num_cells    = num_tx_cells
                num_tx_cells = 0
            else:
                num_cells    = self.DEFAULT_CELL_LIST_LEN
                num_tx_cells = num_tx_cells - self.DEFAULT_CELL_LIST_LEN
        elif num_rx_cells > 0:
            cell_options = self.RX_CELL_OPT
            num_cells    = num_rx_cells
            if num_rx_cells < self.DEFAULT_CELL_LIST_LEN:
                num_cells    = num_rx_cells
                num_rx_cells = 0
            else:
                num_cells    = self.DEFAULT_CELL_LIST_LEN
                num_rx_cells = num_rx_cells - self.DEFAULT_CELL_LIST_LEN
        else:
            # nothing to add
            return

        # prepare cell_list
        cell_list = self._create_available_cell_list(self.DEFAULT_CELL_LIST_LEN)

        # prepare _callback which is passed to SixP.send_request()
        callback = self._create_add_request_callback(
            neighbor_id,
            num_cells,
            cell_options,
            num_txrx_cells,
            num_tx_cells,
            num_rx_cells
        )

        # send a request
        self.mote.sixp.send_request(
            dstMac      = neighbor_id,
            command     = d.SIXP_CMD_ADD,
            cellOptions = cell_options,
            numCells    = num_cells,
            cellList    = cell_list,
            callback    = callback
        )

    def _receive_add_request(self, request):

        # for quick access
        proposed_cells = request['app']['cellList']
        peerMac         = request['mac']['srcMac']

        # find available cells in the received CellList
        slots_in_slotframe = set(range(0, self.settings.tsch_slotframeLength))
        slots_in_use       = set(self.mote.tsch.getSchedule().keys())
        slots_in_cell_list = set(
            map(lambda c: c['slotOffset'], proposed_cells)
        )
        available_slots    = list(
            slots_in_cell_list.intersection(slots_in_slotframe - slots_in_use)
        )

        # prepare cell_list
        candidate_cells = [
            c for c in proposed_cells if c['slotOffset'] in available_slots
        ]
        if len(candidate_cells) < request['app']['numCells']:
            cell_list = candidate_cells
        else:
            cell_list = random.sample(
                candidate_cells,
                request['app']['numCells']
            )

        # prepare callback
        if len(available_slots) > 0:
            code = d.SIXP_RC_SUCCESS

            def callback(event, packet):
                if event == d.SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION:
                    # prepare cell options for this responder
                    if   request['app']['cellOptions'] == self.TXRX_CELL_OPT:
                        cell_options = self.TXRX_CELL_OPT
                    elif request['app']['cellOptions'] == self.TX_CELL_OPT:
                        # invert direction
                        cell_options = self.RX_CELL_OPT
                    elif request['app']['cellOptions'] == self.RX_CELL_OPT:
                        # invert direction
                        cell_options = self.TX_CELL_OPT
                    else:
                        # Unsupported cell options for MSF
                        raise Exception()

                    self._add_cells(
                        neighbor_id  = peerMac,
                        cell_list    = cell_list,
                        cell_options = cell_options
                )
        else:
            code      = d.SIXP_RC_ERR
            cell_list = None
            callback  = None

        # send a response
        self.mote.sixp.send_response(
            dstMac      = peerMac,
            return_code = code,
            cellList    = cell_list,
            callback    = callback
        )

    def _create_add_request_callback(
            self,
            neighbor_id,
            num_cells,
            cell_options,
            num_txrx_cells,
            num_tx_cells,
            num_rx_cells
        ):
        def callback(event, packet):
            if event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION:
                assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
                if packet['app']['code'] == d.SIXP_RC_SUCCESS:
                    # add cells on success of the transaction
                    self._add_cells(
                        neighbor_id  = neighbor_id,
                        cell_list    = packet['app']['cellList'],
                        cell_options = cell_options
                    )

                    # The received CellList could be smaller than the requested
                    # NumCells; adjust num_{txrx,tx,rx}_cells
                    _num_txrx_cells = num_txrx_cells
                    _num_tx_cells   = num_tx_cells
                    _num_rx_cells   = num_rx_cells
                    remaining_cells = num_cells - len(packet['app']['cellList'])
                    if remaining_cells > 0:
                        if   cell_options == self.TXRX_CELL_OPT:
                            # One (TX=1,RX=1,SHARED=1) cell is requested;
                            # RC_SUCCESS shouldn't be returned with an empty cell
                            # list
                            raise Exception()
                        elif cell_options == self.TX_CELL_OPT:
                            _num_tx_cells -= remaining_cells
                        elif cell_options == self.RX_CELL_OPT:
                            _num_rx_cells -= remaining_cells
                        else:
                            # never comes here
                            raise Exception()

                    # start another transaction
                    self._request_adding_cells(
                        neighbor_id    = neighbor_id,
                        num_txrx_cells = _num_txrx_cells,
                        num_tx_cells   = _num_tx_cells,
                        num_rx_cells   = _num_rx_cells
                    )
                else:
                    # TODO: request doesn't succeed; how should we do?
                    pass
            elif event == d.SIXP_CALLBACK_EVENT_TIMEOUT:
                # If this transaction is for the very first cell allocation to
                # the preferred parent, let's retry it. Otherwise, let
                # adaptation to traffic trigger another transaction if
                # necessary.
                if cell_options == self.TXRX_CELL_OPT:
                    self._request_adding_cells(
                        neighbor_id    = neighbor_id,
                        num_txrx_cells = 1
                    )
                else:
                    # do nothing as mentioned above
                    pass
            else:
                # ignore other events
                pass

        return callback

    # DELETE command related stuff
    def _request_deleting_cells(
            self,
            neighbor_id,
            num_cells,
            cell_options
        ):

        # prepare cell_list to send
        cell_list = self._create_occupied_cell_list(
            neighbor_id   = neighbor_id,
            cell_options  = cell_options,
            cell_list_len = self.DEFAULT_CELL_LIST_LEN
        )
        assert len(cell_list) > 0

        # prepare callback
        callback = self._create_delete_request_callback(
            neighbor_id,
            cell_options
        )

        # send a DELETE request
        self.mote.sixp.send_request(
            dstMac      = neighbor_id,
            command     = d.SIXP_CMD_DELETE,
            cellOptions = cell_options,
            numCells    = num_cells,
            cellList    = cell_list,
            callback    = callback
        )

    def _receive_delete_request(self, request):
        # for quick access
        num_cells           = request['app']['numCells']
        cell_options        = request['app']['cellOptions']
        candidate_cell_list = request['app']['cellList']
        peerMac             = request['mac']['srcMac']

        # confirm all the cells in the cell list are allocated for the peer
        # with the specified cell options
        #
        # invert the direction in cell_options
        assert cell_options in [self.TX_CELL_OPT, self.RX_CELL_OPT]
        if   cell_options == self.TX_CELL_OPT:
            our_cell_options = self.RX_CELL_OPT
        elif cell_options == self.RX_CELL_OPT:
            our_cell_options   = self.TX_CELL_OPT

        if (
                (
                    self._are_cells_allocated(
                        peerMac      = peerMac,
                        cell_list    = candidate_cell_list,
                        cell_options = our_cell_options
                    ) is True
                )
                and
                (num_cells <= len(candidate_cell_list))
            ):
            code = d.SIXP_RC_SUCCESS
            cell_list = random.sample(candidate_cell_list, num_cells)

            def callback(event, packet):
                if event == d.SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION:
                    self._delete_cells(
                        neighbor_id  = peerMac,
                        cell_list    = cell_list,
                        cell_options = our_cell_options
                )
        else:
            code      = d.SIXP_RC_ERR
            cell_list = None
            callback  = None

        # send the response
        self.mote.sixp.send_response(
            dstMac      = peerMac,
            return_code = code,
            cellList    = cell_list,
            callback    = callback
        )

    def _create_delete_request_callback(
            self,
            neighbor_id,
            cell_options
        ):
        def callback(event, packet):
            if (
                    (event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION)
                    and
                    (packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE)
                ):
                if packet['app']['code'] == d.SIXP_RC_SUCCESS:
                    self._delete_cells(
                        neighbor_id  = neighbor_id,
                        cell_list    = packet['app']['cellList'],
                        cell_options = cell_options
                    )
                else:
                    # TODO: request doesn't succeed; how should we do?
                    pass
            elif event == d.SIXP_CALLBACK_EVENT_TIMEOUT:
                # TODO: request doesn't succeed; how should we do?
                pass
            else:
                # ignore other events
                pass

        return callback

    # RELOCATE command related stuff
    def _request_relocating_cells(
            self,
            neighbor_id,
            cell_options,
            num_relocating_cells,
            cell_list
        ):

        # determine num_cells and relocation_cell_list;
        # update num_relocating_cells and cell_list
        if self.DEFAULT_CELL_LIST_LEN < num_relocating_cells:
            num_cells             = self.DEFAULT_CELL_LIST_LEN
            relocation_cell_list  = cell_list[:self.DEFAULT_CELL_LIST_LEN]
            num_relocating_cells -= self.DEFAULT_CELL_LIST_LEN
            cell_list             = cell_list[self.DEFAULT_CELL_LIST_LEN:]
        else:
            num_cells             = num_relocating_cells
            relocation_cell_list  = cell_list
            num_relocating_cells  = 0
            cell_list             = None

        # prepare candidate_cell_list
        candidate_cell_list = self._create_available_cell_list(
            self.DEFAULT_CELL_LIST_LEN
        )

        # prepare callback
        def callback(event, packet):
            if event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION:
                assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
                if packet['app']['code'] == d.SIXP_RC_SUCCESS:
                    # perform relocations
                    num_relocations = len(packet['app']['cellList'])
                    self._relocate_cells(
                        neighbor_id   = neighbor_id,
                        src_cell_list = relocation_cell_list[:num_relocations],
                        dst_cell_list = packet['app']['cellList'],
                        cell_options  = cell_options
                    )

                    # adjust num_relocating_cells and cell_list
                    _num_relocating_cells = (
                        num_relocating_cells + num_cells - num_relocations
                    )
                    _cell_list = (
                        cell_list + relocation_cell_list[num_relocations:]
                    )

                    # start another transaction
                    self._request_relocating_cells(
                        neighbor_id          = neighbor_id,
                        cell_options         = cell_options,
                        num_relocating_cells = _num_relocating_cells,
                        cell_list            = _cell_list
                    )

        # send a request
        self.mote.sixp.send_request(
            dstMac             = neighbor_id,
            command            = d.SIXP_CMD_RELOCATE,
            cellOptions        = cell_options,
            numCells           = num_cells,
            relocationCellList = relocation_cell_list,
            candidateCellList  = candidate_cell_list,
            callback           = callback
        )

    def _receive_relocate_request(self, request):
        # for quick access
        num_cells        = request['app']['numCells']
        cell_options     = request['app']['cellOptions']
        relocating_cells = request['app']['relocationCellList']
        candidate_cells  = request['app']['candidateCellList']
        peerMac          = request['mac']['srcMac']

        # confirm all the cells in the cell list are allocated for the peer
        # with the specified cell options
        #
        # invert the direction in cell_options
        assert cell_options in [self.TX_CELL_OPT, self.RX_CELL_OPT]
        if   cell_options == self.TX_CELL_OPT:
            our_cell_options = self.RX_CELL_OPT
        elif cell_options == self.RX_CELL_OPT:
            our_cell_options   = self.TX_CELL_OPT

        if (
                (
                    self._are_cells_allocated(
                        peerMac      = peerMac,
                        cell_list    = relocating_cells,
                        cell_options = our_cell_options
                    ) is True
                )
                and
                (num_cells <= len(candidate_cells))
            ):
            # find available cells in the received candidate cell list
            slots_in_slotframe = set(range(0, self.settings.tsch_slotframeLength))
            slots_in_use       = set(self.mote.tsch.getSchedule().keys())
            candidate_slots    = set(
                map(lambda c: c['slotOffset'], candidate_cells)
            )
            available_slots    = list(
                candidate_slots.intersection(slots_in_slotframe - slots_in_use)
            )

            # prepare cell_list
            cell_list = [
                c for c in candidate_cells if c['slotOffset'] in available_slots
            ]

            # prepare callback
            def callback(event, packet):
                if event == d.SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION:
                    num_relocations = len(cell_list)
                    self._relocate_cells(
                        neighbor_id   = peerMac,
                        src_cell_list = relocating_cells[:num_relocations],
                        dst_cell_list = cell_list,
                        cell_options  = our_cell_options
                    )

        else:
            code      = d.SIXP_RC_ERR
            cell_list = None
            callback  = None

        # send a response
        self.mote.sixp.send_response(
            dstMac      = peerMac,
            return_code = code,
            cellList    = cell_list,
            callback    = callback
        )


    # CLEAR command related stuff
    def _receive_clear_request(self, request):

        peerMac = request['mac']['srcMac']

        def callback(event, packet):
            # remove all the cells no matter what happens
            self._clear_cells(peerMac)

        # create CLEAR response
        self.mote.sixp.send_response(
            dstMac      = peerMac,
            return_code = d.SIXP_RC_SUCCESS,
            callback    = callback
        )
