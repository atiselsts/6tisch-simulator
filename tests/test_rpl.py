"""
Tests for SimEngine.Mote.rpl
"""

import pytest

import SimEngine.Mote.MoteDefines as d

@pytest.fixture(params=['fully_meshed','linear'])
def fixture_conn_type(request):
    return request.param

def test_ranks__forced_state(sim_engine,fixture_conn_type):
    '''
    Verify the force_initial_routing_and_scheduling_state option
    create the expected RPL state.
    '''
    
    sim_engine = sim_engine(
        {
            'exec_numMotes':      3,
            'conn_type':          fixture_conn_type,
        },
        force_initial_routing_and_scheduling_state = True
    )
    
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    assert root.dagRoot is True
    assert root.rpl.getPreferredParent()      == None
    assert root.rpl.getRank()                 ==  256
    assert root.rpl.getDagRank()              ==    1
    
    assert hop1.dagRoot is False
    assert hop1.rpl.getPreferredParent()      == root
    assert hop1.rpl.getRank()                 ==  768
    assert hop1.rpl.getDagRank()              ==    3
    
    if   fixture_conn_type=='fully_meshed':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == root
        assert hop2.rpl.getRank()             ==  768
        assert hop2.rpl.getDagRank()          ==    3
    elif fixture_conn_type=='linear':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == hop1
        assert hop2.rpl.getRank()             == 1280
        assert hop2.rpl.getDagRank()          ==    5