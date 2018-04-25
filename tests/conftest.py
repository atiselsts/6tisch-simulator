import pytest
import time

from SimEngine import SimEngine

ROOT_DIR         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
CONFIG_FILE_PATH = os.path.join(ROOT_DIR, 'bin/config.json')

@pytest.fixture(scope="function")
def sim_engine(request):

    def create_sim_engine(diff_configs={}, initial_rpl_state=None, initial_tsch_scheduling=None):

        settings = SimEngine.SimSettings.SimSettings(**configs)
        settings.setStartTime(time.strftime('%Y%m%d-%H%M%S'))
        settings.setCombinationKeys([])

        log = SimEngine.SimLog.SimLog()
        log.set_log_filter([]) # do not log

        engine = SimEngine.SimEngine()
        print settings, type(engine)

        def fin():
            try:
                if engine.is_alive():
                    # the thread is running, which needs to be stopped
                    # 1 is the possible minimum delay for terminateSimulation()
                    engine.terminateSimulation(delay=1)
                    engine.join()
            except AssertionError:
                # a thread for the engine is not initialized
                pass
            engine.destroy()
            settings.destroy()
            log.destroy()

        request.addfinalizer(fin)

        return engine

    return create_sim_engine
