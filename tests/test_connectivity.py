"""
Tests for SimEngine.Connectivity
"""
import itertools
import json
import gzip
import os
import random
import types

import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog
from SimEngine.Connectivity import ConnectivityMatrixK7

#============================ helpers =========================================

def destroy_all_singletons(engine):
    engine.destroy()
    engine.connectivity.destroy()
    engine.settings.destroy()
    SimLog.SimLog().destroy()

#============================ tests ===========================================

def test_linear_matrix(sim_engine):
    """ verify the connectivity matrix for the 'Linear' class is as expected

    creates a static connectivity linear path
    0 <-- 1 <-- 2 <-- ... <-- num_motes
    """

    num_motes = 6
    engine = sim_engine(
        diff_config = {
            'exec_numMotes': num_motes,
            'conn_class':    'Linear',
        }
    )
    motes  = engine.motes
    matrix = engine.connectivity.matrix

    matrix.dump()

    assert motes[0].dagRoot is True

    for c in range(0, num_motes):
        for p in range(0, num_motes):
            if (c == p+1) or (c+1 == p):
                for channel in d.TSCH_HOPPING_SEQUENCE:
                    assert matrix.get_pdr(c, p, channel)  ==  1.00
                    assert matrix.get_rssi(c, p, channel) ==   -10
            else:
                for channel in d.TSCH_HOPPING_SEQUENCE:
                    assert matrix.get_pdr(c, p, channel)  ==  0.00
                    assert matrix.get_rssi(c, p, channel) == -1000


#=== verify propagate function doesn't raise exception

def test_propagate(sim_engine):
    engine = sim_engine()
    engine.connectivity.propagate()


#=== test for ConnectivityRandom
class TestRandom(object):

    def test_free_run(self, sim_engine):
        # all the motes should be able to join the network
        sim_engine = sim_engine(
            diff_config = {
                'exec_numSlotframesPerRun'      : 10000,
                'conn_class'                    : 'Random',
                'secjoin_enabled'               : False,
                "phy_numChans"                  : 1,
            }
        )
        asn_at_end_of_simulation = (
            sim_engine.settings.tsch_slotframeLength *
            sim_engine.settings.exec_numSlotframesPerRun
        )

        u.run_until_everyone_joined(sim_engine)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

    def test_getter(self, sim_engine):
        num_channels = 2
        sim_engine = sim_engine(
            diff_config = {
                'conn_class'                    : 'Random',
                'exec_numMotes'                 : 2,
                'conn_random_init_min_neighbors': 1,
                'phy_numChans'                  : num_channels,
            }
        )

        # PDR and RSSI should not change over time
        for src, dst in zip(sim_engine.motes[:-1], sim_engine.motes[1:]):
            for channel in d.TSCH_HOPPING_SEQUENCE[:num_channels]:
                pdr  = []
                rssi = []

                for _ in range(100):
                    pdr.append(
                        sim_engine.connectivity.get_pdr(
                            src_id  = src.id,
                            dst_id  = dst.id,
                            channel = channel
                        )
                    )
                    rssi.append(
                        sim_engine.connectivity.get_rssi(
                            src_id  = src.id,
                            dst_id  = dst.id,
                            channel = channel
                        )
                    )
                    # proceed the simulator
                    u.run_until_asn(sim_engine, sim_engine.getAsn() + 1)

                # compare two consecutive PDRs and RSSIs. They should be always
                # the same value. Then, the following condition of 'i != j'
                # should always false
                assert sum([(i != j) for i, j in zip(pdr[:-1], pdr[1:])])   == 0
                assert sum([(i != j) for i, j in zip(rssi[:-1], rssi[1:])]) == 0

        # PDR and RSSI should be the same within the same slot, of course
        for src, dst in zip(sim_engine.motes[:-1], sim_engine.motes[1:]):
            for channel in d.TSCH_HOPPING_SEQUENCE[:num_channels]:
                pdr  = []
                rssi = []

                for _ in range(100):
                    pdr.append(
                        sim_engine.connectivity.get_pdr(
                            src_id  = src.id,
                            dst_id  = dst.id,
                            channel = channel
                        )
                    )
                    rssi.append(
                        sim_engine.connectivity.get_rssi(
                            src_id  = src.id,
                            dst_id  = dst.id,
                            channel = channel
                        )
                    )

                # compare two consecutive PDRs and RSSIs; all the pairs should
                # be same (all comparison, i != j, should be False).
                assert sum([(i != j) for i, j in zip(pdr[:-1], pdr[1:])])   == 0
                assert sum([(i != j) for i, j in zip(rssi[:-1], rssi[1:])]) == 0


    def test_context_random_seed(self, sim_engine):
        diff_config = {
            'exec_numMotes'  : 10,
            'exec_randomSeed': 'context',
            'conn_class'     : 'Random'
        }

        # ConnectivityRandom should create an identical topology for two
        # simulations having the same run_id
        sf_class_list = ['SFNone', 'MSF']
        coordinates = {}
        for sf_class, run_id in itertools.product(sf_class_list, [1, 2]):
            diff_config['sf_class'] = sf_class
            engine = sim_engine(
                diff_config                                = diff_config,
                force_initial_routing_and_scheduling_state = False,
                run_id                                     = run_id
            )
            coordinates[(sf_class, run_id)] = (
                engine.connectivity.matrix.coordinates
            )
            destroy_all_singletons(engine)

        # We have four sets of coordinates:
        # - coordinates of ('SFNone', run_id=1) and ('MSF',    1) should be
        #   identical
        # - coordinates of ('SFNone', run_id=2) and ('MSF',    2) should be
        #   identical
        # - coordinates of ('SFNone,  run_id=1) and ('SFNone', 2) should be
        #   different
        # - coordinates of ('MSF',    run_id=1) and ('MSF',    2) should be
        #   different
        assert coordinates[('SFNone', 1)] == coordinates[('MSF', 1)]
        assert coordinates[('SFNone', 2)] == coordinates[('MSF', 2)]
        assert coordinates[('SFNone', 1)] != coordinates[('SFNone', 2)]
        assert coordinates[('MSF', 1)]    != coordinates[('MSF', 2)]

