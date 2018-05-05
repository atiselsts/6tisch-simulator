import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d

# =========================== fixtures ========================================

# =========================== helpers =========================================

def count_dedicated_tx_cells(mote,neighbor):
    return len(mote.tsch.getTxCells(neighbor=neighbor))

def sixp_done_cb(seqnum, rc):
    print seqnum, rc

# =========================== tests ===========================================

def test_add_delete_6p(
        sim_engine,
    ):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                3,
            'exec_numSlotframesPerRun':     10000,
            'sf_type':                      'SSFSymmetric',
            'conn_type':                    'linear',
        },
    )
    
    # === network forms
    
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]
    
    # give the network time to form
    u.run_until_asn(sim_engine, 10000)
    
    # === add a cell
    
    # make sure no cell yet
    assert len(hop2.tsch.getTxCells(hop1.id))==0
    assert len(hop1.tsch.getRxCells(hop2.id))==0
    
    # trigger a 6P ADD
    hop2.sixp.issue_ADD_REQUEST(
        neighborid = hop1.id,
        cb         = sixp_done_cb,
    )
    
    # give 6P transaction some time to finish
    u.run_until_asn(sim_engine, 20000)
    
    # make cell is added
    assert len(hop2.tsch.getTxCells(hop1.id))==1
    assert len(hop1.tsch.getRxCells(hop2.id))==1
    
