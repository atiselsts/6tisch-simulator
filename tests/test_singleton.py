import time

import pytest

from SimEngine.SimEngine import SimEngine
from SimEngine.SimConfig import SimConfig
from SimEngine.SimSettings import SimSettings
from SimEngine.SimLog import SimLog
from SimEngine.Connectivity import Connectivity
import test_utils as u

@pytest.fixture
def sim_settings():
    # get default configuration
    sim_config = SimConfig(u.CONFIG_FILE_PATH)
    config = sim_config.settings['regular']
    assert 'exec_numMotes' not in config
    config['exec_numMotes'] = sim_config.settings['combination']['exec_numMotes'][0]

    settings = SimSettings(**config)
    settings.setStartTime(time.strftime("%Y%m%d-%H%M%S"))
    settings.setCombinationKeys([])

    # SimLog
    log = SimLog()
    log.set_log_filters([])

    yield

    # SimEngine() in the next line may need a SimSettings instance having the
    # default configuration. The instance created above could be destroyed in a
    # test code. To make sure a meaningful SimSettigs instance is newly
    # created, call destroy() to an instance returned by SimSettings(), which
    # could be one created in a test code.
    SimSettings().destroy()
    settings = SimSettings(**config)

    # make sure a SimEngine instance created during a test is destroyed.
    engine = SimEngine()

    engine.destroy()
    settings.destroy()
    Connectivity().destroy()

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
