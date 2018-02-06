"""
\brief Tests for Mote

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""


def test_app_schedule_transmit(sim):

    sim = sim(**{'numMotes': 2, 'pkPeriod': 0, 'topology': 'linear'})
    node = sim.motes[1]
    # active TX cell event for node, active RX cell event for root, and
    # propagation event
    assert len(sim.events) == 3
    node.app_schedule_transmition(100)
    assert len(sim.events) == 4
    print sim.events[3][2]
    assert sim.events[3][2] == node._app_action_sendSinglePacket