#=== test for LockOn mechanism that is implemented in propagate()
def test_lockon(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'           : 2,
            'exec_numSlotframesPerRun': 1,
            'conn_class'              : 'Linear',
            'app_pkPeriod'            : 0,
            'secjoin_enabled'         : False,
            'sf_class'                : 'SFNone',
            'tsch_probBcast_ebProb'   : 0,
            'rpl_daoPeriod'           : 0
        }
    )

    # short-hands
    root  = sim_engine.motes[0]
    hop_1 = sim_engine.motes[1]

    # force hop_1 to join the network
    eb = root.tsch._create_EB()
    hop_1.tsch._action_receiveEB(eb)
    dio = root.rpl._create_DIO()
    dio['mac'] = {'srcMac': root.get_mac_addr()}
    hop_1.rpl.action_receiveDIO(dio)

    # let hop_1 send an application packet
    hop_1.app._send_a_single_packet()

    # force random.random() to return 1, which will cause any frame not to be
    # received by anyone
    _random = random.random
    def return_one(self):
        return float(1)
    random.random = types.MethodType(return_one, random)

    # run the simulation
    u.run_until_end(sim_engine)

    # put the original random() back to random
    random.random = _random

    # root shouldn't lock on the frame hop_1 sent since root is not expected to
    # receive even the preamble of the packet.
    logs = u.read_log_file([SimLog.LOG_PROP_DROP_LOCKON['type']])
    assert len(logs) == 0

#=== test if the simulator ends without an error

ROOT_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TRACE_FILE_PATH = os.path.join(ROOT_DIR, 'traces/grenoble.k7.gz')

@pytest.fixture(params=['FullyMeshed', 'Linear', 'K7', 'Random'])
def fixture_conn_class(request):
    return request.param

def test_runsim(sim_engine, fixture_conn_class):
    # run the simulation with each conn_class. use a shorter
    # 'exec_numSlotframesPerRun' so that this test doesn't take long time
    diff_config = {
        'exec_numSlotframesPerRun': 100,
        'conn_class'              : fixture_conn_class
    }
    if fixture_conn_class == 'K7':
        with gzip.open(TRACE_FILE_PATH, 'r') as trace:
            header = json.loads(trace.readline())
            diff_config['exec_numMotes'] = header['node_count']
        diff_config['conn_trace'] = TRACE_FILE_PATH

    sim_engine = sim_engine(diff_config=diff_config)
    u.run_until_end(sim_engine)


@pytest.fixture(params=[
    'test_setup',
    'perfect_rssi',
    'poor_rssi',
    'worst_rssi',
    'invalid_rssi'
])
def fixture_propagation_test_type(request):
    return request.param


