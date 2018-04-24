import time

import pytest

from SimEngine.SimEngine import SimEngine
from SimEngine.SimSettings import SimSettings
from SimEngine.Propagation import Propagation


@pytest.fixture
def sim_settings():
    sim_settings = SimSettings(
        **{
            'exec_numMotes':           1,
            'exec_simDataDir':         "simData",
            'app_pkPeriod':            0,
            'rpl_daoPeriod':           0,
            'sf_type':                 'SSF-symmetric',
            'secjoin_enabled':         False,
            'tsch_slotDuration':       0.010,
            'tsch_slotframeLength':    101,
            'top_type':                'linear',
            'top_squareSide':          2.000,
            'top_fullyMeshed':         False,
            'prop_type':               'pisterhack',
            'phy_noInterference':      True,
            'phy_minRssi':             -97,
        }
    )
    sim_settings.setStartTime(time.strftime("%Y%m%d-%H%M%S"))
    sim_settings.setCombinationKeys([])
    yield

    # make sure a SimEngine instance created during a test is destroyed.
    engine = SimEngine()
    # Propagation instance is also destroyed in engine.destroy()
    engine.destroy()

    settings = SimSettings()
    settings.destroy()


@pytest.mark.parametrize("singleton_class",
                         [SimSettings, SimEngine, Propagation])
def test_instantiate(sim_settings, singleton_class):
    # the first SimSettings instance is created during setup
    instance_1 = singleton_class()
    instance_2 = singleton_class()
    assert id(instance_1) == id(instance_2)


@pytest.mark.parametrize("singleton_class",
                         [SimSettings, SimEngine, Propagation])
def test_destroy(sim_settings, singleton_class):
    # the first SimSettings instance is created during setup
    instance_1 = SimEngine()
    instance_1_id = id(instance_1)
    instance_1.destroy()
    instance_2 = SimEngine()
    assert instance_1_id != id(instance_2)
