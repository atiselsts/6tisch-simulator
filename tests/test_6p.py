import pytest

import test_utils as u

# =========================== fixtures ========================================

# =========================== helpers =========================================

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
    
    # === add/delete cells
    
    
