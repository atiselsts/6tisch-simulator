import pytest

import test_utils as u
import SimEngine
import SimEngine.Mote.MoteDefines as d


APP = ['AppPeriodic', 'AppBurst']
@pytest.fixture(params=APP)
def app(request):
    return request.param

@pytest.fixture(params=[0, 60])
def fixture_dao_period(request):
    return request.param

def test_app_upstream(
        sim_engine,
        app,
        fixture_dao_period
    ):

    # at least one app packet should be observed during the simulation

    sim_engine = sim_engine(
        {
            'exec_numMotes'                            : 2,
            'exec_numSlotframesPerRun'                 : 1000,
            'sf_class'                                 : 'SFNone',
            'conn_class'                               : 'Linear',
            'secjoin_enabled'                          : False,
            'app'                                      : app,
            'app_pkPeriod'                             : 2,
            'app_pkPeriodVar'                          : 0,
            'app_pkLength'                             : 90,
            'app_burstTimestamp'                       : 1,
            'app_burstNumPackets'                      : 5,
            'rpl_daoPeriod'                            : fixture_dao_period
        }
    )

    # give the network time to form
    u.run_until_end(sim_engine)

    # the number of 'app.tx' is the same as the number of generated packets.
    logs = u.read_log_file(filter=['app.tx'])

    # five packets should be generated per application
    assert len(logs) > 0
