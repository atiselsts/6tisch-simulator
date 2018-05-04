import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d

# =========================== fixtures ========================================

# =========================== helpers =========================================

def count_dedicated_tx_cells(mote,neighbor):
    returnVal = 0
    for cell in mote.tsch.getTxCells():
        if cell['neighbor']==neighbor.id:
            returnVal += 1
    return returnVal

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
    u.run_until_asn(sim_engine, 1000)
    
    # === add a cell
    
    # make sure no cell yet
    assert count_dedicated_tx_cells(hop2,hop1)==0
    
    # trigger a 6P ADD
    hop2.sixp.issue_ADD_REQUEST(
        neighborid = hop1.id,
        cb         = sixp_done_cb,
    )
    
    # give 6P transaction some time to finish
    u.run_until_asn(sim_engine, 2000)
    
    # make cell is added
    assert count_dedicated_tx_cells(hop2,hop1)==1
    
