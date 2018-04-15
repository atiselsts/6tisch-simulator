"""
\brief Tests for the Fragment Forwarding mechanism

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import copy
import types

import pytest

import SimEngine.Mote as Mote

pytestmark = pytest.mark.skip('fails randomly; skip this for now (issue #74)')

class TestNumFragmentsVsTxQueue:
    @pytest.mark.parametrize('test_input, expected', [
        (0, 1),
        (1, 1),
        (2, 2),
        (3, 3),
        (10, 10),
    ])
    def test_num_frag(self, sim, test_input, expected):
        m = sim(**{'enableFragmentForwarding': True,
                   'numFragments': test_input,
                   'numMotes': 2,
                   'top_type': 'linear',
                   'scheduling_function': 'SSF-symmetric'}).motes[1]
        assert len(m.txQueue) == 0
        m._app_action_enqueueData()
        assert len(m.txQueue) == expected


class TestFragmentForwarding:
    def test_app_is_frag_to_forward_frag_order(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 2,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'dmac': node,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)

        frag0 = leaf.txQueue[0]
        frag1 = leaf.txQueue[1]

        assert node._app_is_frag_to_forward(frag1) is False
        assert node._app_is_frag_to_forward(frag0) is True

    def test_app_is_frag_to_forward_vrbtable_len(self, sim):
        # no size limit for vrbtable
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 2,
                     'numMotes': 5,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf1 = sim.motes[2]
        leaf2 = sim.motes[3]
        leaf3 = sim.motes[4]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf1,
            'dstIp': root,
            'smac': leaf1,
            'dmac': node,
            'sourceRoute': []
        }
        leaf1._app_frag_packet(packet)

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2._app_frag_packet(packet)

        packet['srcIp'] = leaf3
        packet['smac'] = leaf3
        leaf3._app_frag_packet(packet)

        assert node._app_is_frag_to_forward(leaf1.txQueue[0]) is True
        assert node._app_is_frag_to_forward(leaf2.txQueue[0]) is True
        assert node._app_is_frag_to_forward(leaf3.txQueue[0]) is True
        leaf1.txQueue[0]['payload'][3]['datagram_tag'] += 1
        assert node._app_is_frag_to_forward(leaf1.txQueue[0]) is True

    def test_app_is_frag_to_forward_vrbtable_expiration(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 2,
                     'numMotes': 2,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        leaf = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'dmac': root,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)
        frag0 = leaf.txQueue[0]
        frag1 = leaf.txQueue[1]
        itag = frag0['payload'][3]['datagram_tag']

        sim.asn = 100
        root._app_is_frag_to_forward(frag0)
        assert root.vrbTable[leaf][itag]['ts'] == 100

        sim.asn += (60 / sim.settings.slotDuration)
        root._app_is_frag_to_forward(frag0) # duplicate
        assert itag in root.vrbTable[leaf]

        sim.asn += 1
        root._app_is_frag_to_forward(frag1)
        assert leaf not in root.vrbTable


class TestFragmentation:
    def test_app_frag_packet_2(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 2,
                     'numMotes': 2,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        assert len(node.txQueue) == 0
        node._app_frag_packet(packet)
        assert len(node.txQueue) == 2

        frag0 = node.txQueue[0]
        frag1 = node.txQueue[1]

        assert frag0['asn'] == packet['asn']
        assert frag0['type'] == Mote.APP_TYPE_FRAG
        assert frag0['code'] == packet['code']
        assert len(frag0['payload']) == 4
        assert frag0['payload'][0] == packet['payload'][0]
        assert frag0['payload'][1] == packet['payload'][1]
        assert frag0['payload'][2] == packet['payload'][2]
        assert frag0['payload'][3]['datagram_offset'] == 0
        assert frag0['payload'][3]['datagram_size'] == 2
        assert 'datagram_tag' in frag0['payload'][3]
        assert frag0['retriesLeft'] == packet['retriesLeft']
        assert frag0['srcIp'] == packet['srcIp']
        assert frag0['dstIp'] == packet['dstIp']
        assert frag0['sourceRoute'] == packet['sourceRoute']

        assert frag1['asn'] == packet['asn']
        assert frag1['type'] == Mote.APP_TYPE_FRAG
        assert frag1['code'] == packet['code']
        assert len(frag0['payload']) == 4
        assert frag1['payload'][0] == packet['payload'][0]
        assert frag1['payload'][1] == packet['payload'][1]
        assert frag1['payload'][2] == packet['payload'][2]
        assert frag1['payload'][3]['datagram_offset'] == 1
        assert frag1['payload'][3]['datagram_size'] == 2
        assert frag1['payload'][3]['datagram_tag'] == frag0['payload'][3]['datagram_tag']
        assert frag1['retriesLeft'] == packet['retriesLeft']
        assert frag1['srcIp'] == packet['srcIp']
        assert frag1['dstIp'] == packet['dstIp']
        assert frag1['sourceRoute'] == packet['sourceRoute']

    def test_app_frag_packet_3(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 3,
                     'numMotes': 3,
                     'top_type': 'linear'})
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        assert len(node.txQueue) == 0
        node._app_frag_packet(packet)
        assert len(node.txQueue) == 3

        frag0 = node.txQueue[0]
        frag1 = node.txQueue[1]
        frag2 = node.txQueue[2]

        assert frag0['asn'] == packet['asn']
        assert frag0['type'] == Mote.APP_TYPE_FRAG
        assert frag0['code'] == packet['code']
        assert len(frag0['payload']) == 4
        assert frag0['payload'][0] == packet['payload'][0]
        assert frag0['payload'][1] == packet['payload'][1]
        assert frag0['payload'][2] == packet['payload'][2]
        assert frag0['payload'][3]['datagram_offset'] == 0
        assert frag0['payload'][3]['datagram_size'] == 3
        assert 'datagram_tag' in frag0['payload'][3]
        assert frag0['retriesLeft'] == packet['retriesLeft']
        assert frag0['srcIp'] == packet['srcIp']
        assert frag0['dstIp'] == packet['dstIp']
        assert frag0['sourceRoute'] == packet['sourceRoute']

        assert frag1['asn'] == packet['asn']
        assert frag1['type'] == Mote.APP_TYPE_FRAG
        assert frag1['code'] == packet['code']
        assert len(frag0['payload']) == 4
        assert frag1['payload'][0] == packet['payload'][0]
        assert frag1['payload'][1] == packet['payload'][1]
        assert frag1['payload'][2] == packet['payload'][2]
        assert frag1['payload'][3]['datagram_offset'] == 1
        assert frag1['payload'][3]['datagram_size'] == 3
        assert frag1['payload'][3]['datagram_tag'] == frag0['payload'][3]['datagram_tag']
        assert frag1['retriesLeft'] == packet['retriesLeft']
        assert frag1['srcIp'] == packet['srcIp']
        assert frag1['dstIp'] == packet['dstIp']
        assert frag1['sourceRoute'] == packet['sourceRoute']

        assert frag2['asn'] == packet['asn']
        assert frag2['type'] == Mote.APP_TYPE_FRAG
        assert frag2['code'] == packet['code']
        assert len(frag0['payload']) == 4
        assert frag2['payload'][0] == packet['payload'][0]
        assert frag2['payload'][1] == packet['payload'][1]
        assert frag2['payload'][2] == packet['payload'][2]
        assert frag2['payload'][3]['datagram_offset'] == 2
        assert frag2['payload'][3]['datagram_size'] == 3
        assert frag2['payload'][3]['datagram_tag'] == frag0['payload'][3]['datagram_tag']
        assert frag2['retriesLeft'] == packet['retriesLeft']
        assert frag2['srcIp'] == packet['srcIp']
        assert frag2['dstIp'] == packet['dstIp']
        assert frag2['sourceRoute'] == packet['sourceRoute']


class TestReassembly:
    def test_app_reass_packet_in_order(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 3,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        node._app_frag_packet(packet)
        frag0 = node.txQueue[0]
        frag1 = node.txQueue[1]
        frag2 = node.txQueue[2]

        size = frag0['payload'][3]['datagram_size']
        tag = frag0['payload'][3]['datagram_tag']

        assert node not in root.reassQueue

        assert root._app_reass_packet(node, frag0['payload']) is False
        assert len(root.reassQueue[node]) == 1
        assert tag in root.reassQueue[node]
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [0]}

        assert root._app_reass_packet(node, frag1['payload']) is False
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [0, 1]}

        # duplicate fragment should be ignored
        assert root._app_reass_packet(node, frag1['payload']) is False
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [0, 1]}

        assert root._app_reass_packet(node, frag2['payload']) is True
        assert node not in root.reassQueue

    def test_app_reass_packet_out_of_order(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 3,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'scheduling_function': 'SSF-symmetric'})
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        node._app_frag_packet(packet)
        frag0 = node.txQueue[0]
        frag1 = node.txQueue[1]
        frag2 = node.txQueue[2]

        tag = frag0['payload'][3]['datagram_tag']

        assert node not in root.reassQueue

        assert root._app_reass_packet(node, frag2['payload']) is False
        assert len(root.reassQueue[node]) == 1
        assert tag in root.reassQueue[node]
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [2]}

        assert root._app_reass_packet(node, frag0['payload']) is False
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [2, 0]}

        # duplicate fragment should be ignored
        assert root._app_reass_packet(node, frag0['payload']) is False
        assert root.reassQueue[node][tag] == {'ts': 0, 'fragments': [2, 0]}

        assert root._app_reass_packet(node, frag1['payload']) is True
        assert node not in root.reassQueue


class TestPacketFowarding:
    def test_forwarder(self, sim):
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 3,
                  'top_type': 'linear',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2._app_frag_packet(packet)
        frag0 = hop2.txQueue[0]
        frag1 = hop2.txQueue[1]

        assert len(hop1.txQueue) == 0
        assert len(hop1.reassQueue) == 0

        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag0['payload']) == (True, False)
        assert len(hop1.txQueue) == 1
        assert len(hop1.reassQueue) == 0

        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag1['payload']) == (True, False)
        assert len(hop1.txQueue) == 2
        assert len(hop1.reassQueue) == 0

    def test_e2e(self, sim):
        one_second = 1
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 3,
                  'top_type': 'linear',
                  'scheduling_function': 'SSF-symmetric',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]

        hop2.pkPeriod = one_second
        hop2._app_schedule_sendSinglePacket(firstPacket=True)
        assert len(sim.events) == 5
        assert sim.events[4][2] == hop2._app_action_sendSinglePacket

        cb = None
        asn0 = sim.asn
        while len(sim.events) > 0 or asn > (asn0 + (one_second / sim.settings.slotDuration)):
            (asn, priority, cb, tag, kwargs) = sim.events.pop(0)
            sim.asn = asn

            if cb == hop2._app_action_sendSinglePacket:
                # not let the mote schedule another transmission
                hop2.pkPeriod = 0
                hop2._app_schedule_sendSinglePacket(firstPacket=True)
                break
            else:
                cb(**kwargs)

        # application packet is scheduled to be sent [next asn, next asn + 1 sec] with pkPeriod==1
        assert asn <= (asn0 + (one_second / sim.settings.slotDuration))

        # make sure there are two fragments added by _app_action_sendSinglePacket
        assert len(hop2.txQueue) == 0
        hop2._app_action_sendSinglePacket()
        assert len(hop2.txQueue) == 2

        asn0 = sim.asn
        assert root.motestats['appReachesDagroot'] == 0
        # two fragments should reach to the root within two timeslots.
        while len(sim.events) > 0 and asn < (asn0 + (one_second * 2 / sim.settings.slotDuration)):
            (asn, priority, cb, tag, kwargs) = sim.events.pop(0)
            if sim.asn != asn:
                sim.asn = asn
            cb(**kwargs)
            if(len(hop1.txQueue) == 2):
                break

        # now hop1 has two fragments
        assert len(hop2.txQueue) == 0
        assert len(hop1.txQueue) == 0
        assert root.motestats['appReachesDagroot'] == 1

    def test_drop_fragment(self, sim):
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 3,
                  'top_type': 'linear',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False
                  }
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2._app_frag_packet(packet)
        frag0 = hop2.txQueue[0]
        frag1 = hop2.txQueue[1]

        #frag1 should be dropped at hop-1 if a relevant VRBtable entry is not available
        assert len(hop1.txQueue) == 0
        assert len(hop1.reassQueue) == 0
        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag1['payload']) == (True, False)
        assert len(hop1.txQueue) == 0
        assert len(hop1.reassQueue) == 0

        # duplicate frag0 should be dropped at hop-1
        assert len(hop1.txQueue) == 0
        assert len(hop1.reassQueue) == 0
        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag0['payload']) == (True, False)
        assert len(hop1.txQueue) == 1
        assert len(hop1.reassQueue) == 0
        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag0['payload']) == (True, False)
        assert len(hop1.txQueue) == 1
        assert len(hop1.reassQueue) == 0


    def test_vrb_table_size_limit_1(self, sim):
        params = {'enableFragmentForwarding': True,
                  'maxVRBEntryNum': 10,
                  'numFragments': 2,
                  'numMotes': 2,
                  'top_type': 'linear',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        frag = {
            'dstIp': root,
            'payload': [1, 0, 1, {}],
        }
        frag['payload'][3]['datagram_size'] = params['numFragments']
        frag['payload'][3]['datagram_offset'] = 0
        for i in range(0, 10):
            frag['smac'] = i
            frag['payload'][3]['datagram_tag'] = i
            assert hop1._app_is_frag_to_forward(frag) is True
        frag['smac'] += 1
        frag['payload'][3]['datagram_tag'] += 1
        assert hop1._app_is_frag_to_forward(frag) is False

    def test_vrb_table_size_limit_2(self, sim):
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 2,
                  'top_type': 'linear',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        frag = {
            'dstIp': root,
            'payload': [1, 0, 1, {}],
        }
        frag['payload'][3]['datagram_size'] = params['numFragments']
        frag['payload'][3]['datagram_offset'] = 0
        for i in range(0, Mote.FRAGMENT_FORWARDING_DEFAULT_MAX_VRB_ENTRY_NUM):
            frag['smac'] = i
            frag['payload'][3]['datagram_tag'] = i
            assert hop1._app_is_frag_to_forward(frag) is True
        frag['smac'] += 1
        frag['payload'][3]['datagram_tag'] += 1
        assert hop1._app_is_frag_to_forward(frag) is False

class TestDatagramTag:
    def test_tag_on_its_fragments_1(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 2,
                     'numMotes': 2,
                     'top_type': 'linear'})
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        assert len(node.txQueue) == 0

        tag_init = node.next_datagram_tag

        # enqueue two packets
        node._app_frag_packet(packet)
        node._app_frag_packet(packet)

        tag0 = node.txQueue[0]['payload'][3]['datagram_tag']
        tag1 = node.txQueue[2]['payload'][3]['datagram_tag']

        node.next_datagram_tag = 65535
        node._app_frag_packet(packet)
        node._app_frag_packet(packet)

        tag2 = node.txQueue[4]['payload'][3]['datagram_tag']
        tag3 = node.txQueue[6]['payload'][3]['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0

    def test_tag_on_its_fragments_2(self, sim):
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 3,
                  'top_type': 'linear',
                  'scheduling_function': 'SSF-symmetric',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2._app_frag_packet(packet)
        hop2._app_frag_packet(packet)
        hop2._app_frag_packet(packet)
        hop2._app_frag_packet(packet)
        frag0_0 = hop2.txQueue[0]
        frag1_0 = hop2.txQueue[2]
        frag2_0 = hop2.txQueue[4]
        frag3_0 = hop2.txQueue[6]

        tag_init = hop1.next_datagram_tag

        hop1.waitingFor = Mote.DIR_RX
        hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag0_0['payload'])
        hop1.waitingFor = Mote.DIR_RX
        hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag1_0['payload'])

        hop1.next_datagram_tag = 65535
        hop1.waitingFor = Mote.DIR_RX
        hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag2_0['payload'])
        hop1.waitingFor = Mote.DIR_RX
        hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag3_0['payload'])

        tag0 = hop1.txQueue[0]['payload'][3]['datagram_tag']
        tag1 = hop1.txQueue[1]['payload'][3]['datagram_tag']
        tag2 = hop1.txQueue[2]['payload'][3]['datagram_tag']
        tag3 = hop1.txQueue[3]['payload'][3]['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0

    def test_tag_on_its_fragments_3(self, sim):
        params = {'enableFragmentForwarding': True,
                  'numFragments': 2,
                  'numMotes': 3,
                  'top_type': 'linear',
                  'scheduling_function': 'SSF-symmetric',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]
        packet1 = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': hop1,
            'dstIp': root,
            'sourceRoute': []
        }
        packet2 = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2._app_frag_packet(packet2)
        hop2._app_frag_packet(packet2)
        frag0_0 = hop2.txQueue[0]
        frag1_0 = hop2.txQueue[2]

        tag_init = hop1.next_datagram_tag

        hop1._app_frag_packet(packet1)
        tag0 = hop1.txQueue[0]['payload'][3]['datagram_tag']

        hop1.waitingFor = Mote.DIR_RX
        hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag0_0['payload'])
        tag1 = hop1.txQueue[2]['payload'][3]['datagram_tag']

        hop1._app_frag_packet(packet1)
        tag2 = hop1.txQueue[3]['payload'][3]['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == (tag1 + 1) % 65536

class TestOptimization:
    def test_remove_vrb_table_entry_by_expiration(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 4,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'optFragmentForwarding': []})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)
        frag0 = leaf.txQueue[0]
        frag1 = leaf.txQueue[1]
        frag2 = leaf.txQueue[2]
        frag3 = leaf.txQueue[3]


        assert len(node.vrbTable) == 0

        assert node._app_is_frag_to_forward(frag0) is True
        assert node._app_is_frag_to_forward(frag3) is True
        sim.asn += (60 / sim.settings.slotDuration)
        assert node._app_is_frag_to_forward(frag1) is True
        sim.asn += 1
        # VRB Table entry expires
        assert node._app_is_frag_to_forward(frag2) is False

    def test_remove_vrb_table_entry_on_last_frag(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 3,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'optFragmentForwarding': ['kill_entry_by_last']})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)
        frag0 = leaf.txQueue[0]
        frag1 = leaf.txQueue[1]
        frag2 = leaf.txQueue[2]

        assert len(node.vrbTable) == 0

        assert node._app_is_frag_to_forward(frag0) is True
        assert node._app_is_frag_to_forward(frag2) is True
        # the VRB entry is removed by frag2 (last)
        assert node._app_is_frag_to_forward(frag1) is False

    def test_remove_vrb_table_entry_on_missing_frag(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 4,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'optFragmentForwarding': ['kill_entry_by_missing']})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)
        frag0 = leaf.txQueue[0]
        frag1 = leaf.txQueue[1]
        frag2 = leaf.txQueue[2]
        frag3 = leaf.txQueue[3]

        assert len(node.vrbTable) == 0

        assert node._app_is_frag_to_forward(frag0) is True
        # frag2 afterb frag0 indicates frag1 is missing
        assert node._app_is_frag_to_forward(frag2) is False
        assert node._app_is_frag_to_forward(frag1) is False
        assert node._app_is_frag_to_forward(frag3) is False

    def test_remove_vrb_table_entry_on_last_and_missing(self, sim):
        sim = sim(**{'enableFragmentForwarding': True,
                     'numFragments': 4,
                     'numMotes': 3,
                     'top_type': 'linear',
                     'optFragmentForwarding': ['kill_entry_by_last', 'kill_entry_by_missing']})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf = sim.motes[2]
        packet1 = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        packet2 = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet1)
        frag1_0 = leaf.txQueue[0]
        frag1_1 = leaf.txQueue[1]
        frag1_2 = leaf.txQueue[2]
        frag1_3_1 = leaf.txQueue[3]
        frag1_3_2 = copy.copy(frag1_3_1)
        frag1_3_2['payload'] = copy.deepcopy(frag1_3_1['payload'])
        leaf._app_frag_packet(packet2)
        frag2_0 = leaf.txQueue[0]
        frag2_1 = leaf.txQueue[1]
        frag2_2 = leaf.txQueue[2]
        frag2_3 = leaf.txQueue[3]

        node.original_radio_drop_packet = node._radio_drop_packet
        test_is_called = {'result': False}

        def test(self, pkt, reason):
            test_is_called['result'] = True
            assert reason == 'droppedFragNoVRBEntry'

        node._radio_drop_packet = types.MethodType(test, node)

        assert len(node.vrbTable) == 0

        assert node._app_is_frag_to_forward(frag1_0) is True
        assert node._app_is_frag_to_forward(frag1_1) is True
        assert node._app_is_frag_to_forward(frag1_2) is True
        assert node._app_is_frag_to_forward(frag1_3_1) is True
        # the VRB entry is removed by frag1_3_1 (last)
        frag1_3_2['smac'] = leaf
        assert node._app_is_frag_to_forward(frag1_3_2) is False
        assert test_is_called['result'] is True
        node._radio_drop_packet = node.original_radio_drop_packet

        assert node._app_is_frag_to_forward(frag2_0) is True
        # frag2 afterb frag0 indicates frag1 is missing
        assert node._app_is_frag_to_forward(frag2_2) is False
        assert node._app_is_frag_to_forward(frag2_1) is False
        assert node._app_is_frag_to_forward(frag2_3) is False
