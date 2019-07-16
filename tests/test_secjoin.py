import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d

@pytest.fixture(params=[True, False])
def fixture_secjoin_enabled(request):
    return request.param

def test_secjoin_msf(sim_engine, fixture_secjoin_enabled):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'  : 2,
            'sf_class'       : 'MSF',
            'conn_class'     : 'Linear',
            'app_pkPeriod'   : 0,
            'secjoin_enabled': fixture_secjoin_enabled,
            'rpl_extensions' : []
        }
    )

    root = sim_engine.motes[0]
    root_mac_addr = root.get_mac_addr()
    mote = sim_engine.motes[1]

    eb = root.tsch._create_EB()
    mote.tsch._action_receiveEB(eb)

    cells = mote.tsch.get_cells(
        root_mac_addr,
        mote.sf.SLOTFRAME_HANDLE_AUTONOMOUS_CELLS
    )
    assert not cells

    mote.tsch._perform_synchronization()

    if fixture_secjoin_enabled:
        # mote should have an autonomous cell to root
        cells = mote.tsch.get_cells(
            root_mac_addr,
            mote.sf.SLOTFRAME_HANDLE_AUTONOMOUS_CELLS
        )
        assert len(cells) == 1
        autonomous_tx_cell = cells[0]
        assert autonomous_tx_cell.mac_addr == root_mac_addr
        assert (
            sorted(autonomous_tx_cell.options) ==
            sorted([d.CELLOPTION_TX, d.CELLOPTION_SHARED])
        )
        assert autonomous_tx_cell.slot_offset != 0
        assert autonomous_tx_cell.channel_offset != 0
    else:
        assert mote.secjoin.getIsJoined()
        cells = mote.tsch.get_cells(
            root_mac_addr,
            mote.sf.SLOTFRAME_HANDLE_AUTONOMOUS_CELLS
        )
        assert len(cells) == 0
