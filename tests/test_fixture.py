import os

import pytest

from test_utils import run_until_at_asn
from SimEngine import SimConfig


# diff_configs should have a configuration which causes an exception when a
# simulation is instantiate
@pytest.mark.parametrize("diff_configs", [
    {'exec_numMotes': None},
])
def test_exception_in_instantiation(sim_engine, diff_configs):
    """test if an exception raised in a SimEngine thread is propagated here
    """
    with pytest.raises(Exception):
        sim_engine(diff_configs)


# diff_configs should have a configuration which causes an exception when a
# simulation starts
@pytest.mark.parametrize("diff_configs", [
    {'secjoin_enabled': None},
])
def test_exception_in_thread(sim_engine, diff_configs):
    """test if an exception raised in a SimEngine thread is propagated here

    Run a simulation in one slotframe
    """
    sim_engine = sim_engine(diff_configs)
    with pytest.raises(Exception):
        run_until_at_asn(sim_engine,
                         target_asn=sim_engine.settings.tsch_slotframeLength)


@pytest.mark.parametrize('initial_rpl_state, initial_tsch_scheduling', [
    (False, False),
    (True,  False),
    (False, True),
    (True,  True)
])
def test_instantiation(sim_engine, initial_rpl_state, initial_tsch_scheduling):
    sim_engine = sim_engine(diff_configs            = {},
                            initial_rpl_state       = initial_rpl_state,
                            initial_tsch_scheduling = initial_tsch_scheduling)


def test_sim_config(sim_engine):
    """sim should have all the regular configs in bin/config.json by default
    """

    root_dir    = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    config_file = os.path.join(root_dir, 'bin/config.json')
    sim_config  = SimConfig.SimConfig(config_file)

    sim_engine = sim_engine()
    sim_engine.is_alive()
    for key, value in sim_config.config['settings']['regular'].items():
        assert getattr(sim_engine.settings, key) == value


@pytest.mark.parametrize('target_asn_to_pause', [
    1
])
def test_run_until_at_asn(sim_engine, target_asn_to_pause):
    sim_engine = sim_engine()
    print sim_engine.is_alive()

    assert sim_engine.getAsn() == 0
    run_until_at_asn(sim_engine, target_asn_to_pause)
    print sim_engine.is_alive()
    assert sim_engine.getAsn() == target_asn_to_pause
