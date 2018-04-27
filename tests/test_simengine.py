from SimEngine import SimEngine
'''
def test_create_destroy_engine(repeat4times):
    engine = SimEngine.DiscreteEventEngine()
    print id(engine)
    engine.destroy()
'''
def test_create_start_destroy_engine(repeat4times):
    engine = SimEngine.DiscreteEventEngine()
    engine.start()
    engine.join()

class StateOfTest(object):
    def __init__(self):
        self.events = []
    def _cb_asn_1_1(self):
        self.events += ['1.1']
    def _cb_asn_1_2(self):
        self.events += ['1.2']
    def _cb_asn_2(self):
        self.events += ['2']

def test_event_execution_order(repeat4times):

    # create engine
    engine = SimEngine.DiscreteEventEngine()
    engine.scheduleAtAsn(
        asn         = 10,
        cb          = engine._actionEndSim,
        uniqueTag   = ('engine','_actionEndSim'),
    )
    stateoftest = StateOfTest()

    # schedule events (out of order)
    engine.scheduleAtAsn(
        asn         = 1,
        cb          = stateoftest._cb_asn_1_1,
        uniqueTag   = ('stateoftest','_cb_asn_1_1'),
        priority    = 1,
    )
    engine.scheduleAtAsn(
        asn         = 2,
        cb          = stateoftest._cb_asn_2,
        uniqueTag   = ('stateoftest','_cb_asn_2'),
    )
    engine.scheduleAtAsn(
        asn         = 1,
        cb          = stateoftest._cb_asn_1_2,
        uniqueTag   = ('stateoftest','_cb_asn_1_2'),
        priority    = 2,
    )

    # run engine, run until done
    assert not engine.is_alive()
    engine.start()
    engine.join()
    assert not engine.is_alive()

    # verify we got the right events
    assert stateoftest.events == ['1.1','1.2','2']
