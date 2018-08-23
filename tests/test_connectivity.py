"""
Tests for SimEngine.Connectivity
"""
import itertools
import os
import random
import shutil
import types

from scipy.stats import t
from numpy import average, std
from math import sqrt

import test_utils as u
from SimEngine import SimLog


#============================ helpers =========================================

def destroy_all_singletons(engine):
    engine.destroy()
    engine.connectivity.destroy()
    engine.settings.destroy()
    SimLog.SimLog().destroy()

def print_connectivity_matrix(matrix):
    output         = []
    output        += ['\n']

    # header
    line           = []
    for source in matrix:
        line      += [str(source)]
    line           = '\t|'.join(line)
    output        += ['\t|'+line]

    # body
    for source in matrix:
        line       = []
        line      += [str(source)]
        for dest in matrix:
            if source == dest:
                line += ['N/A']
            else:
                line  += [str(matrix[source][dest][0]['pdr'])]
        line       = '\t|'.join(line)
        output    += [line]

    output         = '\n'.join(output)
    print output

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
    matrix = engine.connectivity.connectivity_matrix

    print_connectivity_matrix(matrix)

    assert motes[0].dagRoot is True

    for c in range(0, num_motes):
        for p in range(0, num_motes):
            if (c == p+1) or (c+1 == p):
                for channelOffset in range(engine.settings.phy_numChans):
                    assert matrix[c][p][channelOffset]['pdr']  ==  1.00
                    assert matrix[c][p][channelOffset]['rssi'] ==   -10
            else:
                for channelOffset in range(engine.settings.phy_numChans):
                    assert matrix[c][p][channelOffset]['pdr']  ==  0.00
                    assert matrix[c][p][channelOffset]['rssi'] == -1000

def test_k7_matrix(sim_engine):
    """ verify the connectivity matrix for the 'K7' class is as expected """

    num_motes = 50
    here = os.path.dirname(__file__)
    engine = sim_engine(
        diff_config = {
            'exec_numMotes': num_motes,
            'conn_class':    'K7',
            'conn_trace':    os.path.join(here, '..', 'traces', 'grenoble.k7.gz'),
            'phy_numChans':  15,
        }
    )
    motes  = engine.motes
    matrix = engine.connectivity.connectivity_matrix

    print_connectivity_matrix(matrix)

    assert motes[0].dagRoot is True

    for src in range(0, num_motes):
        for dst in range(0, num_motes):
            if src == dst:
                continue
            for channelOffset in range(engine.settings.phy_numChans):
                assert 'pdr' in matrix[src][dst][channelOffset]
                assert 'rssi' in matrix[src][dst][channelOffset]
                assert isinstance(matrix[src][dst][channelOffset]['pdr'], (int, long, float))
                assert isinstance(matrix[src][dst][channelOffset]['rssi'], (int, long, float))
                assert 0 <= matrix[src][dst][channelOffset]['pdr'] <= 1
                assert -1000 <= matrix[src][dst][channelOffset]['rssi'] <= 0

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
        sim_engine = sim_engine(
            diff_config = {
                'conn_class'                    : 'Random',
                'exec_numMotes'                 : 2,
                'conn_random_init_min_neighbors': 1,
                'phy_numChans'                  : 2,
            }
        )

        # PDR and RSSI should not change over time
        for src, dst in zip(sim_engine.motes[:-1], sim_engine.motes[1:]):
            for channel in range(sim_engine.settings.phy_numChans):
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
            for channel in range(sim_engine.settings.phy_numChans):
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
            coordinates[(sf_class, run_id)] = engine.connectivity.coordinates
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
