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
            'secjoin_enabled': fixture_secjoin_enabled
        }
    )

    root = sim_engine.motes[0]
    root_mac_addr = root.get_mac_addr()
    mote = sim_engine.motes[1]

    eb = root.tsch._create_EB()
    mote.tsch._action_receiveEB(eb)

    cells = mote.tsch.get_cells(root_mac_addr, mote.sf.SLOTFRAME_HANDLE)
    assert not cells

    mote.tsch._perform_synchronization()

    if fixture_secjoin_enabled:
        # mote should have an autonomous cell to root
        cells = mote.tsch.get_cells(root_mac_addr, mote.sf.SLOTFRAME_HANDLE)
        assert len(cells) == 1
        autonomous_up_cell = cells[0]
        assert autonomous_up_cell.mac_addr == root_mac_addr
        assert (
            sorted(autonomous_up_cell.options) ==
            sorted([d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED])
        )
        assert autonomous_up_cell.slot_offset != 0
        assert autonomous_up_cell.channel_offset != 0

        # on completing the join process, the autonomous cell should be
        # removed
        mote.secjoin.setIsJoined()
        assert mote.secjoin.getIsJoined()
        cells = mote.tsch.get_cells(root_mac_addr, mote.sf.SLOTFRAME_HANDLE)
        assert len(cells) == 0
    else:
        assert mote.secjoin.getIsJoined()
        cells = mote.tsch.get_cells(root_mac_addr, mote.sf.SLOTFRAME_HANDLE)
        assert len(cells) == 0
