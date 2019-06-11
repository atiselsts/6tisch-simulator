"""
Tests for SimEngine.Mote.sf
"""

from itertools import chain
import random
import types

import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog
from SimEngine import SimEngine
from SimEngine.Mote.sf import SchedulingFunctionMSF
from SimEngine.Mote.sf import SchedulingFunctionSFNone

# =========================== helpers =========================================

def set_app_traffic_rate(sim_engine, app_pkPeriod):
    sim_engine.settings.app_pkPeriod = app_pkPeriod

def start_app_traffic(mote):
    mote.app.startSendingData()

def stop_app_traffic(sim_engine):
    set_app_traffic_rate(sim_engine, 0)

def run_until_cell_allocation(sim_engine, mote, _cell_options):

    mote.tsch.original_addCell = mote.tsch.addCell
    def new_addCell(
            self,
            slotOffset,
            channelOffset,
            neighbor,
            cellOptions,
            slotframe_handle=0
        ):
        mote.tsch.original_addCell(
            slotOffset,
            channelOffset,
            neighbor,
            cellOptions,
            slotframe_handle
        )

        if (
                (self.mote.id == mote.id)
                and
                (neighbor is not None)
                and
                (neighbor == mote.rpl.getPreferredParent())
                and
                (cellOptions == _cell_options)
            ):
            # pause the simulator
            sim_engine.pauseAtAsn(sim_engine.getAsn() + 1)
            # revert addCell
            mote.tsch.addCell = mote.tsch.original_addCell
    mote.tsch.addCell = types.MethodType(new_addCell, mote.tsch)

    u.run_until_end(sim_engine)

def run_until_dedicated_tx_cell_is_allocated(sim_engine, mote):
    run_until_cell_allocation(
        sim_engine,
        mote,
        [d.CELLOPTION_TX]
    )

def run_until_sixp_cmd_is_seen(sim_engine, mote, cmd):
    mote.sixp.original_tsch_enqueue = mote.sixp._tsch_enqueue
    def new_tsch_enqueue(self, packet):
        mote.sixp.original_tsch_enqueue(packet)
        if (
                (packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST)
                and
                (packet['app']['code'] == cmd)
            ):
            sim_engine.pauseAtAsn(sim_engine.getAsn() + 1)
            # revert _tsch_enqueue
            mote.sixp._tsch_enqueue = mote.sixp.original_tsch_enqueue
    mote.sixp._tsch_enqueue = types.MethodType(new_tsch_enqueue, mote.sixp)
    u.run_until_end(sim_engine)

# =========================== fixtures =========================================

@pytest.fixture(params=['add', 'delete', 'relocate'])
def test_case(request):
    return request.param

# =========================== tests ===========================================

