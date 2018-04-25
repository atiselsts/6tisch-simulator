import os

import pytest

from test_utils import run_until_at_asn
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
        run_until_at_asn(
            sim_engine,
            target_asn=1, # duration doesn't matter, simulation just need to be started
        )

#=== testing all combination of initial_rpl_state initial_tsch_scheduling

INITIAL_RPL_STATE_VALS = [True,False]
@pytest.fixture(params=INITIAL_RPL_STATE_VALS)
def initial_rpl_state(request):
    return request.param

INITIAL_TSCH_SCHEDULING = [True,False]
@pytest.fixture(params=INITIAL_TSCH_SCHEDULING)
def initial_tsch_scheduling(request):
    return request.param

def test_instantiation(sim_engine, initial_rpl_state, initial_tsch_scheduling):
    sim_engine = sim_engine(
        diff_configs            = {},
        initial_rpl_state       = initial_rpl_state,
        initial_tsch_scheduling = initial_tsch_scheduling,
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

#=== test run_until_at_asn() util works

TARGET_ASN_TO_PAUSE = range(1,100,10)
@pytest.fixture(params=TARGET_ASN_TO_PAUSE)
def target_asn_to_pause(request):
    return request.param

def test_run_until_at_asn(sim_engine, target_asn_to_pause):
    sim_engine = sim_engine()

    assert sim_engine.getAsn() == 0
    run_until_at_asn(sim_engine, target_asn_to_pause)
    assert sim_engine.getAsn() == target_asn_to_pause
