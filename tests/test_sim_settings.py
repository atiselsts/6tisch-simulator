from SimEngine.SimSettings import SimSettings


class TestSingleton:

    @classmethod
    def teardown_method(cls):
        # make sure a SimSettings instance created during a test is destroyed
        settings = SimSettings()
        settings.destroy()

    def test_instantiate(self):
        # the second call of SimSettings() should return the same instance as the
        # first call.
        settings1 = SimSettings()
        settings2 = SimSettings()
        assert id(settings1) == id(settings2)

    def test_destroy(self):
        # after calling destroy(), SimSettings() should return a different (new)
        # instance to one returned before.
        settings1 = SimSettings()
        settings1.destroy()
        settings2 = SimSettings()
        assert id(settings1) != id(settings2)
