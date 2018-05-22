import pytest

import test_utils as u
import SimEngine
import SimEngine.Mote.MoteDefines as d


APP = ['AppPeriodic', 'AppBurst']
@pytest.fixture(params=APP)
def app(request):
    return request.param

def test_app_upstream(
        sim_engine,
        app
    ):
    """Test Application Upstream Traffic
    - objective   : test if app generates and sends packets as expected
    - precondition: form a 2-mote linear network
    - precondition: app sends 5 packets during the simulation time
    - action      : run the simulation for 10 seconds
    - expectation : each application sends five packets
    """

    sim_engine = sim_engine(
        {
            'exec_numMotes'                            : 2,
            'exec_numSlotframesPerRun'                 : 11,
            'sf_type'                                  : 'SFNone',
            'conn_class'                               : 'Linear',
            'tsch_probBcast_ebDioProb'                 : 0,
            'app'                                      : app,
            'app_pkPeriod'                             : 2,
            'app_pkPeriodVar'                          : 0,
            'app_pkLength'                             : 90,
            'app_burstTimestamp'                       : 1,
            'app_burstNumPackets'                      : 5,
        },
        force_initial_routing_and_scheduling_state = True,
    )

    # give the network time to form
    u.run_until_asn(sim_engine, 1010)

    # the number of 'app.tx' is the same as the number of generated packets.
    logs = u.read_log_file(filter=['app.tx'])

    # five packets should be generated per application
    assert len(logs) == 5
