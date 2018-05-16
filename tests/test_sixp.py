import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d

# =========================== fixtures ========================================

# =========================== helpers =========================================

def count_dedicated_tx_cells(mote,neighbor):
    return len(mote.tsch.getTxCells(neighbor=neighbor))

# =========================== tests ===========================================

def test_add_delete_sixp(
        sim_engine,
    ):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                3,
            'exec_numSlotframesPerRun':     10000,
            'sf_type':                      'SFNone',
            'conn_class':                   'Linear',
            'app_pkPeriod':                 0,
            'tsch_probBcast_ebDioProb':     0,
            'rpl_daoPeriod':                0
        },
        force_initial_routing_and_scheduling_state = True
    )
    
    # === network forms
    
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]
    
    # give the network time to form
    u.run_until_asn(sim_engine, 10000)
    
    # expected number of cells:
    # '1' is the initial value here since hop1 and hop2 have one TX cell each
    # which is installed via force_initial_routing_and_scheduling_state
    numCellExpected = 1
    
    # === add cells
    
    for _ in range(3):
    
        # check number of cells
        assert len(hop2.tsch.getTxCells(hop1.id))==numCellExpected
        assert len(hop1.tsch.getRxCells(hop2.id))==numCellExpected
        
        # trigger a SIXP ADD
        hop2.sixp.issue_ADD_REQUEST(
            neighborid = hop1.id,
        )
        
        # give SIXP transaction some time to finish
        u.run_until_asn(sim_engine, sim_engine.getAsn()+10000)
        
        # I now expect one more cell
        numCellExpected += 1
        
        # make cell is added
        assert len(hop2.tsch.getTxCells(hop1.id))==numCellExpected
        assert len(hop1.tsch.getRxCells(hop2.id))==numCellExpected
    
    # === delete cells
    
    for _ in range(3):
    
        # check number of cells
        assert len(hop2.tsch.getTxCells(hop1.id))==numCellExpected
        assert len(hop1.tsch.getRxCells(hop2.id))==numCellExpected
        
        # trigger a SIXP DELETE
        hop2.sixp.issue_DELETE_REQUEST(
            neighborid = hop1.id,
        )
        
        # give SIXP transaction some time to finish
        u.run_until_asn(sim_engine, sim_engine.getAsn()+10000)
        
        # I now expect one less cell
        numCellExpected -= 1
        
        # make cell is added
        assert len(hop2.tsch.getTxCells(hop1.id))==numCellExpected
        assert len(hop1.tsch.getRxCells(hop2.id))==numCellExpected
