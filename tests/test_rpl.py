"""
Tests for SimEngine.Mote.rpl
"""

import pytest

import SimEngine.Mote.MoteDefines as d
import SimEngine.Mote.rpl as rpl

@pytest.fixture(params=['fully_meshed','linear'])
def fixture_conn_type(request):
    return request.param

def test_ranks_forced_state(sim_engine,fixture_conn_type):
    '''
    Verify the force_initial_routing_and_scheduling_state option
    create the expected RPL state.
    '''
    
    sim_engine = sim_engine(
        {
            'exec_numMotes': 3,
            'conn_type':     fixture_conn_type,
        },
        force_initial_routing_and_scheduling_state = True
    )
    
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    assert root.dagRoot is True
    assert root.rpl.getPreferredParent()      ==    None
    assert root.rpl.getRank()                 ==     256
    assert root.rpl.getDagRank()              ==       1
    
    assert hop1.dagRoot is False
    assert hop1.rpl.getPreferredParent()      == root.id
    assert hop1.rpl.getRank()                 ==     768
    assert hop1.rpl.getDagRank()              ==       3
    
    if   fixture_conn_type=='fully_meshed':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == root.id
        assert hop2.rpl.getRank()             ==     768
        assert hop2.rpl.getDagRank()          ==       3
    elif fixture_conn_type=='linear':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == hop1.id
        assert hop2.rpl.getRank()             ==    1280
        assert hop2.rpl.getDagRank()          ==       5
        
def test_source_route_calculation(sim_engine):
    
    sim_engine = sim_engine(
        {
            'exec_numMotes':      1,
        },
    )
    
    mote = sim_engine.motes[0]
    
    # assume DAOs have been receuved by all mote in this topology
    '''          4----5
                /      
       0 ----- 1 ------ 2 ----- 3  NODAO  6 ---- 7
    '''
    mote.rpl.addParentChildfromDAOs(parent_id=0, child_id=1)
    mote.rpl.addParentChildfromDAOs(parent_id=1, child_id=4)
    mote.rpl.addParentChildfromDAOs(parent_id=4, child_id=5)
    mote.rpl.addParentChildfromDAOs(parent_id=1, child_id=2)
    mote.rpl.addParentChildfromDAOs(parent_id=2, child_id=3)
    # no DAO received for 6->3 link
    mote.rpl.addParentChildfromDAOs(parent_id=6, child_id=7)
    
    # verify all source routes
    assert mote.rpl.computeSourceRoute(1) == [1]
    assert mote.rpl.computeSourceRoute(2) == [1,2]
    assert mote.rpl.computeSourceRoute(3) == [1,2,3]
    assert mote.rpl.computeSourceRoute(4) == [1,4]
    assert mote.rpl.computeSourceRoute(5) == [1,4,5]
    with pytest.raises(rpl.NoSourceRouteError):
        mote.rpl.computeSourceRoute(6)
    with pytest.raises(rpl.NoSourceRouteError):
        mote.rpl.computeSourceRoute(7)
