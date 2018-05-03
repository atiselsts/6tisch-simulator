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
    - precondition: app sends 5 packets during the simualtion time
    - action      : run the simulation for 10 seconds
    - expectation : each application sends five packets
    """

    sim_engine = sim_engine(
        {
            'exec_numMotes'                            : 2,
            'exec_numSlotframesPerRun'                 : 11,
            'sf_type'                                  : 'SSFSymmetric',
            'conn_type'                                : 'linear',
            'tsch_probBcast_ebProb'                    : 0,
            'tsch_probBcast_dioProb'                   : 0,
            'app'                                      : app,
            'app_pkPeriod'                             : 2,
            'app_pkPeriodVar'                          : 0,
            'app_pkLength'                             : 90,
            'app_burstTimestamp'                       : 1,
            'app_burstNumPackets'                      : 5,
            'app_e2eAck'                               : False,
        },
        force_initial_routing_and_scheduling_state = True
    )

    # run the simulation for 1010 timeslots (10 seconds)
    u.run_until_asn(sim_engine, 1000)

    # the number of 'app.tx' is the same as the number of generated packets.
    logs = u.read_log_file(filter=['app.tx'])

    # five packets should be generated per application
    assert len(logs) == 5

def test_app_ack_by_root(sim_engine):
    """Test Application Acknowledgement by Root
    - objective   : test if root sends back appliaction ack
    - precondition: form a 2-mote linear network
    - precondition: root is configured to send application ack
    - action      : send an application packet to root
    - expectation : root generates an ack
    """

    sim_engine = sim_engine(
        {
            'exec_numMotes'                            : 2,
            'sf_type'                                  : 'SSFSymmetric',
            'conn_type'                                : 'linear',
            'tsch_probBcast_ebProb'                    : 0,
            'tsch_probBcast_dioProb'                   : 0,
            'app'                                      : 'AppBurst',
            'app_pkPeriod'                             : 0,
            'app_pkPeriodVar'                          : 0,
            'app_pkLength'                             : 90,
            'app_burstTimestamp'                       : 1,
            'app_burstNumPackets'                      : 1,
            'app_e2eAck'                               : True,
        },
        force_initial_routing_and_scheduling_state = True
    )

    # run the simulation
    u.run_until_asn(sim_engine, 1000)

    # correct logs
    logs = u.read_log_file(
        filter=[
            'app.rx'
        ]
    )

    # root should receive one app packet
    assert len([log for log in logs if ((log['_mote_id'] == 0) and (log['packet']['type'] == d.APP_TYPE_DATA) )]) == 1

    # ack should be received by the mote
    assert len([log for log in logs if ((log['_mote_id'] == 1) and (log['packet']['type'] == d.APP_TYPE_DATA) )]) == 1
