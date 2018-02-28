"""
\brief Tests for the conventional 6LoWPAN fragmentation

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.Mote as Mote


class TestNumFragmentsVsTxQueue:
    @pytest.mark.parametrize('test_input, expected', [
        (0, 1),
        (1, 1),
        (2, 2),
        (3, 3),
        (10, 10),
    ])
    def test_num_frag(self, sim, test_input, expected):
        m = sim(**{'numFragments': test_input,
                   'numMotes': 2,
                   'topology': 'linear',
                   'linearTopologyStaticScheduling': True}).motes[1]
        assert len(m.txQueue) == 0
        m._app_action_enqueueData()
        assert len(m.txQueue) == expected


class TestFragmentation:

    def test_app_frag_packet_2(self, sim):
        sim = sim(**{'numFragments': 2,
                     'numMotes': 2,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
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
        sim = sim(**{'numFragments': 3,
                     'numMotes': 3,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})

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
        sim = sim(**{'numFragments': 3,
                     'numMotes': 3,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
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
        sim = sim(**{'numFragments': 3,
                     'numMotes': 3,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
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

    def test_app_reass_packet_queue_len(self, sim):
        sim = sim(**{'numFragments': 2,
                     'numMotes': 2,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
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
            'sourceRoute': []
        }
        leaf._app_frag_packet(packet)
        frag0 = leaf.txQueue[0]
        frag0['payload'][3]['datagram_size'] = 3

        assert len(root.reassQueue) == 0
        assert root._app_reass_packet(leaf, frag0['payload']) is False
        assert len(root.reassQueue) == 0

    def test_app_reass_packet_node_queue_num(self, sim):
        sim = sim(**{'numFragments': 2,
                     'numMotes': 4,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf1 = sim.motes[2]
        leaf2 = sim.motes[3]
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
        frag0_1 = leaf1.txQueue[0]
        assert len(node.reassQueue) == 0
        assert node._app_reass_packet(leaf1, frag0_1['payload']) is False
        assert len(node.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2._app_frag_packet(packet)
        frag0_2 = leaf2.txQueue[0]
        assert len(node.reassQueue) == 1
        assert node._app_reass_packet(leaf2, frag0_2['payload']) is False
        assert len(node.reassQueue) == 1

    def test_app_reass_packet_root_queue_num(self, sim):
        sim = sim(**{'numFragments': 2,
                     'numMotes': 3,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
        root = sim.motes[0]
        leaf1 = sim.motes[1]
        leaf2 = sim.motes[2]
        packet = {
            'asn': 0,
            'type': Mote.APP_TYPE_DATA,
            'code': None,
            'payload': [1, 0, 1],
            'retriesLeft': Mote.TSCH_MAXTXRETRIES,
            'srcIp': leaf1,
            'dstIp': root,
            'smac': leaf1,
            'dmac': root,
            'sourceRoute': []
        }
        leaf1._app_frag_packet(packet)
        frag0_1 = leaf1.txQueue[0]
        assert len(root.reassQueue) == 0
        assert root._app_reass_packet(leaf1, frag0_1['payload']) is False
        assert len(root.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2._app_frag_packet(packet)
        frag0_2 = leaf2.txQueue[0]
        assert len(root.reassQueue) == 1
        assert root._app_reass_packet(leaf2, frag0_2['payload']) is False
        # root doesn't have reassQueue size limitation
        assert len(root.reassQueue) == 2


class TestPacketFowarding:
    def test_forwarder(self, sim):
        params = {'numFragments': 2, 'numMotes': 3,
                  'topology': 'linear', 'linearTopologyStaticScheduling': True}
        params.update({'pkPeriod': 0, 'pkPeriodVar': 0, 'downwardAcks': False})
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
        assert len(hop1.txQueue) == 0
        assert len(hop1.reassQueue) == 1

        hop1.waitingFor = Mote.DIR_RX
        assert hop1.radio_rxDone(Mote.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag1['payload']) == (True, False)
        assert len(hop1.txQueue) == 2
        assert len(hop1.reassQueue) == 0

    def test_e2e(self, sim):
        one_second = 1
        params = {'numFragments': 2, 'numMotes': 3,
                  'topology': 'linear', 'linearTopologyStaticScheduling': True}
        params.update({'pkPeriod': 0, 'pkPeriodVar': 0, 'downwardAcks': False})
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]

        hop2.app_schedule_transmition(one_second)
        assert len(sim.events) == 5
        assert sim.events[4][2] == hop2._app_action_sendSinglePacket

        cb = None
        asn0 = sim.asn
        while (len(sim.events) > 0) or (asn > (asn0 + (one_second / sim.settings.slotDuration))):
            (asn, priority, cb, tag) = sim.events.pop(0)
            sim.asn = asn

            if cb == hop2._app_action_sendSinglePacket:
                # not let the mote schedule another transmission
                hop2.app_schedule_transmition(0)
                break
            else:
                cb()

        # application packet is scheduled to be sent [next asn, next asn + 1 sec] with pkPeriod==1
        assert asn <= (asn0 + (one_second / sim.settings.slotDuration))

        # make sure there are two fragments added by _app_action_sendSinglePacket
        assert len(hop2.txQueue) == 0
        hop2._app_action_sendSinglePacket()
        assert len(hop2.txQueue) == 2

        asn0 = sim.asn

        # two fragments should be sent within two timeslots. In each of them,
        # hop2 has one TX cell to hop2
        while len(sim.events) > 0 and asn < (asn0 + (one_second * 2 / sim.settings.slotDuration)):
            (asn, priority, cb, tag) = sim.events.pop(0)
            if sim.asn != asn:
                # sync all the motes
                hop1.timeCorrectedSlot = sim.asn
                hop2.timeCorrectedSlot = sim.asn
                sim.asn = asn
            cb()
            if(len(hop1.txQueue) == 2):
                break

        # now hop1 has two fragments
        assert len(hop2.txQueue) == 0
        assert len(hop1.txQueue) == 2

        assert root.motestats['appReachesDagroot'] == 0
        asn0 = sim.asn
        # two fragments should be sent to the final destination within the next two timeslots.
        while (len(sim.events) > 0) and (asn < (asn0 + (one_second * 2 / sim.settings.slotDuration))):
            (asn, priority, cb, tag) = sim.events.pop(0)
            if sim.asn != asn:
                sim.asn = asn
            cb()
        assert root.motestats['appReachesDagroot'] == 1


class TestDatagramTag:
    def test_tag_on_its_fragments_1(self, sim):
        sim = sim(**{'numFragments': 2,
                     'numMotes': 2,
                     'topology': 'linear',
                     'linearTopologyStaticScheduling': True})
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
