"""
Tests for SimEngine.Connectivity
"""
import os

import test_utils as u

#============================ helpers =========================================

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
                continue
            line  += [str(matrix[source][dest][0]['pdr'])]
        line       = '\t|'.join(line)
        output    += [line]

    output         = '\n'.join(output)
    #print output

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

        # PDR and RSSI should not be always the same over the slots
        for src, dst in zip(sim_engine.motes[:-1], sim_engine.motes[1:]):
            for channel in range(sim_engine.settings.phy_numChans):
                pdr  = []
                rssi = []

                for _ in range(100):
                    pdr.append(
                        sim_engine.connectivity.get_pdr(
                            source      = src.id,
                            destination = dst.id,
                            channel     = channel
                        )
                    )
                    rssi.append(
                        sim_engine.connectivity.get_rssi(
                            source      = src.id,
                            destination = dst.id,
                            channel     = channel
                        )
                    )
                    # proceed the simulator
                    u.run_until_asn(sim_engine, sim_engine.getAsn() + 1)

                # compare two consecutive PDRs and RSSIs; if we have even one
                # True in the comparison, i != j, something should be wrong
                # with PisterHackModel class
                assert sum([(i != j) for i, j in zip(pdr[:-1], pdr[1:])])   > 0
                assert sum([(i != j) for i, j in zip(rssi[:-1], rssi[1:])]) > 0

        # PDR and RSSI should be the same within the same slot
        for src, dst in zip(sim_engine.motes[:-1], sim_engine.motes[1:]):
            for channel in range(sim_engine.settings.phy_numChans):
                pdr  = []
                rssi = []

                for _ in range(100):
                    pdr.append(
                        sim_engine.connectivity.get_pdr(
                            source      = src.id,
                            destination = dst.id,
                            channel     = channel
                        )
                    )
                    rssi.append(
                        sim_engine.connectivity.get_rssi(
                            source      = src.id,
                            destination = dst.id,
                            channel     = channel
                        )
                    )

                # compare two consecutive PDRs and RSSIs; all the pairs should
                # be same (all comparison, i != j, should be False).
                assert sum([(i != j) for i, j in zip(pdr[:-1], pdr[1:])])   == 0
                assert sum([(i != j) for i, j in zip(rssi[:-1], rssi[1:])]) == 0
