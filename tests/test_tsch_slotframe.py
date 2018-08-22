"""
Test for TSCH Slotframe and Cell manipulation
"""

import pytest

from SimEngine.Mote.tsch import SlotFrame, Cell
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