class TestMSF(object):

    def test_initial_dedicated_cell_allocation_to_parent(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 2,
                'sf_class'     : 'MSF',
                'conn_class'   : 'Linear',
                'app_pkPeriod' : 0
            }
        )

        u.run_until_end(sim_engine)
        logs = [
            log for log in u.read_log_file(filter=[SimLog.LOG_TSCH_ADD_CELL['type']])
            if (
                (log['_mote_id'] == sim_engine.motes[1].id)
                and
                (sorted(log['cellOptions']) == sorted([d.CELLOPTION_TX]))
                and
                (log['neighbor'] is not None)
            )
        ]

        # mote_1 should schedule one dedicated cell to its parent
        # (mote_0)
        assert len(logs) == 1

    def test_autonomous_non_shared_cell_allocation(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 2,
                'sf_class':     'MSF'
            }
        )

        root = sim_engine.motes[0]
        non_root = sim_engine.motes[1]

        # root should have one autonomous RX cell just after its initialization
        cells = [
            cell for cell in root.tsch.get_cells(None, root.sf.SLOTFRAME_HANDLE)
            if cell.options == [d.CELLOPTION_TX, d.CELLOPTION_RX]
        ]
        assert len(cells) == 1

        # non_root should not have one autonomous RX cell until it gets
        # synchronized (it should not have even SlotFrame 1)
        assert non_root.tsch.get_slotframe(non_root.sf.SLOTFRAME_HANDLE) is None

        # make non_root synchronized
        eb = root.tsch._create_EB()
        eb_dummy = {
            'type':            d.PKT_TYPE_EB,
            'mac': {
                'srcMac':      '00-00-00-AA-AA-AA',     # dummy
                'dstMac':      d.BROADCAST_ADDRESS,     # broadcast
                'join_metric': 1000
            }
        }
        non_root.tsch._action_receiveEB(eb)
        non_root.tsch._action_receiveEB(eb_dummy)
        cells = [
            cell for cell in non_root.tsch.get_cells(None, root.sf.SLOTFRAME_HANDLE)
            if cell.options == [d.CELLOPTION_TX, d.CELLOPTION_RX]
        ]
        assert len(cells) == 1

    @pytest.fixture(params=['start-up', 'neighbor-add'])
    def fixture_autonomous_shared_cell_mode(self, request):
        return request.param

    def test_autonomous_shared_cell_allocation(
            self,
            sim_engine,
            fixture_autonomous_shared_cell_mode
        ):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 2,
                'sf_class':     'MSF'
            }
        )

        root = sim_engine.motes[0]
        mote = sim_engine.motes[1]

        # add root to mote's neighbor table
        root_mac_addr = root.get_mac_addr()

        if fixture_autonomous_shared_cell_mode == 'start-up':
            mote.sixlowpan._add_on_link_neighbor(root_mac_addr)
            mote.sf.start()
        elif fixture_autonomous_shared_cell_mode == 'neighbor-add':
            mote.sf.start()
            mote.sixlowpan._add_on_link_neighbor(root_mac_addr)

        cells = mote.tsch.get_cells(root_mac_addr, mote.sf.SLOTFRAME_HANDLE)
        assert len(cells) == 0

    def test_msf(self, sim_engine):
        """ Test Scheduling Function Traffic Adaptation
        - objective   : test if msf adjust the number of allocated cells in
                        accordance with traffic
        - precondition: form a 2-mote linear network
        - precondition: the network is formed
        - action      : change traffic
        - expectation : MSF should trigger ADD/DELETE/RELOCATE accordingly
        """

        # to make this test easy, change
        # MSF_HOUSEKEEPINGCOLLISION_PERIOD to 1 second
        msf_housekeeping_period_backup = d.MSF_HOUSEKEEPINGCOLLISION_PERIOD
        d.MSF_HOUSEKEEPINGCOLLISION_PERIOD = 1

        sim_engine = sim_engine(
            diff_config = {
                'exec_randomSeed': 3413860673863013345,
                'app_pkPeriod'            : 0,
                'app_pkPeriodVar'         : 0,
                'exec_numMotes'           : 2,
                'exec_numSlotframesPerRun': 4000,
                'rpl_daoPeriod'           : 0,
                'tsch_keep_alive_interval': 0,
                'tsch_probBcast_ebProb'   : 0,
                'secjoin_enabled'         : False,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear',
            }
        )

        # for quick access
        root = sim_engine.motes[0]
        mote = sim_engine.motes[1]

        # disable DIO
        def do_nothing(self):
            pass
        mote.rpl._send_DIO = types.MethodType(do_nothing, mote)

        # get the mote joined
        eb = root.tsch._create_EB()
        eb_dummy = {
            'type':            d.PKT_TYPE_EB,
            'mac': {
                'srcMac':      '00-00-00-AA-AA-AA',     # dummy
                'dstMac':      d.BROADCAST_ADDRESS,     # broadcast
                'join_metric': 1000
            }
        }
        mote.tsch._action_receiveEB(eb)
        mote.tsch._action_receiveEB(eb_dummy)
        dio = root.rpl._create_DIO()
        dio['mac'] = {
            'srcMac': root.get_mac_addr(),
            'dstMac': d.BROADCAST_ADDRESS
        }
        mote.sixlowpan.recvPacket(dio)

        # 1. test autonomous cell installation
        # 1.1 test Non-SHARED autonomous cell
        cells = [
            cell for cell in mote.tsch.get_cells(
                mac_addr         = None,
                slotframe_handle = SchedulingFunctionMSF.SLOTFRAME_HANDLE
            )
            if cell.options == [d.CELLOPTION_TX, d.CELLOPTION_RX]
        ]
        assert len(cells) == 1
        # 1.2 test SHARED autonomous cell to root
        cells = [
            cell for cell in mote.tsch.get_cells(
                mac_addr         = root.get_mac_addr(),
                slotframe_handle = SchedulingFunctionMSF.SLOTFRAME_HANDLE
            )
            if cell.options == [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED]
        ]
        assert len(cells) == 1

        # 2. test dedicated cell allocation
        # 2.1 decrease MSF_MIN_NUM_TX and MSF_MAX_NUMCELLS to speed up this test
        d.MSF_MIN_NUM_TX   = 10
        d.MSF_MAX_NUMCELLS = 10

        # 2.2 confirm the mote doesn't have any dedicated cell to its parent
        cells = [
            cell for cell in  mote.tsch.get_cells(
                mac_addr         = root.get_mac_addr(),
                slotframe_handle = SchedulingFunctionMSF.SLOTFRAME_HANDLE
            )
            if cell.options == [d.CELLOPTION_TX]
        ]
        assert len(cells) == 0

        # 2.3 the mote should have triggered a 6P to allocate one
        # dedicated cell
        logs = u.read_log_file(filter=[SimLog.LOG_SIXP_TX['type']])
        assert len(logs) == 1
        packet = logs[0]['packet']
        assert packet['mac']['dstMac'] == root.get_mac_addr()
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST
        assert packet['app']['code'] == d.SIXP_CMD_ADD
        assert packet['app']['numCells'] == 1
        assert packet['app']['cellOptions'] == [d.CELLOPTION_TX]

        # wait until the managed cell is available
        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + mote.settings.tsch_slotframeLength * 2
        )

        # mote should have one managed cell scheduled
        cells = [
            cell for cell in  mote.tsch.get_cells(
                mac_addr         = root.get_mac_addr(),
                slotframe_handle = SchedulingFunctionMSF.SLOTFRAME_HANDLE
            )
            if cell.options == [d.CELLOPTION_TX]
        ]
        assert len(cells) == 1

        # 2.4 send an application packet per slotframe
        mote.settings.app_pkPeriod = (
            mote.settings.tsch_slotframeLength / 2 *
            mote.settings.tsch_slotDuration
        )
        mote.app.startSendingData()

        # 2.5 run for 10 slotframes
        assert mote.sf.cell_utilization == 0.0
        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + mote.settings.tsch_slotframeLength * 10
        )

        # 2.6 confirm the cell usage reaches 100%
        assert mote.sf.cell_utilization == 1.0

        # 2.7 one dedicated cell should be allocated in the next 2 slotframes
        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + mote.settings.tsch_slotframeLength * 2
        )
        cells = [
            cell for cell in  mote.tsch.get_cells(
                mac_addr         = root.get_mac_addr(),
                slotframe_handle = SchedulingFunctionMSF.SLOTFRAME_HANDLE
            )
            if cell.options == [d.CELLOPTION_TX]
        ]
        assert len(cells) == 2
        slot_offset = cells[0].slot_offset

        # adjust the packet interval
        mote.settings.app_pkPeriod = (
            mote.settings.tsch_slotframeLength / 3 *
            mote.settings.tsch_slotDuration
        )

        # 3. test cell relocation
        # 3.1 increase the following Rpl values in order to avoid invalidating
        # the root as a parent
        mote.rpl.of.MAX_NUM_OF_CONSECUTIVE_FAILURES_WITHOUT_ACK = 100
        mote.rpl.of.UPPER_LIMIT_OF_ACCEPTABLE_ETX = 100
        mote.rpl.of.MAXIMUM_STEP_OF_RANK = 100

        # 3.2 deny input frames over the dedicated cell on the side of the root
        def rxDone_wrapper(self, packet, channel):
            if (
                    (packet is not None)
                    and
                    (
                        (
                            self.engine.getAsn() %
                            mote.settings.tsch_slotframeLength
                        ) == slot_offset
                    )
                ):
                self.active_cell = None
                self.waitingFor = None
                # silently discard this packet
                return False
            else:
                return self.rxDone_original(packet, channel)
        root.tsch.rxDone_original = root.tsch.rxDone
        root.tsch.rxDone = types.MethodType(rxDone_wrapper, root.tsch)

        # 3.3 run for the next 20 slotframes
        asn_start = sim_engine.getAsn()
        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + mote.settings.tsch_slotframeLength * 20
        )

        # 3.5 RELOCATE should have happened
        logs = [
            log for log in u.read_log_file(filter=['sixp.comp'], after_asn=asn_start)
            if (
                (log['_mote_id'] == mote.id)
                and
                (log['cmd'] == d.SIXP_CMD_RELOCATE)
            )
        ]
        assert len(logs) == 1

        # 4. test dedicated cell deallocation
        # 4.1 stop application packet transmission
        mote.settings.app_pkPeriod = 0

        # 4.2 run for a while
        asn_start = sim_engine.getAsn()
        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + mote.settings.tsch_slotframeLength * 20
        )

        # 4.3 DELETE should have happened
        logs = [
            log for log in u.read_log_file(filter=['sixp.comp'], after_asn=asn_start)
            if (
                (log['_mote_id'] == mote.id)
                and
                (log['cmd'] == d.SIXP_CMD_DELETE)
            )
        ]
        assert len(logs) > 0

        # put the backup value to d.MSF_HOUSEKEEPINGCOLLISION_PERIOD
        d.MSF_HOUSEKEEPINGCOLLISION_PERIOD = msf_housekeeping_period_backup

    def test_parent_switch(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numSlotframesPerRun': 4000,
                'exec_numMotes'           : 3,
                'app_pkPeriod'            : 0,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear'
            }
        )

        # for quick access
        root   = sim_engine.motes[0]
        mote_1 = sim_engine.motes[1]
        mote_2 = sim_engine.motes[2]
        asn_at_end_of_simulation = (
            sim_engine.settings.tsch_slotframeLength *
            sim_engine.settings.exec_numSlotframesPerRun
        )

        # wait for hop_2 to get ready. this is when the network is ready to
        # operate.
        u.run_until_mote_is_ready_for_app(sim_engine, mote_2)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # stop DIO (and EB) transmission
        sim_engine.settings.tsch_probBcast_ebProb = 0

        # force mote_1 to switch its preferred parent
        old_parent = root
        new_parent = mote_2

        # invalidate old_parent
        dio = old_parent.rpl._create_DIO()
        dio['mac'] = {'srcMac': old_parent.get_mac_addr()}
        dio['app']['rank'] = 65535
        mote_1.rpl.action_receiveDIO(dio)
        # give a DIO from new_parent with a good rank
        dio = new_parent.rpl._create_DIO()
        dio['mac'] = {'srcMac': new_parent.get_mac_addr()}
        dio['app']['rank'] = 255
        mote_1.rpl.action_receiveDIO(dio)

        # mote_1 should issue CLEAR to the old preferred parent and ADD to the
        # new one
        asn_start_testing = sim_engine.getAsn()
        u.run_until_end(sim_engine)
        logs = u.read_log_file(
            filter    = [SimLog.LOG_SIXP_TX['type']],
            after_asn = asn_start_testing
        )

        def it_is_clear_request(packet):
            # return if the packet is a CLEAR request sent from mote_1 to
            # new_parent
            return (
                (packet['mac']['srcMac'] == mote_1.get_mac_addr())
                and
                (packet['mac']['dstMac'] == old_parent.get_mac_addr())
                and
                (packet['type'] == d.PKT_TYPE_SIXP)
                and
                (packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST)
                and
                (packet['app']['code'] == d.SIXP_CMD_CLEAR)
            )

        assert len([l for l in logs if it_is_clear_request(l['packet'])]) > 0

    @pytest.fixture(params=['adapt_to_traffic', 'relocate'])
    def function_under_test(self, request):
        return request.param
    def test_no_available_cell(self, sim_engine, function_under_test):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numSlotframesPerRun': 1000,
                'exec_numMotes'           : 2,
                'app_pkPeriod'            : 0,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear'
            }
        )

        # for quick access
        root   = sim_engine.motes[0]
        hop_1 = sim_engine.motes[1]
        asn_at_end_of_simulation = (
            sim_engine.settings.tsch_slotframeLength *
            sim_engine.settings.exec_numSlotframesPerRun
        )

        # wait for hop_1 to get ready.
        u.run_until_mote_is_ready_for_app(sim_engine, hop_1)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # fill up the hop_1's schedule
        channel_offset = 0
        cell_options = [d.CELLOPTION_TX]
        used_slots = hop_1.tsch.get_busy_slots(hop_1.sf.SLOTFRAME_HANDLE)
        for _slot in range(sim_engine.settings.tsch_slotframeLength):
            if _slot in used_slots:
                continue
            else:
                hop_1.tsch.addCell(
                    slotOffset       = _slot,
                    channelOffset    = channel_offset,
                    neighbor         = root.get_mac_addr(),
                    cellOptions      = cell_options,
                    slotframe_handle = hop_1.sf.SLOTFRAME_HANDLE
                )
        assert (
            len(hop_1.tsch.get_busy_slots(hop_1.sf.SLOTFRAME_HANDLE)) ==
            sim_engine.settings.tsch_slotframeLength
        )

        # put dummy stats so that scheduling adaptation can be triggered
        hop_1.sf.num_cells_elapsed = 100
        hop_1.sf.num_cells_used   = hop_1.sf.num_cells_elapsed

        # trigger scheduling adaptation
        root_mac_addr = root.get_mac_addr()
        hop_1.sf.retry_count[root_mac_addr] = 0
        if   function_under_test == 'adapt_to_traffic':
            hop_1.sf._adapt_to_traffic(root_mac_addr)
        elif function_under_test == 'relocate':
            relocating_cell = filter(
                lambda cell: cell.options == [d.CELLOPTION_TX],
                hop_1.tsch.get_cells(root.get_mac_addr(), hop_1.sf.SLOTFRAME_HANDLE)
            )[0]
            hop_1.sf._request_relocating_cells(
                neighbor             = root_mac_addr,
                cell_options         = [d.CELLOPTION_TX],
                num_relocating_cells = 1,
                cell_list            = [relocating_cell]
            )


        else:
            # not implemented
            assert False

        # make sure the log is written into the file
        SimEngine.SimLog.SimLog().flush()

        # MSF should output a "schedule-full" error in the log file
        logs = u.read_log_file(
            filter    = [SimLog.LOG_MSF_ERROR_SCHEDULE_FULL['type']],
            after_asn = sim_engine.getAsn() - 1
        )
        assert len(logs) == 1
        assert logs[0]['_mote_id'] == hop_1.id


    def test_sax(self, sim_engine):
        # FIXME: test should be done against computed hash values
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 10,
                'sf_class'     : 'MSF'
            }
        )

        sax = sim_engine.motes[0].sf._sax

        for mote in sim_engine.motes:
            print sax(mote.get_mac_addr())

    def test_get_autonomous_cell(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 10,
                'sf_class'     : 'MSF'
            }
        )

        mote = sim_engine.motes[0]
        mac_addr = '00-00-00-00-00-00-00-00'

        # hash_value should be zero
        slot_offset, channel_offset = mote.sf._get_autonomous_cell(mac_addr)
        assert slot_offset == 1
        assert channel_offset == 0

    def test_clear(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'  : 2,
                'sf_class'       : 'MSF',
                'conn_class'     : 'Linear',
                'secjoin_enabled': False
            }
        )

        root = sim_engine.motes[0]
        mote = sim_engine.motes[1]
        root_mac_addr = root.get_mac_addr()

        u.run_until_mote_is_ready_for_app(sim_engine, mote)

        cells = mote.tsch.get_cells(
            mac_addr         = root_mac_addr,
            slotframe_handle = mote.sf.SLOTFRAME_HANDLE
        )
        assert len(cells) == 1
        # mote should have a SHARED autonomous cell of the root
        assert cells[0].mac_addr == root_mac_addr
        assert d.CELLOPTION_TX in cells[0].options
        assert d.CELLOPTION_RX in cells[0].options
        assert d.CELLOPTION_SHARED in cells[0].options
        # keep the reference to the SHARED autonomous cell
        root_autonomous_cell = cells[0]

        # execute CLEAR (call the equivalent internal method of the
        # SF)
        mote.sf._clear_cells(root_mac_addr)

        # get the autonomous cell again
        cells = mote.tsch.get_cells(
            mac_addr         = root_mac_addr,
            slotframe_handle = mote.sf.SLOTFRAME_HANDLE
        )
        assert len(cells) == 1
        assert cells[0] == root_autonomous_cell

    def test_retry(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'           : 2,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear',
                'secjoin_enabled'         : False,
                'app_pkPeriod'            : 0,
                'rpl_daoPeriod'           : 0,
                'rpl_extensions'          : [],
                'tsch_keep_alive_interval': 0,
                'tsch_probBcast_ebProb'   : 0
            }
        )
        root = sim_engine.motes[0]
        mote = sim_engine.motes[1]

        # make root not to respond to a 6P request
        root.sf.recv_request = SchedulingFunctionSFNone(root).recv_request

        # get the mote joined
        eb = root.tsch._create_EB()
        eb_dummy = {
            'type':            d.PKT_TYPE_EB,
            'mac': {
                'srcMac':      '00-00-00-AA-AA-AA',     # dummy
                'dstMac':      d.BROADCAST_ADDRESS,     # broadcast
                'join_metric': 1000
            }
        }
        mote.tsch._action_receiveEB(eb)
        mote.tsch._action_receiveEB(eb_dummy)

        assert mote.tsch.isSync

        dio = root.rpl._create_DIO()
        dio['mac'] = {
            'srcMac': root.get_mac_addr(),
            'dstMac': d.BROADCAST_ADDRESS
        }
        # need to put the DIO to 6LoWPAN layer so that mote can learn
        # root's MAC address and schedule the autonomous shared cell.
        mote.sixlowpan.recvPacket(dio)

        assert mote.rpl.dodagId is not None

        # stop DIO timer to make this test simple
        root.rpl.trickle_timer.stop()
        mote.rpl.trickle_timer.stop()

        u.run_until_end(sim_engine)

        # we should see three 6P timeout logs
        logs = u.read_log_file(
            filter=[SimLog.LOG_SIXP_TRANSACTION_TIMEOUT['type']]
        )
        assert (
            len([log for log in logs if log['_mote_id']==mote.id]) ==
            SchedulingFunctionMSF.MAX_RETRY  + 1
        )

        # mote should lose its parent
        logs = u.read_log_file(
            filter=[SimLog.LOG_RPL_CHURN['type']]
        )
        assert len(logs) == 2
        assert logs[0]['preferredParent'] == root.get_mac_addr()
        assert logs[1]['preferredParent'] is None

    def test_create_available_cell_list(self, sim_engine):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'       : 1,
                'sf_class'            : 'MSF',
                'tsch_slotframeLength': 2
            }
        )
        mote = sim_engine.motes[0]
        # one of slots is supposed to be used for the autonomous cell;
        # the other shouldn't selected by _crate_available_cell_list()
        # because it's slot_offset is 0
        cells = mote.tsch.get_cells(
            mac_addr         = None,
            slotframe_handle = mote.sf.SLOTFRAME_HANDLE
        )
        assert len(cells) == 1
        assert cells[0].slot_offset != 0
        cells =  mote.sf._create_available_cell_list(1)
        assert len(cells) == 0

    def test_locked_slot_in_relocation_request(self, sim_engine):
        # MSF shouldn't select a slot offset out of the candidate cell
        # list which is in locked_slots
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'           : 2,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear',
                'secjoin_enabled'         : False,
                'app_pkPeriod'            : 0,
                'rpl_daoPeriod'           : 0,
                'rpl_extensions'          : [],
                'tsch_keep_alive_interval': 0,
                'tsch_probBcast_ebProb'   : 0
            }
        )

        root = sim_engine.motes[0]
        mote = sim_engine.motes[1]

        u.get_join(root, mote)
        # wait for a while
        u.run_until_asn(
            sim_engine,
            2 * sim_engine.settings.tsch_slotframeLength
        )

        # mote should have one dedicated cell
        cells = mote.tsch.get_cells(
            root.get_mac_addr(),
            mote.sf.SLOTFRAME_HANDLE
        )
        assert len(cells) == 2
        cells = [cell for cell in cells if cell.options == [d.CELLOPTION_TX]]
        assert len(cells) == 1
        cell = cells[0]

        # send a RELOCATE request to mote, which has the used slot
        # offset in both of the candidate cell list and the relocation
        # cell list
        target_slot_offset = cell.slot_offset + 1
        if (cell.slot_offset + 1) == sim_engine.settings.tsch_slotframeLength:
            target_slot_offset = 1
        # put target_slot_offset into locked_slots. target_slot_offset
        # is in the candidate cell list
        mote.sf.locked_slots.add(target_slot_offset)
        root.sixp.send_request(
            dstMac             = mote.get_mac_addr(),
            command            = d.SIXP_CMD_RELOCATE,
            cellOptions        = [d.CELLOPTION_RX],
            numCells           = 1,
            relocationCellList = [{
                'slotOffset'   : cell.slot_offset,
                'channelOffset': cell.channel_offset
            }],
            candidateCellList  = [{
                'slotOffset'   : target_slot_offset,
                'channelOffset': 0
            }],
            callback           = None
        )

        u.run_until_asn(
            sim_engine,
            sim_engine.getAsn() + 2 * sim_engine.settings.tsch_slotframeLength
        )
        logs = u.read_log_file(filter=[SimLog.LOG_SIXP_RX['type']])
        assert len(logs) == 4 # including the first round-trip for ADD
        response = logs[-1]['packet']
        assert response['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
        assert response['app']['code'] == d.SIXP_RC_SUCCESS
        assert len(response['app']['cellList']) == 0

    @pytest.fixture(params=[True, False])
    def limit_autonomous_cell_use(self, request):
        return request.param

    def test_limit_autonomous_cell_use(
            self,
            sim_engine,
            limit_autonomous_cell_use
        ):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'                : 2,
                'sf_class'                     : 'MSF',
                'conn_class'                   : 'Linear',
                'secjoin_enabled'              : False,
                'app_pkPeriod'                 : 0,
                'rpl_daoPeriod'                : 0,
                'rpl_extensions'               : [],
                'tsch_keep_alive_interval'     : 0,
                'tsch_probBcast_ebProb'        : 0,
                'msf_limit_autonomous_cell_use': limit_autonomous_cell_use
            }
        )

        root = sim_engine.motes[0]
        root_mac_addr = root.get_mac_addr()
        mote = sim_engine.motes[1]
        mote.sf.start()
        mote_slotframe = mote.tsch.get_slotframe(mote.sf.SLOTFRAME_HANDLE)

        # install the autonomous cell to the root
        assert not mote.sf._get_autonomous_shared_cell(root_mac_addr)
        mote.sf._allocate_autonomous_shared_cell(root_mac_addr)
        cells = mote_slotframe.get_cells_by_mac_addr(root_mac_addr)
        autonomous_cell = mote.sf._get_autonomous_shared_cell(root_mac_addr)
        assert autonomous_cell
        assert d.CELLOPTION_TX in autonomous_cell.options

        # add an dedicated cell to the root
        dedicated_cell = {'slotOffset': 1, 'channelOffset': 1}
        mote.sf._add_cells(
            neighbor     = root_mac_addr,
            cell_list    = [dedicated_cell],
            cell_options = [d.CELLOPTION_TX]
        )
        assert len(mote_slotframe.get_cells_by_mac_addr(root_mac_addr)) == 2

        # check whether TX bit gets off or not
        autonomous_cell = mote.sf._get_autonomous_shared_cell(root_mac_addr)
        if limit_autonomous_cell_use:
            assert d.CELLOPTION_TX not in autonomous_cell.options
        else:
            assert d.CELLOPTION_TX in autonomous_cell.options

        # delete the dedicated cell
        mote.sf._delete_cells(
            neighbor     = root_mac_addr,
            cell_list    = [dedicated_cell],
            cell_options = [d.CELLOPTION_TX]
        )
        assert len(mote_slotframe.get_cells_by_mac_addr(root_mac_addr)) == 1
        autonomous_cell = mote.sf._get_autonomous_shared_cell(root_mac_addr)
        assert d.CELLOPTION_TX in autonomous_cell.options

        # test "clear"
        # add the dedicated cell again
        dedicated_cell = {'slotOffset': 1, 'channelOffset': 1}
        mote.sf._add_cells(
            neighbor     = root_mac_addr,
            cell_list    = [dedicated_cell],
            cell_options = [d.CELLOPTION_TX]
        )
        assert len(mote_slotframe.get_cells_by_mac_addr(root_mac_addr)) == 2

        # add another dedicated cell
        dedicated_cell = {'slotOffset': 2, 'channelOffset': 2}
        mote.sf._add_cells(
            neighbor     = root_mac_addr,
            cell_list    = [dedicated_cell],
            cell_options = [d.CELLOPTION_TX]
        )
        assert len(mote_slotframe.get_cells_by_mac_addr(root_mac_addr)) == 3

        # check whether TX bit gets off or not
        autonomous_cell = mote.sf._get_autonomous_shared_cell(root_mac_addr)
        if limit_autonomous_cell_use:
            assert d.CELLOPTION_TX not in autonomous_cell.options
        else:
            assert d.CELLOPTION_TX in autonomous_cell.options

        # exec "clear""
        mote.sf._clear_cells(root_mac_addr)
        # the autonomous cell should be kept
        autonomous_cell = mote.sf._get_autonomous_shared_cell(root_mac_addr)
        assert autonomous_cell
        # and of course, TX bit should be set
        assert d.CELLOPTION_TX in autonomous_cell.options
