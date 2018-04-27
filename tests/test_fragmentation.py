"""
Tests for 6LoWPAN fragmentation
"""

import pytest

import test_utils as u


FRAGMENTATION = [
    'PerHopReassembly',
    'FragmentForwarding'
]
@pytest.fixture(params=FRAGMENTATION)
def fragmentation(request):
    return request.param


FRAGMENTATION_FF_DISCARD_VRB_ENTRY_POLICY = [
    [],
    ['last_fragment'],
    ['missing_fragment'],
    ['last_fragment', 'missing_fragment']
]
@pytest.fixture(params=FRAGMENTATION_FF_DISCARD_VRB_ENTRY_POLICY)
def fragmentation_ff_discard_vrb_entry_policy(request):
    return request.param


class TestPacketDelivery:
    """ Behavioral Testing for Fragmentation
    - objective   : test if packets are delivered to the root (destination)
    - precondition: form a 3-node linear topology
    - action      : send packets from each motes except for the root
    - expectation : the root receives the packets
    """

    APP_PKLENGTH = [45, 90, 135, 180]
    @pytest.fixture(params=APP_PKLENGTH)
    def app_pkLength(self, request):
        return request.param

    def test_packet_delivery(
            self,
            sim_engine,
            app_pkLength,
            fragmentation,
            fragmentation_ff_discard_vrb_entry_policy
        ):

        sim_engine = sim_engine(
            {
                'exec_numMotes'                            : 3,
                'exec_numSlotframesPerRun'                 : 10,
                'sf_type'                                  : 'SSFSymmetric',
                'conn_type'                                : 'linear',
                'app_pkPeriod'                             : 5,
                'app_pkPeriodVar'                          : 0,
                'tsch_probBcast_ebProb'                    : 0,
                'tsch_probBcast_dioProb'                   : 0,
                'sixlowpan_reassembly_buffers_num'         : 2,
                'app_pkLength'                             : app_pkLength,
                'fragmentation'                            : fragmentation,
                'fragmentation_ff_discard_vrb_entry_policy': fragmentation_ff_discard_vrb_entry_policy
            },
            force_initial_routing_and_scheduling_state = True
        )

        # run the simulation for 1000 timeslots (10 seconds)
        u.run_until_asn(sim_engine, 1000)

        # the root should receive packet from both of the two motes during 10 seconds.
        # - Packets are generated at every 5 seconds
        # - The first packet is generated within the first 5 seconds
        # - the minimum e2e latency of one fragment from the leaf is about 2 sec
        # - a packet is divided into two fragments at most in this test
        # - two fragments from the leaf need at least 4 sec to reach the root
        senders = []
        for log in u.read_log_file(filter=['app_reaches_dagroot']):
            if log['mote_id'] not in senders:
                senders.append(log['mote_id'])
            if len(senders) == 2:
                # root should receive packets from both of the two motes
                # if it reaches here, it means success
                return

        assert False
