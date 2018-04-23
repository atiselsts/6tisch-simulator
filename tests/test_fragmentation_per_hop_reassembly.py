"""
\brief Tests for the conventional 6LoWPAN fragmentation

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.Mote.MoteDefines as d
import SimEngine.Mote.Mote as Mote
import SimEngine

class TestNumFragmentsVsTxQueue:

    @pytest.mark.parametrize('test_input, expected', [
        (0, 1),
        (1, 1),
        (2, 2),
        (3, 3),
        (10, 10),
    ])

    def test_num_frag(self, sim, test_input, expected):
        m = sim(
            **{
                'exec_numMotes':       2,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
                'frag_numFragments':   test_input,
            }
        ).motes[1]
        assert len(m.tsch.getTxQueue()) == 0
        m.app._action_mote_enqueueDataForDAGroot()
        assert len(m.tsch.getTxQueue()) == expected

class TestFragmentation:

    def test_app_frag_packet_2(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   2,
                'exec_numMotes':       2,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.app.fragment_and_enqueue_packet(packet)
        assert len(node.tsch.getTxQueue()) == 2

        fragTheory = {
            'asn':                packet['asn'],
            'type':               d.APP_TYPE_FRAG,
            'code':               packet['code'],
            'payload': {
                'asn_at_source':  packet['payload']['asn_at_source'],
                'hops':           packet['payload']['hops'],
                'datagram_size':  2,
                'datagram_offset':0,
                'datagram_tag':   node.tsch.getTxQueue()[0]['payload']['datagram_tag'],
            },
            'retriesLeft':        packet['retriesLeft'],
            'srcIp':              packet['srcIp'],
            'dstIp':              packet['dstIp'],
            'sourceRoute':        packet['sourceRoute'],
            'nextHop':            node.tsch.getTxQueue()[0]['nextHop'],
        }

        fragTheory['payload']['datagram_offset'] = 0
        assert node.tsch.getTxQueue()[0] == fragTheory
        fragTheory['payload']['datagram_offset'] = 1
        assert node.tsch.getTxQueue()[1] == fragTheory

    def test_app_frag_packet_3(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   3,
                'exec_numMotes':       3,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )
        root = sim.motes[0]
        node = sim.motes[1]
        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.app.fragment_and_enqueue_packet(packet)
        assert len(node.tsch.getTxQueue()) == 3

        fragTheory = {
            'asn':                packet['asn'],
            'type':               d.APP_TYPE_FRAG,
            'code':               packet['code'],
            'payload': {
                'asn_at_source':  packet['payload']['asn_at_source'],
                'hops':           packet['payload']['hops'],
                'datagram_size':  3,
                'datagram_offset':0,
                'datagram_tag':   node.tsch.getTxQueue()[0]['payload']['datagram_tag'],
            },
            'retriesLeft':        packet['retriesLeft'],
            'srcIp':              packet['srcIp'],
            'dstIp':              packet['dstIp'],
            'sourceRoute':        packet['sourceRoute'],
            'nextHop':            node.tsch.getTxQueue()[0]['nextHop'],
        }

        fragTheory['payload']['datagram_offset'] = 0
        assert node.tsch.getTxQueue()[0] == fragTheory
        fragTheory['payload']['datagram_offset'] = 1
        assert node.tsch.getTxQueue()[1] == fragTheory
        fragTheory['payload']['datagram_offset'] = 2
        assert node.tsch.getTxQueue()[2] == fragTheory

class TestReassembly:

    def test_app_reass_packet_in_order(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   3,
                'exec_numMotes':       3,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )

        root = sim.motes[0]
        node = sim.motes[1]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.app.fragment_and_enqueue_packet(packet)
        assert len(node.tsch.getTxQueue()) == 3

        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        size = frag0['payload']['datagram_size']
        tag  = frag0['payload']['datagram_tag']

        assert node not in root.app.reassQueue

        assert root.app.frag_reassemble_packet(node, frag0['payload']) is False
        assert len(root.app.reassQueue[node]) == 1
        assert tag in root.app.reassQueue[node]
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [0]}

        assert root.app.frag_reassemble_packet(node, frag1['payload']) is False
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [0, 1]}

        # duplicate fragment should be ignored
        assert root.app.frag_reassemble_packet(node, frag1['payload']) is False
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [0, 1]}

        assert root.app.frag_reassemble_packet(node, frag2['payload']) is True
        assert node not in root.app.reassQueue

    def test_app_reass_packet_out_of_order(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   3,
                'exec_numMotes':       3,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )

        root = sim.motes[0]
        node = sim.motes[1]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.app.fragment_and_enqueue_packet(packet)
        assert len(node.tsch.getTxQueue()) == 3

        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        size = frag0['payload']['datagram_size']
        tag  = frag0['payload']['datagram_tag']

        assert node not in root.app.reassQueue

        assert root.app.frag_reassemble_packet(node, frag2['payload']) is False
        assert len(root.app.reassQueue[node]) == 1
        assert tag in root.app.reassQueue[node]
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [2]}

        assert root.app.frag_reassemble_packet(node, frag0['payload']) is False
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [2, 0]}

        # duplicate fragment should be ignored
        assert root.app.frag_reassemble_packet(node, frag0['payload']) is False
        assert root.app.reassQueue[node][tag] == {'ts': 0, 'fragments': [2, 0]}

        assert root.app.frag_reassemble_packet(node, frag1['payload']) is True
        assert node not in root.app.reassQueue

    def test_app_reass_packet_queue_len(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   2,
                'exec_numMotes':       2,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )

        root = sim.motes[0]
        leaf = sim.motes[1]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf,
            'dstIp':              root,
            'sourceRoute':        [],
        }

        leaf.app.fragment_and_enqueue_packet(packet)

        frag0 = leaf.tsch.getTxQueue()[0]
        frag0['payload']['datagram_size'] = 3

        assert len(root.app.reassQueue) == 0
        assert root.app.frag_reassemble_packet(leaf, frag0['payload']) is False
        assert len(root.app.reassQueue) == 0

    def test_app_reass_packet_node_queue_num_1(self, sim):
        sim = sim(
            **{
                'frag_numFragments':   2,
                'exec_numMotes':       4,
                'top_type':            'linear',
                'sf_type':             'SSF-symmetric',
            }
        )

        root  = sim.motes[0]
        node  = sim.motes[1]
        leaf1 = sim.motes[2]
        leaf2 = sim.motes[3]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf1,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        leaf1.app.fragment_and_enqueue_packet(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 0
        assert node.app.frag_reassemble_packet(leaf1, frag0_1['payload']) is False
        assert len(node.app.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac']  = leaf2
        leaf2.app.fragment_and_enqueue_packet(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 1
        assert node.app.frag_reassemble_packet(leaf2, frag0_2['payload']) is False
        assert len(node.app.reassQueue) == 1

    def test_app_reass_packet_node_queue_num_2(self, sim):
        sim = sim(
            **{
                'frag_numFragments': 2,
                'exec_numMotes': 4,
                'top_type': 'linear',
                'sf_type': 'SSF-symmetric',
                'frag_ph_numReassBuffs': 1,
            }
        )

        root = sim.motes[0]
        node = sim.motes[1]
        leaf1 = sim.motes[2]
        leaf2 = sim.motes[3]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf1,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        leaf1.app.fragment_and_enqueue_packet(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 0
        assert node.app.frag_reassemble_packet(leaf1, frag0_1['payload']) is False
        assert len(node.app.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2.app.fragment_and_enqueue_packet(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 1
        assert node.app.frag_reassemble_packet(leaf2, frag0_2['payload']) is False
        reass_queue_num = 0
        for i in node.app.reassQueue:
            reass_queue_num += len(node.app.reassQueue[i])
        assert reass_queue_num == 1


    def test_app_reass_packet_node_queue_num_3(self, sim):
        sim = sim(**{'frag_numFragments': 2,
                     'exec_numMotes': 4,
                     'top_type': 'linear',
                     'sf_type': 'SSF-symmetric',
                     'frag_ph_numReassBuffs': 2})
        root = sim.motes[0]
        node = sim.motes[1]
        leaf1 = sim.motes[2]
        leaf2 = sim.motes[3]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf1,
            'dstIp':              root,
            'smac': leaf1,
            'dmac': node,
            'sourceRoute':        [],
        }

        leaf1.app.fragment_and_enqueue_packet(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 0
        assert node.app.frag_reassemble_packet(leaf1, frag0_1['payload']) is False
        assert len(node.app.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2.app.fragment_and_enqueue_packet(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(node.app.reassQueue) == 1
        assert node.app.frag_reassemble_packet(leaf2, frag0_2['payload']) is False
        reass_queue_num = 0
        for i in node.app.reassQueue:
            reass_queue_num += len(node.app.reassQueue[i])
        assert reass_queue_num == 2

    def test_app_reass_packet_root_queue_num(self, sim):
        sim = sim(**{'frag_numFragments': 2,
                     'exec_numMotes': 3,
                     'top_type': 'linear',
                     'sf_type': 'SSF-symmetric'})
        root = sim.motes[0]
        leaf1 = sim.motes[1]
        leaf2 = sim.motes[2]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': leaf1,
            'dstIp': root,
            'smac': leaf1,
            'dmac': root,
            'sourceRoute':        [],
        }

        leaf1.app.fragment_and_enqueue_packet(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(root.app.reassQueue) == 0
        assert root.app.frag_reassemble_packet(leaf1, frag0_1['payload']) is False
        assert len(root.app.reassQueue) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2.app.fragment_and_enqueue_packet(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(root.app.reassQueue) == 1
        assert root.app.frag_reassemble_packet(leaf2, frag0_2['payload']) is False
        # root doesn't have app.reassQueue size limitation
        assert len(root.app.reassQueue) == 2

class TestPacketFowarding:
    def test_forwarder(self, sim):
        params = {'frag_numFragments': 2,
                  'exec_numMotes': 3,
                  'top_type': 'linear',
                  'sf_type': 'SSF-symmetric',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute':        [],
        }

        hop2.app.fragment_and_enqueue_packet(packet)
        frag0 = hop2.tsch.getTxQueue()[0]
        frag1 = hop2.tsch.getTxQueue()[1]

        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.app.reassQueue) == 0

        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(
            d.APP_TYPE_FRAG,
            None,
            hop2,
            [hop1],
            hop2,
            root,
            [],
            frag0['payload']
        ) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.app.reassQueue) == 1

        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(
            type        = d.APP_TYPE_FRAG,
            code        = None,
            smac        = hop2,
            dmac        = [hop1],
            srcIp       = hop2,
            dstIp       = root,
            srcRoute    = [],
            payload     = frag1['payload']
        ) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 2
        assert len(hop1.app.reassQueue) == 0

    def test_e2e(self, sim):
        one_second = 1
        params = {'frag_numFragments': 2,
                  'exec_numMotes': 3,
                  'top_type': 'linear',
                  'sf_type': 'SSF-cascading',
                  'app_pkPeriod': 0,
                  'app_pkPeriodVar': 0,
                  'app_e2eAck': False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]

        hop2.app.pkPeriod = one_second
        hop2.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)
        assert len(sim.events) == 5
        assert sim.events[4][2] == hop2.app._action_mote_sendSinglePacketToDAGroot

        cb = None
        asn0 = sim.asn
        while len(sim.events) > 0:
            (asn, priority, cb, tag, kwarg) = sim.events.pop(0)
            sim.asn = asn

            if cb == hop2.app._action_mote_sendSinglePacketToDAGroot:
                # not let the mote schedule another transmission
                hop2.app.pkPeriod = 0
                hop2.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)
                break
            else:
                cb(**kwarg)

            if asn > (asn0 + (one_second / sim.settings.tsch_slotDuration)):
                # timeout
                break;

        # application packet is scheduled to be sent [next asn, next asn + 1 sec] with app.pkPeriod==1
        assert asn <= (asn0 + (one_second / sim.settings.tsch_slotDuration))

        # make sure there are two fragments added by app._action_mote_sendSinglePacketToDAGroot
        assert len(hop2.tsch.getTxQueue()) == 0
        hop2.app._action_mote_sendSinglePacketToDAGroot()
        assert len(hop2.tsch.getTxQueue()) == 2

        asn0 = sim.asn

        # two fragments should be sent within two slotframes. In each of them,
        # hop2 has one TX cell to hop2
        while len(sim.events) > 0:
            (asn, priority, cb, tag, kwarg) = sim.events.pop(0)
            if sim.asn != asn:
                # sync all the motes
                hop1.tsch.asnLastSync = sim.asn
                hop2.tsch.asnLastSync = sim.asn
                sim.asn = asn
            cb(**kwarg)

            if len(hop1.tsch.getTxQueue()) == 2:
                break

            if asn > (asn0 + (2 * sim.settings.tsch_slotframeLength)):
                # timeout
                break

        # now hop1 has two fragments
        assert len(hop2.tsch.getTxQueue()) == 0
        assert len(hop1.tsch.getTxQueue()) == 2

        assert SimEngine.SimLog.LOG_APP_REACHES_DAGROOT['type'] not in root.motestats
        asn0 = sim.asn
        # two fragments should be sent to the final destination within the next two timeslots.
        while (len(sim.events) > 0) and (asn < (asn0 + (one_second * 2 / sim.settings.tsch_slotDuration))):
            (asn, priority, cb, tag, kwarg) = sim.events.pop(0)
            if sim.asn != asn:
                sim.asn = asn
            cb(**kwarg)
        assert root.motestats[SimEngine.SimLog.LOG_APP_REACHES_DAGROOT['type']] == 1


class TestDatagramTag:

    def test_tag_on_its_fragments_1(self, sim):
        sim = sim(**{'frag_numFragments': 2,
                     'exec_numMotes': 2,
                     'top_type': 'linear',
                     'sf_type': 'SSF-cascading'})
        root = sim.motes[0]
        node = sim.motes[1]

        packet = {
            'asn':                0,
            'type':               d.APP_TYPE_DATA,
            'code':               None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0

        tag_init = node.app.next_datagram_tag

        # enqueue two packets
        node.app.fragment_and_enqueue_packet(packet)
        node.app.fragment_and_enqueue_packet(packet)

        tag0 = node.tsch.getTxQueue()[0]['payload']['datagram_tag']
        tag1 = node.tsch.getTxQueue()[2]['payload']['datagram_tag']

        node.app.next_datagram_tag = 65535
        node.app.fragment_and_enqueue_packet(packet)
        node.app.fragment_and_enqueue_packet(packet)

        tag2 = node.tsch.getTxQueue()[4]['payload']['datagram_tag']
        tag3 = node.tsch.getTxQueue()[6]['payload']['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0