def test_propagation(sim_engine, fixture_propagation_test_type):
    PERFECT_PDR  = 1.0
    RSSI_VALUES = {
        'perfect_rssi': -10,
        'poor_rssi'   : -90,
        'worst_rssi'  : -97, # the worst in rssi_pdr_table of Connectivity.py
        'invalid_rssi': -1000
    }

    num_motes = 2
    num_frames = 1000
    sim_engine = sim_engine(
        diff_config = {
            'exec_numSlotframesPerRun': num_frames * (d.TSCH_MAXTXRETRIES + 1),
            'exec_numMotes'           : num_motes,
            'secjoin_enabled'         : False,
            'app_pkPeriod'            : 0,
            'rpl_of'                  : 'OFNone',
            'rpl_daoPeriod'           : 0,
            'rpl_extensions'          : [],
            'sf_class'                : 'SFNone',
            'tsch_slotframeLength'    : 2,
            'tsch_probBcast_ebProb'   : 0,
            'tsch_keep_alive_interval': 0,
            'tsch_tx_queue_size'      : num_frames,
            'conn_class'              : 'Linear', # this is intentional
            'phy_numChans'            : 1
        }
    )
    root = sim_engine.motes[0]
    mote = sim_engine.motes[1]
    # aliases
    dst = root
    src = mote

    class TestConnectivityMatrixK7(ConnectivityMatrixK7):
        def _additional_initialization(self):
            # set up the connectivity matrix
            channel = d.TSCH_HOPPING_SEQUENCE[0]
            self.set_pdr(src.id, dst.id, channel, PERFECT_PDR)
            self.set_rssi(
                src.id,
                dst.id,
                channel,
                RSSI_VALUES[fixture_propagation_test_type]
            )
            # dump the connectivity matrix
            print 'The Connectivity Matrix ("1.0" means PDR of 100%):'
            self.dump()

    # replace the 'Linear' conn_class with the test purpose
    # conn_class, TestConnectivityMatrixK7
    if fixture_propagation_test_type != 'test_setup':
        sim_engine.connectivity.matrix = TestConnectivityMatrixK7(
            sim_engine.connectivity
        )

    # add a dedicated TX cell in order to avoid backoff wait
    slot_offset = 1
    channel_offset = 0
    dst.tsch.addCell(
        slot_offset,
        channel_offset,
        src.get_mac_addr(),
        [d.CELLOPTION_RX]
    )
    src.tsch.addCell(
        slot_offset,
        channel_offset,
        dst.get_mac_addr(),
        [d.CELLOPTION_TX]
    )

    # get mote synchronized
    eb = root.tsch._create_EB()
    mote.tsch._action_receiveEB(eb)

    # put a fake EB to mote so that it can get synchronized
    # immediately
    eb_dummy = {
        'type':            d.PKT_TYPE_EB,
        'mac': {
            'srcMac':      '00-00-00-AA-AA-AA',     # dummy
            'dstMac':      d.BROADCAST_ADDRESS,     # broadcast
            'join_metric': 1000
        }
    }
    mote.tsch._action_receiveEB(eb_dummy)

    # disabled the trickle timer
    root.rpl.trickle_timer.stop()
    mote.rpl.trickle_timer.stop()

    # [test types]
    #
    # test_setup: verify if we can set up a test environment
    # correctly, where there is no background traffic
    #
    # perfect_rssi/poor_rssi: all the transmission should succeed
    # since the links between the two motes have a PDR of 100%
    # regardless of their RSSI values

    if fixture_propagation_test_type != 'test_setup':
        # put frames to the TX queue of the source; use the keep-alive
        # frame as the test packet
        for seqno in range(num_frames):
            packet = {
                'type': d.PKT_TYPE_KEEP_ALIVE,
                'mac': {
                    'srcMac': src.get_mac_addr(),
                    'dstMac': dst.get_mac_addr()
                },
                'app': { 'seq': seqno } # for debugging purpose
            }
            src.tsch.enqueue(packet)

    u.run_until_end(sim_engine)

    num_transmissions = len(u.read_log_file([SimLog.LOG_TSCH_TXDONE['type']]))

    if fixture_propagation_test_type == 'test_setup':
        # we shouldn't see any transmission
        assert num_transmissions == 0
    else:
        # num_transmissions contains the number of retransmissions if
        # any. in other words, num_transmissions should be equal to
        # num_frames when no frame is dropped
        assert num_transmissions == num_frames
