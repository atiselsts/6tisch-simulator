import os
import pytest
import time

from SimEngine import SimConfig,   \
                      SimSettings, \
                      SimLog,      \
                      SimEngine

ROOT_DIR         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CONFIG_FILE_PATH = os.path.join(ROOT_DIR, 'bin/config.json')

@pytest.fixture(scope="function")
def sim_engine(request):

    def create_sim_engine(diff_configs={}, initial_rpl_state=None, initial_tsch_scheduling=None):

        sim_config = SimConfig.SimConfig(CONFIG_FILE_PATH)

        configs = sim_config.settings['regular']
        # retrieve exec_numMotes which is supposed to be in "combination"
        assert 'exec_numMotes' not in configs
        configs['exec_numMotes'] = sim_config.settings['combination']['exec_numMotes'][0]
        configs.update(**diff_configs)

        sim_settings = SimSettings.SimSettings(**configs)
        sim_settings.setStartTime(time.strftime('%Y%m%d-%H%M%S'))
        sim_settings.setCombinationKeys([])

        sim_log = SimEngine.SimLog.SimLog()
        sim_log.set_log_filters('all') # do not log

        sim_engine = SimEngine.SimEngine()

        def fin():
            try:
                need_terminate_sim_engine_thread = sim_engine.is_alive()
            except AssertionError:
                # sim_engine thread is not initialized for some reason.
                need_terminate_sim_engine_thread = False

            if need_terminate_sim_engine_thread:
                if sim_engine.simPaused:
                    # if the thread is paused, resume it so that an event for
                    # termination is scheduled; otherwise deadlock happens
                    sim_engine.play()
                sim_engine.terminateSimulation(1)
                sim_engine.join()

            sim_engine.destroy()
            sim_settings.destroy()
            sim_log.destroy()

        request.addfinalizer(fin)

        return sim_engine

    return create_sim_engine
