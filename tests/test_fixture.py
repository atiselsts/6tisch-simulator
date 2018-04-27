import pytest

import test_utils as u
from SimEngine import SimConfig

#============================ helpers =========================================

#============================ tests ===========================================

#=== test to verify sim_engine is created/destroyed well

def test_sim_engine_created(sim_engine, repeat4times):
    pass

#=== test to verify sim_engine is created/init/destroyed well

def test_sim_engine_created_and_init(sim_engine, repeat4times):
    s = sim_engine(
        diff_config = {
            'exec_numMotes': 1,
        }
    )

#=== exception during initialization

def test_exception_at_intialization(sim_engine, repeat4times):
    with pytest.raises(TypeError):
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes': 'dummy', # 'dummy' not int, causes exception
            }
        )

#=== runtime exception propagates past run_until_asn()

class MyException(Exception):
    pass

def _raiseException():
    raise MyException()

def test_exception_at_runtime(sim_engine, repeat4times):
    """test if an exception raised in a SimEngine thread is propagated here

    Run a simulation in one slotframe
    """
    sim_engine = sim_engine()
    sim_engine.scheduleAtAsn(
        asn         = 10,
        cb          = _raiseException,
        uniqueTag   = ('engine','_raiseException'),
    )
    
    with pytest.raises(MyException):
        u.run_until_asn(
            sim_engine,
            target_asn = 20, # past the _raiseException event
        )

#=== testing force_initial_routing_and_scheduling_state options

FORCE_INITIAL_ROUTING_AND_SCHEDULING_STATE = [False]
@pytest.fixture(params=FORCE_INITIAL_ROUTING_AND_SCHEDULING_STATE)
def force_initial_routing_and_scheduling_state(request):
    return request.param

def test_instantiation(sim_engine, force_initial_routing_and_scheduling_state, repeat4times):
    sim_engine = sim_engine(
        diff_config                                   = {},
        force_initial_routing_and_scheduling_state    = force_initial_routing_and_scheduling_state,
    )

#=== verify default configs from bin/config.json are loaded correctly

def test_sim_config(sim_engine, repeat4times):

    sim_config  = SimConfig.SimConfig(u.CONFIG_FILE_PATH)

    sim_engine = sim_engine()
    for (k,v) in sim_config.config['settings']['regular'].items():
        assert getattr(sim_engine.settings,k) == v

#=== test that run_until_asn() works

def test_run_until_asn(sim_engine, repeat4times):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':            1,
            'exec_numSlotframesPerRun': 1,
        }
    )
    
    assert sim_engine.getAsn() == 0
    
    for target_asn in range(1,10,5):
        u.run_until_asn(
            sim_engine,
            target_asn = target_asn,
        )
        assert sim_engine.getAsn() == target_asn
