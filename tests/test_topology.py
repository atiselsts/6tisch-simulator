"""
\brief Tests for TopologyCreator Factory

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""


import SimEngine.Topology as Topology
import SimEngine.Mote.Mote as Mote
import SimEngine.Mote.MoteDefines as d

def test_create_random_topology_1(sim):
    sim()
    assert isinstance(Topology.Topology([]), Topology.RandomTopology)

def test_create_random_topology_2(sim):
    sim(**{'top_type': 'random'})
    assert isinstance(Topology.Topology([]), Topology.RandomTopology)

def test_create_linear_topology(sim):
    sim(**{'top_type': 'linear'})
    assert isinstance(Topology.Topology([]), Topology.LinearTopology)

def test_create_trace_topology(sim):
    sim(**{'top_type': 'trace', 'prop_type': 'trace',
           'prop_trace': 'traces/grenoble.k7.gz'})
    assert isinstance(Topology.Topology([]), Topology.TraceTopology)

def test_linear_topology_with_3_motes(sim):
    sim = sim(**{'exec_numMotes': 3, 'top_type': 'linear'})
    motes = sim.motes

    assert len(motes) == 3
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[0].y == 0
    assert motes[2].x == 0.06 and motes[0].y == 0
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[1].PDR == {motes[0]: 1.0, motes[2]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0}
    assert motes[1].id in motes[0].RSSI
    assert motes[2].id in motes[0].RSSI
    assert motes[0].id in motes[1].RSSI
    assert motes[2].id in motes[1].RSSI
    assert motes[0].id in motes[2].RSSI
    assert motes[1].id in motes[2].RSSI

def test_linear_topology_4_motes(sim):
    sim = sim(**{'exec_numMotes': 4, 'top_type': 'linear'})
    motes = sim.motes

    assert len(motes) == 4
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[0].y == 0
    assert motes[2].x == 0.06 and motes[0].y == 0
    assert motes[3].x == 0.09 and motes[0].y == 0
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0, motes[3]: 1.0}
    assert motes[3].PDR == {motes[2]: 1.0}
    assert motes[1].id in motes[0].RSSI
    assert motes[2].id in motes[0].RSSI
    assert motes[3].id in motes[0].RSSI
    assert motes[0].id in motes[1].RSSI
    assert motes[2].id in motes[1].RSSI
    assert motes[3].id in motes[1].RSSI
    assert motes[0].id in motes[2].RSSI
    assert motes[1].id in motes[2].RSSI
    assert motes[3].id in motes[2].RSSI
    assert motes[0].id in motes[3].RSSI
    assert motes[1].id in motes[3].RSSI
    assert motes[2].id in motes[3].RSSI

def test_linear_rpl_tree_builder(sim):
    sim = sim(**{'exec_numMotes': 4, 'top_type': 'linear'})
    motes = sim.motes

    assert motes[0].dagRoot is True
    assert motes[0].rpl.getPreferredParent() is None
    assert motes[0].rpl.daoParents[(1,)] == [[0]]
    assert motes[0].rpl.daoParents[(2,)] == [[1]]
    assert motes[0].rpl.daoParents[(3,)] == [[2]]
    assert motes[0].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE
    assert motes[0].rpl.getDagRank() == 1

    assert motes[1].dagRoot is False
    assert motes[1].rpl.getPreferredParent() == motes[0]
    assert motes[1].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 8
    assert motes[1].rpl.getDagRank() == 8

    assert motes[2].dagRoot is False
    assert motes[2].rpl.getPreferredParent() == motes[1]
    assert motes[2].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 15
    assert motes[2].rpl.getDagRank() == 15

    assert motes[3].dagRoot is False
    assert motes[3].rpl.getPreferredParent() == motes[2]
    assert motes[3].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 22
    assert motes[3].rpl.getDagRank() == 22

def test_two_branch_topology_with_6_motes(sim):
    sim = sim(**{'exec_numMotes': 6, 'top_type': 'twoBranch'})
    motes = sim.motes

    assert len(motes) == 6
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[1].y == 0
    assert motes[2].x == 0.06 and motes[2].y == -0.03
    assert motes[3].x == 0.09 and motes[3].y == -0.03
    assert motes[4].x == 0.06 and motes[4].y == 0.03
    assert motes[5].x == 0.09 and motes[5].y == 0.03
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[1].PDR == {motes[0]: 1.0, motes[2]: 1.0, motes[4]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0, motes[3]: 1.0}
    assert motes[3].PDR == {motes[2]: 1.0}
    assert motes[4].PDR == {motes[1]: 1.0, motes[5]: 1.0}
    assert motes[5].PDR == {motes[4]: 1.0}
    assert motes[1].id in motes[0].RSSI
    assert motes[2].id in motes[0].RSSI
    assert motes[3].id in motes[0].RSSI
    assert motes[4].id in motes[0].RSSI
    assert motes[5].id in motes[0].RSSI
    assert motes[0].id in motes[1].RSSI
    assert motes[2].id in motes[1].RSSI
    assert motes[3].id in motes[1].RSSI
    assert motes[4].id in motes[1].RSSI
    assert motes[5].id in motes[1].RSSI
    assert motes[0].id in motes[2].RSSI
    assert motes[1].id in motes[2].RSSI
    assert motes[3].id in motes[2].RSSI
    assert motes[4].id in motes[2].RSSI
    assert motes[5].id in motes[2].RSSI
    assert motes[0].id in motes[3].RSSI
    assert motes[1].id in motes[3].RSSI
    assert motes[2].id in motes[3].RSSI
    assert motes[4].id in motes[3].RSSI
    assert motes[5].id in motes[3].RSSI
    assert motes[0].id in motes[4].RSSI
    assert motes[1].id in motes[4].RSSI
    assert motes[2].id in motes[4].RSSI
    assert motes[3].id in motes[4].RSSI
    assert motes[5].id in motes[4].RSSI
    assert motes[0].id in motes[5].RSSI
    assert motes[1].id in motes[5].RSSI
    assert motes[2].id in motes[5].RSSI
    assert motes[3].id in motes[5].RSSI
    assert motes[4].id in motes[5].RSSI


def test_two_branch_topology_with_9_motes(sim):
    sim = sim(**{'exec_numMotes': 9, 'top_type': 'twoBranch'})
    motes = sim.motes

    assert len(motes) == 9
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[1].y == 0
    assert motes[2].x == 0.06 and motes[2].y == -0.03
    assert motes[3].x == 0.09 and motes[3].y == -0.03
    assert motes[4].x == 0.12 and motes[4].y == -0.03
    assert motes[5].x == 0.15 and motes[5].y == -0.03
    assert motes[6].x == 0.06 and motes[6].y == 0.03
    assert motes[7].x == 0.09 and motes[7].y == 0.03
    assert motes[8].x == 0.12 and motes[8].y == 0.03
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[1].PDR == {motes[0]: 1.0, motes[2]: 1.0, motes[6]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0, motes[3]: 1.0}
    assert motes[3].PDR == {motes[2]: 1.0, motes[4]: 1.0}
    assert motes[4].PDR == {motes[3]: 1.0, motes[5]: 1.0}
    assert motes[5].PDR == {motes[4]: 1.0}
    assert motes[6].PDR == {motes[1]: 1.0, motes[7]: 1.0}
    assert motes[7].PDR == {motes[6]: 1.0, motes[8]: 1.0}
    assert motes[8].PDR == {motes[7]: 1.0}


def test_two_branch_rpl_tree_builder(sim):
    sim = sim(**{'exec_numMotes': 6, 'top_type': 'twoBranch'})
    motes = sim.motes

    assert motes[0].dagRoot is True
    assert motes[0].rpl.getPreferredParent() is None
    assert motes[0].rpl.daoParents[(1,)] == [[0]]
    assert motes[0].rpl.daoParents[(2,)] == [[1]]
    assert motes[0].rpl.daoParents[(3,)] == [[2]]
    assert motes[0].rpl.daoParents[(4,)] == [[1]]
    assert motes[0].rpl.daoParents[(5,)] == [[4]]
    assert motes[0].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE
    assert motes[0].rpl.getDagRank() == 1

    assert motes[1].dagRoot is False
    assert motes[1].rpl.getPreferredParent() == motes[0]
    assert motes[1].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 8
    assert motes[1].rpl.getDagRank() == 8

    assert motes[2].dagRoot is False
    assert motes[2].rpl.getPreferredParent() == motes[1]
    assert motes[2].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 15
    assert motes[2].rpl.getDagRank() == 15

    assert motes[3].dagRoot is False
    assert motes[3].rpl.getPreferredParent() == motes[2]
    assert motes[3].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 22
    assert motes[3].rpl.getDagRank() == 22

    assert motes[4].dagRoot is False
    assert motes[4].rpl.getPreferredParent() == motes[1]
    assert motes[4].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 15
    assert motes[4].rpl.getDagRank() == 15

    assert motes[5].dagRoot is False
    assert motes[5].rpl.getPreferredParent() == motes[4]
    assert motes[5].rpl.getRank() == d.RPL_MIN_HOP_RANK_INCREASE * 22
    assert motes[5].rpl.getDagRank() == 22
