"""
\brief Tests for TopologyCreator Factory

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""


import SimEngine.Topology as Topology


def test_create_random_topology_1(settings):
    settings()
    assert isinstance(Topology.Topology([]), Topology.RandomTopology)


def test_create_random_topology_2(settings):
    settings(**{'topology': 'random'})
    assert isinstance(Topology.Topology([]), Topology.RandomTopology)


def test_create_linear_topology(settings):
    settings(**{'topology': 'linear'})
    assert isinstance(Topology.Topology([]), Topology.LinearTopology)
