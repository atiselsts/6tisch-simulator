import os

import pytest

import test_utils as u
from SimEngine import SimConfig

#=== test to verify sim_engine is created/destroyed well

@pytest.mark.parametrize("dummycounter", [1,2,3,4])
def test_sim_engine_runs(sim_engine, dummycounter):
    pass

#=== error test which verifies exception at initialization propagates up

@pytest.mark.parametrize("diff_config", [
    {'app_pkPeriod': 'dummy'},
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
    {'secjoin_enabled': None},
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

#=== testing force_initial_routing_and_scheduling_state options

FORCE_INITIAL_ROUTING_AND_SCHEDULING_STATE = [None, 'linear']
@pytest.fixture(params=FORCE_INITIAL_ROUTING_AND_SCHEDULING_STATE)
def force_initial_routing_and_scheduling_state(request):
    return request.param

def test_instantiation(sim_engine, force_initial_routing_and_scheduling_state):
    print force_initial_routing_and_scheduling_state
    sim_engine = sim_engine(
        diff_config                         = {},
        force_initial_routing_and_scheduling_state  = force_initial_routing_and_scheduling_state,
    )

#=== test verify default configs from bin/config.json are loaded correctly

def test_sim_config(sim_engine):

    sim_config  = SimConfig.SimConfig(u.CONFIG_FILE_PATH)

    sim_engine = sim_engine()
    for (k,v) in sim_config.config['settings']['regular'].items():
        assert getattr(sim_engine.settings,k) == v

#=== test run_until_asn() util works

TARGET_ASN_TO_PAUSE = range(1,100,10)
@pytest.fixture(params=TARGET_ASN_TO_PAUSE)
def target_asn_to_pause(request):
    return request.param

def test_run_until_asn(sim_engine, target_asn_to_pause):
    sim_engine = sim_engine({'exec_numMotes': 1})

    assert sim_engine.getAsn() == 0
    u.run_until_asn(sim_engine, target_asn_to_pause)
    assert sim_engine.getAsn() == target_asn_to_pause
