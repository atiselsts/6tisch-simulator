"""
Tests for 6LoWPAN fragmentation
"""

import pytest

import test_utils as u

#pytestmark = pytest.mark.skip('work-in-progress; not ready')


class TestFragmentDelivery:
    """ Behavioral Testing for Fragmentation
    - objective   : check if a large packet is delivered to the destination
    - precondition: form a 3-node linear topology
    - action      : send packets from each motes except for the root
    - expectation : the root receives the packets
    """

    def test_large_packet(self, sim_engine):
        app_pkLength = 10
        sim_engine = sim_engine(
            {
                'exec_numMotes'           : 3,
                'sf_type'                 : 'SSFSymmetric',
                'app_pkPeriod'            : 1,
                'app_pkPeriodVar'         : 0,
                'app_pkLength'            : app_pkLength,
                'fragmentation'           : 'PerHopReassembly',
            },
            force_initial_routing_and_scheduling_state = True
        )

        # run the simulation for 1000 timeslots
        u.run_until_asn(sim_engine, 1000)

        # one packet from each mote, two packets in total, at least should
        # reach the root during 1000 timeslots
        # this will be checked by seeing logs
