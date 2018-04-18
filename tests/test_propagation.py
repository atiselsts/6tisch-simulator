from SimEngine import Propagation
from SimEngine import SimSettings
from SimEngine.Mote import Mote

import pytest


class TestSingleton:

    @classmethod
    def setup_method(cls):
        # make sure a default SimSettings instance
        SimSettings.SimSettings(**{
            'exec_numMotes': 1,
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

    def teardown_method(cls):
        # make sure a Propagation instance created during a test is destroyed
        engine = Propagation.Propagation()
        engine.destroy()

        settings = SimSettings.SimSettings()
        settings.destroy()

    def test_instantiate(self):
        # the second call of Propagation() should return the same instance as the
        # first call.
        engine1 = Propagation.Propagation()
        engine2 = Propagation.Propagation()
        assert id(engine1) == id(engine2)

    def test_destroy(self):
        # after calling destroy(), Propagation.Propagation() should return a different (new)
        # instance to one returned before.
        engine1 = Propagation.Propagation()
        engine1.destroy()
        engine2 = Propagation.Propagation()
        assert id(engine1) != id(engine2)


def test_propagation_from_trace_get_pdr(sim):
    sim(**{'prop_trace': 'traces/grenoble.k7.gz',
           'top_fullyMeshed': False,
           'top_squareSide': 20})
    asn = 10
    source = Mote.Mote(1)
    destination = Mote.Mote(2)
    channel = 11
    propagation = Propagation.PropagationTrace(trace='traces/grenoble.k7.gz')

    propagation.get_pdr(source, destination, asn=asn, channel=channel)
    propagation.get_pdr(source, destination, asn=asn)
    propagation.get_pdr(source, destination, channel=channel)
