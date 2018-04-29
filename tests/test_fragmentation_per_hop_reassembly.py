"""
\brief Tests for the conventional 6LoWPAN fragmentation

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.Mote.MoteDefines as d
import SimEngine.Mote.Mote as Mote
import SimEngine

pytestmark = pytest.mark.skip('all tests needs to be updated')

class TestNumFragmentsVsTxQueue:

    @pytest.mark.parametrize('test_recv, expected', [
        (45, 1),
        (90, 1),
        (135, 2),
        (270, 3),
        (900, 10),
    ])

    def test_num_frag(self, sim, test_recv, expected):
        m = sim(
            **{
                'fragmentation': 'PerHopReassembly',
                'exec_numMotes': 2,
                'sf_type'      : 'SSFSymmetric',
                'app_pkLength' : test_recv
            }
        ).motes[1]
        assert len(m.tsch.getTxQueue()) == 0
        m.app._action_mote_enqueueDataForDAGroot()
        assert len(m.tsch.getTxQueue()) == expected

class TestFragmentation:

    def test_app_frag_packet_2(self, sim):
        sim = sim(
            **{
                'fragmentation': 'PerHopReassembly',
                'app_pkLength' : 180,
                'exec_numMotes': 2,
                'sf_type'      : 'SSFSymmetric',
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.sixlowpan.send(packet)
        assert len(node.tsch.getTxQueue()) == 2

        fragTheory = {
            'asn':                packet['asn'],
            'type':               d.APP_TYPE_FRAG,
            'code':               packet['code'],
            'payload': {
                'asn_at_source':  packet['payload']['asn_at_source'],
                'hops':           packet['payload']['hops'],
                'datagram_size':  180,
                'datagram_offset':0,
                'datagram_tag':   node.tsch.getTxQueue()[0]['payload']['datagram_tag'],
                'length':         90,
                'original_type':  d.APP_TYPE_DATA,
            },
            'retriesLeft':        packet['retriesLeft'],
            'srcIp':              packet['srcIp'],
            'dstIp':              packet['dstIp'],
            'sourceRoute':        packet['sourceRoute'],
            'nextHop':            node.tsch.getTxQueue()[0]['nextHop'],
        }

        fragTheory['payload']['datagram_offset'] = 0
        assert node.tsch.getTxQueue()[0] == fragTheory
        fragTheory['payload']['datagram_offset'] = 90
        assert node.tsch.getTxQueue()[1] == fragTheory

    def test_app_frag_packet_3(self, sim):
        sim = sim(
            **{
                'fragmentation'    : 'PerHopReassembly',
                'app_pkLength'     : 270,
                'exec_numMotes'    : 3,
                'sf_type'          : 'SSFSymmetric',
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.sixlowpan.send(packet)
        assert len(node.tsch.getTxQueue()) == 3

        fragTheory = {
            'asn':                packet['asn'],
            'type':               d.APP_TYPE_FRAG,
            'code':               packet['code'],
            'payload': {
                'asn_at_source':  packet['payload']['asn_at_source'],
                'hops':           packet['payload']['hops'],
                'datagram_size':  270,
                'datagram_offset':0,
                'datagram_tag':   node.tsch.getTxQueue()[0]['payload']['datagram_tag'],
                'length':         90,
                'original_type':  d.APP_TYPE_DATA,
            },
            'retriesLeft':        packet['retriesLeft'],
            'srcIp':              packet['srcIp'],
            'dstIp':              packet['dstIp'],
            'sourceRoute':        packet['sourceRoute'],
            'nextHop':            node.tsch.getTxQueue()[0]['nextHop'],
        }

        fragTheory['payload']['datagram_offset'] = 0
        assert node.tsch.getTxQueue()[0] == fragTheory
        fragTheory['payload']['datagram_offset'] = 90
        assert node.tsch.getTxQueue()[1] == fragTheory
        fragTheory['payload']['datagram_offset'] = 180
        assert node.tsch.getTxQueue()[2] == fragTheory

class TestReassembly:

    def test_app_reass_packet_in_order(self, sim):
        sim = sim(
            **{
                'fragmentation'                  : 'PerHopReassembly',
                'app_pkLength'                   : 270,
                'exec_numMotes'                  : 3,
                'sf_type'                        : 'SSFSymmetric',
                'app_e2eAck'                     : False,
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.sixlowpan.send(packet)
        assert len(node.tsch.getTxQueue()) == 3

        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        size = frag0['payload']['datagram_size']
        tag  = frag0['payload']['datagram_tag']

        assert node not in root.sixlowpan.reassembly_buffers

        root.sixlowpan.recv(node, frag0)
        len(root.sixlowpan.reassembly_buffers[node]) == 1
        assert tag in root.sixlowpan.reassembly_buffers[node]
        assert root.sixlowpan.reassembly_buffers[node][tag] == {'expiration': 6000,
                                                               'fragments': [
                                                                   {
                                                                       'datagram_offset': 0,
                                                                       'fragment_length': 90
                                                                   }]}


        root.sixlowpan.recv(node, frag1)
        assert root.sixlowpan.reassembly_buffers[node][tag] == {'expiration': 6000,
                                                               'fragments': [
                                                                   {
                                                                       'datagram_offset': 0,
                                                                       'fragment_length': 90
                                                                   },
                                                                   {
                                                                       'datagram_offset': 90,
                                                                       'fragment_length': 90
                                                                   }]}

        # duplicate fragment should be ignored
        root.sixlowpan.recv(node, frag1)
        assert len(root.sixlowpan.reassembly_buffers[node][tag]) == 2

        root.sixlowpan.recv(node, frag2)
        assert node not in root.sixlowpan.reassembly_buffers

    def test_app_reass_packet_out_of_order(self, sim):
        sim = sim(
            **{
                'fragmentation'                  : 'PerHopReassembly',
                'fragmentation_ff_options'       : [],
                'app_pkLength'                   : 270,
                'exec_numMotes'                  : 3,
                'sf_type'                        : 'SSFSymmetric',
                'app_e2eAck'                     : False,
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              node,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0
        node.sixlowpan.send(packet)
        assert len(node.tsch.getTxQueue()) == 3

        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        size = frag0['payload']['datagram_size']
        tag  = frag0['payload']['datagram_tag']

        assert node not in root.sixlowpan.reassembly_buffers

        root.sixlowpan.recv(node, frag2)
        assert len(root.sixlowpan.reassembly_buffers[node]) == 1
        assert tag in root.sixlowpan.reassembly_buffers[node]
        assert root.sixlowpan.reassembly_buffers[node][tag] == {'expiration': 6000,
                                                               'fragments': [
                                                                   {
                                                                       'datagram_offset': 180,
                                                                       'fragment_length': 90
                                                                   }]}

        root.sixlowpan.recv(node, frag0)
        assert root.sixlowpan.reassembly_buffers[node][tag] == {'expiration': 6000,
                                                               'fragments': [
                                                                   {
                                                                       'datagram_offset': 180,
                                                                       'fragment_length': 90
                                                                   },
                                                                   {
                                                                       'datagram_offset': 0,
                                                                       'fragment_length': 90
                                                                   }]}

        # duplicate fragment should be ignored
        root.sixlowpan.recv(node, frag0)
        assert len(root.sixlowpan.reassembly_buffers[node][tag]) == 2

        root.sixlowpan.recv(node, frag1)
        assert node not in root.sixlowpan.reassembly_buffers

    def test_app_reass_packet_node_queue_num_1(self, sim):
        sim = sim(
            **{
                'fragmentation'                   : 'PerHopReassembly',
                'fragmentation_ff_options'        : [],
                'sixlowpan_reassembly_buffers_num': 1,
                'app_pkLength'                    : 180,
                'exec_numMotes'                   : 4,
                'sf_type'                         : 'SSFSymmetric',
                'app_e2eAck'                      : False,
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf1,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        leaf1.sixlowpan.send(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(node.sixlowpan.reassembly_buffers) == 0
        node.sixlowpan.recv(leaf1, frag0_1)
        assert len(node.sixlowpan.reassembly_buffers) == 1

        packet['srcIp'] = leaf2
        packet['smac']  = leaf2
        leaf2.sixlowpan.send(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(node.sixlowpan.reassembly_buffers) == 1
        node.sixlowpan.recv(leaf2, frag0_2)
        assert len(node.sixlowpan.reassembly_buffers) == 1
        assert leaf2 not in node.sixlowpan.reassembly_buffers

    def test_app_reass_packet_node_queue_num_2(self, sim):
        sim = sim(
            **{
                'fragmentation'                   : 'PerHopReassembly',
                'fragmentation_ff_options'        : [],
                'sixlowpan_reassembly_buffers_num': 2,
                'app_pkLength'                    : 180,
                'exec_numMotes'                   : 4,
                'sf_type'                         : 'SSFSymmetric',
                'app_e2eAck'                      : False,
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp':              leaf1,
            'dstIp':              root,
            'sourceRoute':        [],
        }
        leaf1.sixlowpan.send(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(node.sixlowpan.reassembly_buffers) == 0
        node.sixlowpan.recv(leaf1, frag0_1)
        assert len(node.sixlowpan.reassembly_buffers) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2.sixlowpan.send(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(node.sixlowpan.reassembly_buffers) == 1
        node.sixlowpan.recv(leaf2, frag0_2)
        assert len(node.sixlowpan.reassembly_buffers) == 2

    def test_app_reass_packet_root_queue_num(self, sim):
        sim = sim(
            **{
                'fragmentation'                   : 'PerHopReassembly',
                'fragmentation_ff_options'        : [],
                'sixlowpan_reassembly_buffers_num': 1,
                'app_pkLength'                    : 180,
                'exec_numMotes'                   : 3,
                'sf_type'                         : 'SSFSymmetric',
                'app_e2eAck'                      : False,
            }
        )
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': leaf1,
            'dstIp': root,
            'smac': leaf1,
            'dmac': root,
            'sourceRoute':        [],
        }

        leaf1.sixlowpan.send(packet)
        frag0_1 = leaf1.tsch.getTxQueue()[0]
        assert len(root.sixlowpan.reassembly_buffers) == 0
        root.sixlowpan.recv(leaf1, frag0_1)
        assert len(root.sixlowpan.reassembly_buffers) == 1

        packet['srcIp'] = leaf2
        packet['smac'] = leaf2
        leaf2.sixlowpan.send(packet)
        frag0_2 = leaf2.tsch.getTxQueue()[0]
        assert len(root.sixlowpan.reassembly_buffers) == 1
        root.sixlowpan.recv(leaf2, frag0_2)
        # root doesn't have sixlowpan.reassembly_buffers size limitation
        assert len(root.sixlowpan.reassembly_buffers) == 2

class TestPacketFowarding:
    def test_forwarder(self, sim):
        params = {'fragmentation'                   : 'PerHopReassembly',
                  'fragmentation_ff_options'        : [],
                  'sixlowpan_reassembly_buffers_num': 1,
                  'app_pkLength'                    : 180,
                  'exec_numMotes'                   : 3,
                  'sf_type'                         : 'SSFSymmetric',
                  'app_e2eAck'                      : False}

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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute':        [],
        }

        hop2.sixlowpan.send(packet)
        frag0 = hop2.tsch.getTxQueue()[0]
        frag1 = hop2.tsch.getTxQueue()[1]

        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

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
        assert len(hop1.sixlowpan.reassembly_buffers) == 1

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
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

    def test_e2e(self, sim):
        one_second = 1
        params = {'fragmentation'                   : 'PerHopReassembly',
                  'fragmentation_ff_options'        : [],
                  'sixlowpan_reassembly_buffers_num': 1,
                  'app_pkLength'                    : 180,
                  'exec_numMotes'                   : 3,
                  'sf_type'                         : 'SSFSymmetric',
                  'app_e2eAck'                      : False}
        sim = sim(**params)
        root = sim.motes[0]
        hop1 = sim.motes[1]
        hop2 = sim.motes[2]

        hop2.app.pkPeriod = one_second
        hop2.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)
        assert len(sim.events) == 11
        assert sim.events[4][2] == hop2.app._action_mote_sendSinglePacketToDAGroot

        cb = None
        asn0 = sim.asn
        while len(sim.events) > 0:
            (asn, intraSlotOrder, cb, tag, kwarg) = sim.events.pop(0)
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
            (asn, intraSlotOrder, cb, tag, kwarg) = sim.events.pop(0)
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

        assert SimEngine.SimLog.LOG_APP_RX['type'] not in root.motestats
        asn0 = sim.asn
        # two fragments should be sent to the final destination within the next two timeslots.
        while (len(sim.events) > 0) and (asn < (asn0 + (one_second * 2 / sim.settings.tsch_slotDuration))):
            (asn, intraSlotOrder, cb, tag, kwarg) = sim.events.pop(0)
            if sim.asn != asn:
                sim.asn = asn
            cb(**kwarg)
        assert root.motestats[SimEngine.SimLog.LOG_APP_RX['type']] == 1


class TestDatagramTag:

    def test_tag_on_its_fragments_1(self, sim):
        sim = sim(
            **{
                'fragmentation': 'PerHopReassembly',
                'app_pkLength' : 180,
                'exec_numMotes': 2,
                'sf_type'      : 'SSFSymmetric',
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
                'length':         sim.settings.app_pkLength,
            },
            'retriesLeft':        d.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute':        [],
        }
        assert len(node.tsch.getTxQueue()) == 0

        tag_init = node.sixlowpan.next_datagram_tag

        # enqueue two packets
        node.sixlowpan.send(packet)
        node.sixlowpan.send(packet)

        tag0 = node.tsch.getTxQueue()[0]['payload']['datagram_tag']
        tag1 = node.tsch.getTxQueue()[2]['payload']['datagram_tag']

        node.sixlowpan.next_datagram_tag = 65535
        node.sixlowpan.send(packet)
        node.sixlowpan.send(packet)

        tag2 = node.tsch.getTxQueue()[4]['payload']['datagram_tag']
        tag3 = node.tsch.getTxQueue()[6]['payload']['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0
