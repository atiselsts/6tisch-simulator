import os

import pytest

import test_utils as u
from SimEngine import SimConfig

#=== test to verify sim_engine is created/destroyed well

@pytest.mark.parametrize("dummycounter", [1,2,3,4])
def test_sim_engine_runs(sim_engine, dummycounter):
    pass

'''
#=== error test which verifies exception at initialization propagates up

@pytest.mark.parametrize("diff_config", [
    {'exec_numMotes': 'dummy'},
])
def test_exception_at_initialization(sim_engine, diff_config):
    """test if an exception raised in a SimEngine thread is propagated here
    """
    with pytest.raises(Exception):
        sim_engine = sim_engine(
            diff_config     = diff_config,
        )

#=== error test which verifies exception during runtime propagates up

@pytest.mark.parametrize("diff_config", [
    {'app_pkPeriod': 'dummy'},
])
def test_exception_at_runtime(sim_engine, diff_config):
    """test if an exception raised in a SimEngine thread is propagated here

    Run a simulation in one slotframe
    """
    sim_engine = sim_engine(
        diff_config     = diff_config,
    )
    with pytest.raises(Exception):
        u.run_until_asn(
            sim_engine,
            target_asn=1, # duration doesn't matter, simulation just need to be started
        )
'''

#=== testing force_initial_routing_and_schedule options

FORCE_INITIAL_ROUTING_AND_SCHEDULE = [False,True]
@pytest.fixture(params=FORCE_INITIAL_ROUTING_AND_SCHEDULE)
def force_initial_routing_and_schedule(request):
    return request.param

def test_instantiation(sim_engine, force_initial_routing_and_schedule):
    sim_engine = sim_engine(
        diff_config                         = {},
        force_initial_routing_and_schedule  = force_initial_routing_and_schedule,
    )

#=== test verify default configs from bin/config.json are loaded correctly

def test_sim_config(sim_engine):
    
    root_dir    = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    config_file = os.path.join(root_dir, 'bin/config.json')
    sim_config  = SimConfig.SimConfig(config_file)

    sim_engine = sim_engine()
    sim_engine.is_alive()
    for (k,v) in sim_config.config['settings']['regular'].items():
        assert getattr(sim_engine.settings,k) == v

#=== test run_until_asn() util works

TARGET_ASN_TO_PAUSE = range(1,100,10)
@pytest.fixture(params=TARGET_ASN_TO_PAUSE)
def target_asn_to_pause(request):
    return request.param

def test_run_until_at_asn(sim_engine, target_asn_to_pause):
    sim_engine = sim_engine()

    assert sim_engine.getAsn() == 0
    u.run_until_asn(sim_engine, target_asn_to_pause)
    assert sim_engine.getAsn() == target_asn_to_pause
