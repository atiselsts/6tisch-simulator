"""
Test for TSCH Slotframe and Cell manipulation
"""

import pytest

import test_utils as u
from SimEngine.Mote.tsch import SlotFrame, Cell
from SimEngine import SimLog
import SimEngine.Mote.MoteDefines as d

all_options_on = [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED]

@pytest.fixture(params=[None, 'test_mac_addr'])
def fixture_neighbor_mac_addr(request):
    return request.param


def test_add(fixture_neighbor_mac_addr):
    slotframe = SlotFrame(101)
    cell = Cell(0, 0, all_options_on, fixture_neighbor_mac_addr)
    slotframe.add(cell)

    assert slotframe.get_cells_at_asn(0) == [cell]
    assert slotframe.get_cells_at_asn(1) == []
    assert slotframe.get_cells_at_asn(100) == []
    assert slotframe.get_cells_at_asn(101) == [cell]

    assert slotframe.get_cells_by_slot_offset(0) == [cell]
    assert slotframe.get_cells_by_slot_offset(1) == []
    assert slotframe.get_cells_by_slot_offset(100) == []

    assert slotframe.get_cells_by_mac_addr(fixture_neighbor_mac_addr) == [cell]
    assert slotframe.get_cells_by_mac_addr('dummy_mac_addr') == []

    assert (
        filter(
            lambda cell: cell.options == [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED],
            slotframe.get_cells_by_mac_addr(fixture_neighbor_mac_addr)
        ) == [cell]
    )


def test_delete_cell():
    neighbor_mac_addr = 'test_mac_addr'
    slotframe = SlotFrame(101)
    cell = Cell(0, 0, all_options_on, neighbor_mac_addr)

    assert slotframe.get_cells_by_mac_addr(neighbor_mac_addr) == []
    assert slotframe.get_cells_by_slot_offset(0) == []

    slotframe.add(cell)

    assert slotframe.get_cells_by_mac_addr(neighbor_mac_addr) == [cell]
    assert slotframe.get_cells_by_slot_offset(0) == [cell]

    slotframe.delete(cell)

    assert slotframe.get_cells_by_mac_addr(neighbor_mac_addr) == []
    assert slotframe.get_cells_by_slot_offset(0) == []


def test_add_cells_for_same_mac_addr():
    slotframe = SlotFrame(101)

    cell_1 = Cell(1, 5, [d.CELLOPTION_TX], 'test_mac_addr_1')
    cell_2 = Cell(51, 10, [d.CELLOPTION_RX], 'test_mac_addr_1')

    assert slotframe.get_cells_by_slot_offset(1) == []

    slotframe.add(cell_1)
    slotframe.add(cell_2)

    assert slotframe.get_cells_by_slot_offset(1) == [cell_1]
    assert slotframe.get_cells_by_slot_offset(51) == [cell_2]
    assert slotframe.get_cells_by_mac_addr('test_mac_addr_1') == [
        cell_1, cell_2
    ]


def test_add_cells_at_same_slot_offset():
    slotframe = SlotFrame(101)

    cell_1 = Cell(1, 5, [d.CELLOPTION_TX], 'test_mac_addr_1')
    cell_2 = Cell(1, 5, [d.CELLOPTION_RX], 'test_mac_addr_2')

    assert slotframe.get_cells_by_slot_offset(1) == []

    slotframe.add(cell_1)
    slotframe.add(cell_2)

    assert slotframe.get_cells_by_slot_offset(1) == [
        cell_1, cell_2
    ]
    assert slotframe.get_cells_by_mac_addr('test_mac_addr_1') == [cell_1]
    assert slotframe.get_cells_by_mac_addr('test_mac_addr_2') == [cell_2]

def test_tx_with_two_slotframes(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'app_pkPeriod'            : 0,
            'exec_numMotes'           : 2,
            'exec_numSlotframesPerRun': 1000,
            'secjoin_enabled'         : False,
            'sf_class'                : 'SFNone',
            'conn_class'              : 'Linear',
            'rpl_extensions'          : [],
            'rpl_daoPeriod'           : 0
        }
    )

    # shorthands
    root  = sim_engine.motes[0]
    hop_1 = sim_engine.motes[1]

    # force motes to have two slotframes
    for mote in sim_engine.motes:
        mote.tsch.slotframes = []
        for i in range(2):
            mote.tsch.slotframes.append(SlotFrame(101))

    # install the minimal cell to the root
    root.tsch.add_minimal_cell()

    asn_at_end_of_simulation = (
        sim_engine.settings.tsch_slotframeLength *
        sim_engine.settings.exec_numSlotframesPerRun
    )

    u.run_until_everyone_joined(sim_engine)
    assert sim_engine.getAsn() < asn_at_end_of_simulation

    # put DIO to hop1
    dio = root.rpl._create_DIO()
    dio['mac'] = {'srcMac': root.id}
    hop_1.rpl.action_receiveDIO(dio)

    # install one TX cells to each slotframe
    for i in range(2):
        hop_1.tsch.addCell(
            slotOffset       = i + 1,
            channelOffset    = 0,
            neighbor         = root.id,
            cellOptions      = [d.CELLOPTION_TX],
            slotframe_handle = i
        )
        root.tsch.addCell(
            slotOffset       = i + 1,
            channelOffset    = 0,
            neighbor         = hop_1.id,
            cellOptions      = [d.CELLOPTION_RX],
            slotframe_handle = i
        )

    # the first dedicated cell is scheduled at slot_offset 1, the other is at
    # slot_offset 2
    cell_in_slotframe_0 = hop_1.tsch.get_cells(root.id, 0)[0]
    cell_in_slotframe_1 = hop_1.tsch.get_cells(root.id, 1)[0]

    # run until the end of this slotframe
    slot_offset = sim_engine.getAsn() % 101
    u.run_until_asn(sim_engine, sim_engine.getAsn() + (101 - slot_offset - 1))

    # send two application packets, which will be sent over the dedicated cells
    hop_1.app._send_a_single_packet()
    hop_1.app._send_a_single_packet()

    # run for one slotframe
    asn = sim_engine.getAsn()
    assert (asn % 101) == 100 # the next slot is slotoffset 0
    u.run_until_asn(sim_engine, asn + 101)

    # check logs
    ## TX side (hop_1)
    logs = [
        log for log in u.read_log_file(
                filter    = [SimLog.LOG_TSCH_TXDONE['type']],
                after_asn = asn
            ) if log['_mote_id'] == hop_1.id
    ]
    assert len(logs) == 2
    assert (logs[0]['_asn'] % 101) == cell_in_slotframe_0.slot_offset
    assert (logs[1]['_asn'] % 101) == cell_in_slotframe_1.slot_offset

    ## RX side (root)
    logs = [
        log for log in u.read_log_file(
                filter    = [SimLog.LOG_TSCH_RXDONE['type']],
                after_asn = asn
            ) if log['_mote_id'] == root.id
    ]
    assert len(logs) == 2
    assert (logs[0]['_asn'] % 101) == cell_in_slotframe_0.slot_offset
    assert (logs[1]['_asn'] % 101) == cell_in_slotframe_1.slot_offset

    # confirm hop_1 has the minimal cell
    assert len(hop_1.tsch.get_cells(None)) == 1
    assert (
        hop_1.tsch.get_cells(None)[0].options == [
            d.CELLOPTION_TX,
            d.CELLOPTION_RX,
            d.CELLOPTION_SHARED
        ]
    )
