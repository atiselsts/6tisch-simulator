import os

import pytest

import test_utils as u
from SimEngine import SimConfig

#=== error test which verifies exception at initialization propagates up
@pytest.mark.parametrize("diff_config", [
    {'exec_numMotes': None},
])
def test_exception_at_initialization(sim_engine, diff_config):
    """test if an exception raised in a SimEngine thread is propagated here
    """
    with pytest.raises(Exception):
        sim_engine(diff_config)


#=== test which verifies exception during runtime propagates up

@pytest.mark.parametrize("diff_config", [
    {'secjoin_enabled': None},
])
def test_exception_at_runtime(sim_engine, diff_config):
    """test if an exception raised in a SimEngine thread is propagated here

    Run a simulation in one slotframe
    """
    sim_engine = sim_engine(diff_config)
    with pytest.raises(Exception):
        u.run_until_asn(
            sim_engine,
            target_asn=1, # duration doesn't matter, simulation just need to be started
        )

#=== testing all combination of force_initial_routing_state force_initial_schedule

FORCE_INITIAL_ROUTING_STATE = [True,False]
@pytest.fixture(params=FORCE_INITIAL_ROUTING_STATE)
def force_initial_routing_state(request):
    return request.param

FORCE_INITIAL_SCHEDULE = [True,False]
@pytest.fixture(params=FORCE_INITIAL_SCHEDULE)
def force_initial_schedule(request):
    return request.param

def test_instantiation(sim_engine, force_initial_routing_state, force_initial_schedule):
    sim_engine = sim_engine(
        diff_config                    = {},
        force_initial_routing_state    = force_initial_routing_state,
        force_initial_schedule         = force_initial_schedule,
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
