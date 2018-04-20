import time
from SimEngine.SimEngine import SimEngine
from SimEngine.SimSettings import SimSettings


class TestSingleton:

    @classmethod
    def setup_method(cls):
        # make sure a default SimSettings instance
        settings = SimSettings(**{
            'exec_numMotes': 1,
            'exec_simDataDir': "simData",
            'app_pkPeriod': 0,
            'rpl_dioPeriod': 0,
            'rpl_daoPeriod': 0,
            'sf_type': 'SSF-symmetric',
            'secjoin_enabled': False,
            'tsch_slotDuration': 0.010,
            'tsch_slotframeLength': 101,
            'tsch_ebPeriod_sec': 0,
            'top_type': 'linear',
            'top_squareSide': 2.000,
            'top_fullyMeshed': False,
            'prop_type': 'pisterhack',
            'phy_noInterference': True,
            'phy_minRssi': -97})
        start_time = time.strftime("%Y%m%d-%H%M%S")
        settings.setStartTime(start_time)
        settings.setCombinationKeys([])

    def teardown_method(cls):
        # make sure a SimEngine instance created during a test is destroyed
        engine = SimEngine()
        engine.destroy()

        settings = SimSettings()
        settings.destroy()

    def test_instantiate(self):
        # the second call of SimEngine() should return the same instance as the
        # first call.
        engine1 = SimEngine()
        engine2 = SimEngine()
        assert id(engine1) == id(engine2)

    def test_destroy(self):
        # after calling destroy(), SimEngine() should return a different (new)
        # instance to one returned before.
        engine1 = SimEngine()
        engine1.destroy()
        engine2 = SimEngine()
        assert id(engine1) != id(engine2)
