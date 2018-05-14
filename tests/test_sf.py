"""
Tests for SimEngine.Mote.sf
"""

import test_utils as u
from SimEngine import SimLog

def test_msf_traffic_adaptation(sim_engine):
    """ Test Scheduling Function Traffic Adaptation
    - objective   : test if msf increases the number of cells
    - precondition: form a 2-mote linear network
    - precondition: the network is formed
    - action      : increase the app pkPeriod
    - expectation : MSF should trigger ADD_REQUEST_TX
    """

    sim_engine = sim_engine(
        {
            'app_pkPeriod':  10,
            'exec_numMotes': 2,
            'sf_class':      'MSF',
            'conn_class':    'FullyMeshed',
        },
    )

    root  = sim_engine.motes[0]
    node1 = sim_engine.motes[1]
    first_stop = 5 * 60 * 100
    second_stop = first_stop + 5 * 60 * 100

    # give the network time to form
    u.run_until_asn(sim_engine, first_stop)

    # increase data rate
    sim_engine.settings.app_pkPeriod = 1

    # give the sf time to adapt traffic
    u.run_until_asn(sim_engine, second_stop)

    # check ADD_REQUEST where triggered after first stop
    logs = u.read_log_file(filter=[SimLog.LOG_SIXP_ADD_REQUEST_TX['type']], after_asn=first_stop)
    assert len(logs) > 0
