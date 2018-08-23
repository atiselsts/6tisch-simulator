import json
import os
import re
import subprocess
import types

import pytest

import test_utils as u
from SimEngine import SimLog
from SimEngine import SimSettings
import SimEngine.Mote.MoteDefines as d


@pytest.fixture(params=['PerHopReassembly', 'FragmentForwarding'])
def fragmentation(request):
    return request.param


@pytest.fixture(params=[90, 180])
def app_pkLength(request):
    return request.param


@pytest.fixture(params=['without_pkt_loss', 'with_pkt_loss'])
def pkt_loss_mode(request):
    return request.param


def test_avg_hops(sim_engine, fragmentation, app_pkLength, pkt_loss_mode):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numSlotframesPerRun': 40,
            'exec_numMotes'           : 10,
            'fragmentation'           : fragmentation,
            'app'                     : 'AppPeriodic',
            'app_pkPeriod'            : 0,
            'app_pkLength'            : app_pkLength,
            'tsch_probBcast_ebProb'   : 0,
            'rpl_daoPeriod'           : 0,
            'conn_class'              : 'Linear'
        },
        force_initial_routing_and_scheduling_state = True,
    )

    # in this test, the leaf sends two application packets. when pkt_loss_mode
    # is 'with_pkt_loss', the second application packet will be lost at the
    # root.

    # shorthands
    root = sim_engine.motes[0]
    leaf = sim_engine.motes[-1]
    sim_settings = SimSettings.SimSettings()

    # make the app send an application packet
    leaf.app._send_a_single_packet()

    # wait for some time
    u.run_until_asn(sim_engine, 2020)

    # the root should receive the first application packet
    logs = u.read_log_file([SimLog.LOG_APP_RX['type']])
    assert len(logs) == 1
    assert logs[0]['_mote_id'] == root.id
    assert logs[0]['packet']['net']['srcIp'] == leaf.get_ipv6_global_addr()
    assert logs[0]['packet']['net']['dstIp'] == root.get_ipv6_global_addr()
    assert logs[0]['packet']['type'] == d.PKT_TYPE_DATA

    # make the root not receive at 6LoWPAN layer anything if pkt_loss_mode is
    # 'with_pkt_loss'
    if   pkt_loss_mode == 'with_pkt_loss':
        assert root.dagRoot is True
        def recvPacket(self, packet):
            # do nothing; ignore the incoming packet
            pass
        root.sixlowpan.recvPacket = types.MethodType(
            recvPacket,
            root.sixlowpan
        )
    elif pkt_loss_mode == 'without_pkt_loss':
        # do nothing
        pass
    else:
        raise NotImplemented()

    # make the app send another application packet
    leaf.app._send_a_single_packet()

    # run the simulator until it ends
    u.run_until_end(sim_engine)

    # confirm the leaf sent two application packets
    logs = u.read_log_file([SimLog.LOG_APP_TX['type']])
    assert len(logs) == 2
    for i in range(2):
        assert logs[i]['_mote_id'] == leaf.id
        assert logs[i]['packet']['net']['srcIp'] == leaf.get_ipv6_global_addr()
        assert logs[i]['packet']['net']['dstIp'] == root.get_ipv6_global_addr()
        assert logs[i]['packet']['type'] == d.PKT_TYPE_DATA

    # run compute_kpis.py against the log file
    compute_kpis_path = os.path.join(
        os.path.dirname(__file__),
        '../bin',
        'compute_kpis.py'
    )
    output = subprocess.check_output(
        '{0} \'{1}\''.format(
            'python',
            compute_kpis_path
        ),
        shell=True
    ).split('\n')

    # remove blank lines
    output = [line for line in output if not re.match(r'^\s*$', line)]

    # confirm if compute_kpis.py referred the right log file
    # the first line of output has the log directory name
    assert re.search(sim_settings.getOutputFile(), output[0]) is not None

    # convert the body of the output, which is a JSON string, to an object
    json_string = '\n'.join(output[1:-1])
    kpis = json.loads(json_string)

    # the avg_hops should be the same number as leaf.id since we use a linear
    # topology here.
    assert kpis['null'][str(leaf.id)]['avg_hops'] == leaf.id
