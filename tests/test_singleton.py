import time

import pytest

from SimEngine.SimEngine import SimEngine
from SimEngine.SimSettings import SimSettings
from SimEngine.SimLog import SimLog
from SimEngine.Connectivity import Connectivity


@pytest.fixture
def sim_settings():
    # SimSettings
    sim_settings = SimSettings(**{'exec_numMotes'       : 1,
                                  'exec_simDataDir'     : "simData",
                                  'app_pkPeriod'        : 0,
                                  'app_pkLength'        : 90,
                                  'rpl_daoPeriod'       : 0,
                                  'fragmentation'       : 'FragmentForwarding',
                                  'sf_type'             : 'SSFSymmetric',
                                  'secjoin_enabled'     : False,
                                  'tsch_slotDuration'   : 0.010,
                                  'tsch_slotframeLength': 101,
                                  'tsch_max_payload_len': 90,
                                  'conn_type'           : 'linear',
                                  'phy_noInterference'  : True,
                                  'phy_numChans'        : 16,
                                  'phy_minRssi'         : -97})

    sim_settings.setStartTime(time.strftime("%Y%m%d-%H%M%S"))
    sim_settings.setCombinationKeys([])

    # SimLog
    log = SimLog()
    log.set_log_filters([])

    yield

    # make sure a SimEngine instance created during a test is destroyed.
    engine = SimEngine()
    # Connectivity instance is also destroyed in engine.destroy()
    engine.destroy()

    settings = SimSettings()
    settings.destroy()

    log = SimLog()
    log.destroy()


@pytest.mark.parametrize("singleton_class",
                         [SimSettings, SimEngine, Connectivity, SimLog])
def test_instantiate(sim_settings, singleton_class):
    # the first SimSettings instance is created during setup
    instance_1 = singleton_class()
    instance_2 = singleton_class()
    assert id(instance_1) == id(instance_2)


@pytest.mark.parametrize("singleton_class",
                         [SimSettings, SimEngine, Connectivity, SimLog])
def test_destroy(sim_settings, singleton_class):
    # the first SimSettings instance is created during setup
    instance_1 = singleton_class()
    instance_1_id = id(instance_1)
    instance_1.destroy()
    instance_2 = singleton_class()
    assert instance_1_id != id(instance_2)
