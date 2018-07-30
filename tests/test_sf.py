"""
Tests for SimEngine.Mote.sf
"""

import types

import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog
from SimEngine import SimEngine

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
            cellOptions
        ):
        mote.tsch.original_addCell(
            slotOffset,
            channelOffset,
            neighbor,
            cellOptions
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

def run_until_mote_is_ready_for_app(sim_engine, mote):
    run_until_cell_allocation(
        sim_engine,
        mote,
        [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED]
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
    def test_msf(self, sim_engine):
        """ Test Scheduling Function Traffic Adaptation
        - objective   : test if msf adjust the number of allocated cells in
                        accordance with traffic
        - precondition: form a 2-mote linear network
        - precondition: the network is formed
        - action      : change traffic
        - expectation : MSF should trigger ADD/DELETE/RELOCATE accordingly
        """

        sim_engine = sim_engine(
            diff_config = {
                'app_pkPeriod'            : 0,
                'app_pkPeriodVar'         : 0.05,
                'exec_numMotes'           : 3,
                'exec_numSlotframesPerRun': 4000,
                'secjoin_enabled'         : False,
                'sf_class'                : 'MSF',
                'conn_class'              : 'Linear',
            }
        )

        # XXX
        d.MSF_MIN_NUM_TX = 10

        # for quick access
        root                     = sim_engine.motes[0]
        hop_1                    = sim_engine.motes[1]
        hop_2                    = sim_engine.motes[2]
        asn_at_end_of_simulation = (
            sim_engine.settings.tsch_slotframeLength *
            sim_engine.settings.exec_numSlotframesPerRun
        )

        # make hop_1 not receive anything on dedicated RX cells other than the
        # first allocated one than one dedicated RX cell so that MSF would
        # perform cell relocation
        hop_1.tsch.original_addCell        = hop_1.tsch.addCell
        hop_1.tsch.original_tsch_action_RX = hop_1.tsch._tsch_action_RX
        def new_addCell(self, slotOffset, channelOffset, neighbor, cellOptions):
            if (
                    (cellOptions == [d.CELLOPTION_RX])
                    and
                    (len(self.getRxCells(neighbor)) == 0)
                ):

                # remember the slotoffset of first allocated dedicated cell. While
                # this cell might be deleted later, ignore such an edge case for
                # this test.
                self.first_dedicated_slot_offset = slotOffset

            self.original_addCell(
                slotOffset,
                channelOffset,
                neighbor,
                cellOptions
            )
        def new_action_RX(self):
            slot_offset = self.engine.getAsn() % self.settings.tsch_slotframeLength
            cell        = self.schedule[slot_offset]
            if (
                    (cell['neighbor'] is not None)
                    and
                    hasattr(self, 'first_dedicated_slot_offset')
                    and
                    ((self.first_dedicated_slot_offset) != slot_offset)
                ):
                # do nothing on this dedicated cell
                pass
            else:
                self.original_tsch_action_RX()

        hop_1.tsch.addCell         = types.MethodType(new_addCell, hop_1.tsch)
        hop_1.tsch._tsch_action_RX = types.MethodType(new_action_RX, hop_1.tsch)

        # wait for the network formed
        u.run_until_everyone_joined(sim_engine)

        # wait for hop_2 to get ready to start application
        run_until_mote_is_ready_for_app(sim_engine, hop_2)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # generate application traffic which is supposed to trigger an ADD
        # transaction between hop_2 and hop_1
        asn_starting_app_traffic = sim_engine.getAsn()
        set_app_traffic_rate(sim_engine, 1.4)
        start_app_traffic(hop_2)
        run_until_dedicated_tx_cell_is_allocated(sim_engine, hop_2)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # increase the traffic
        asn_increasing_app_traffic = sim_engine.getAsn()
        set_app_traffic_rate(sim_engine, 1.1)
        run_until_dedicated_tx_cell_is_allocated(sim_engine, hop_2)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # decrease the traffic; run until a RELOCATE command is issued
        set_app_traffic_rate(sim_engine, 1.4)
        run_until_sixp_cmd_is_seen(sim_engine, hop_2, d.SIXP_CMD_RELOCATE)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # stop the traffic; run until a DELETE command is issued
        stop_app_traffic(sim_engine)
        run_until_sixp_cmd_is_seen(sim_engine, hop_2, d.SIXP_CMD_DELETE)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

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
        run_until_mote_is_ready_for_app(sim_engine, mote_2)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # stop DIO (and EB) transmission
        sim_engine.settings.tsch_probBcast_ebProb = 0

        # force mote_1 to switch its preferred parent
        old_parent = root
        new_parent = mote_2

        # invalidate old_parent
        dio = old_parent.rpl._create_DIO()
        dio['app']['rank'] = 65535
        mote_1.rpl.action_receiveDIO(dio)
        # give a DIO from new_parent with a good rank
        dio = new_parent.rpl._create_DIO()
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
        def it_is_add_request(packet):
            # return if the packet is a ADD request sent from mote_1 to
            # new_parent
            return (
                (packet['mac']['srcMac'] == mote_1.id)
                and
                (packet['mac']['dstMac'] == new_parent.id)
                and
                (packet['type'] == d.PKT_TYPE_SIXP)
                and
                (packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST)
                and
                (packet['app']['code'] == d.SIXP_CMD_ADD)
            )

        def it_is_clear_request(packet):
            # return if the packet is a CLEAR request sent from mote_1 to
            # new_parent
            return (
                (packet['mac']['srcMac'] == mote_1.id)
                and
                (packet['mac']['dstMac'] == old_parent.id)
                and
                (packet['type'] == d.PKT_TYPE_SIXP)
                and
                (packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST)
                and
                (packet['app']['code'] == d.SIXP_CMD_CLEAR)
            )

        assert len([l for l in logs if it_is_add_request(l['packet'])]) > 0
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
        run_until_mote_is_ready_for_app(sim_engine, hop_1)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        # fill up the hop_1's schedule
        channel_offset = 0
        cell_options = [d.CELLOPTION_TX]
        used_slots = hop_1.tsch.getSchedule().keys()
        for _slot in range(sim_engine.settings.tsch_slotframeLength):
            if _slot in used_slots:
                continue
            else:
                hop_1.tsch.addCell(_slot, channel_offset, root.id, cell_options)
        assert len(hop_1.tsch.getSchedule()) == sim_engine.settings.tsch_slotframeLength

        # put dummy stats so that scheduling adaptation can be triggered
        hop_1.sf.num_cells_passed = 100
        hop_1.sf.num_cells_used   = hop_1.sf.num_cells_passed

        # trigger scheduling adaptation
        if   function_under_test == 'adapt_to_traffic':
            hop_1.sf._adapt_to_traffic(root.id)
        elif function_under_test == 'relocate':
            _slot = hop_1.tsch.getTxRxSharedCells(root.id).keys()[0]
            relocating_cell = hop_1.tsch.getTxRxSharedCells(root.id)[_slot]
            hop_1.sf._request_relocating_cells(
                neighbor_id          = root.id,
                cell_options         = [
                    d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED
                ],
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
