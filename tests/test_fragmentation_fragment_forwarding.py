"""
\brief Tests for the Fragment Forwarding mechanism

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import copy
import types

import pytest

import SimEngine.Mote.Mote as Mote
import SimEngine.Mote.MoteDefines as d
import SimEngine

#pytestmark = pytest.mark.skip('all tests needs to be updated')

# number of fragments generated is correct
@pytest.mark.parametrize('num_bytes_in, exp_num_frags_out', [
    (45,  1),
    (90,  1),
    (135, 2),
    (270, 3),
    (900, 10),
])
def test_num_frags(sim_engine, num_bytes_in, exp_num_frags_out):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes': 2,
            'app_pkLength' : num_bytes_in,
            'fragmentation': 'FragmentForwarding',
        },
        force_initial_routing_and_scheduling_state = True,
    )
    
    # root <- hop1
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    
    # verify that the expected number of fragments are created
    assert len(hop1.tsch.getTxQueue()) == 0
    hop1.app._action_mote_enqueueDataForDAGroot()
    assert len(hop1.tsch.getTxQueue()) == exp_num_frags_out

# in-order fragments are forwarded
def test_ff_frag_out_of_order(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                             3,
            'conn_type':                                 'linear',
            'app_pkLength':                              180, # 2 frags per packet
            'fragmentation':                             'FragmentForwarding',
        },
        force_initial_routing_and_scheduling_state = True,
    )
    
    # root <- hop1 <- hop2
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    # send a long packet from hop2
    packet = {
        'asn':                0,
        'type':               d.APP_TYPE_DATA,
        'code':               None,
        'payload': {
            'asn_at_source':  0,
            'hops':           1,
            'length':         sim_engine.settings.app_pkLength,
        },
        'retriesLeft':        d.TSCH_MAXTXRETRIES,
        'smac':               hop2,
        'dmac':               hop1,
        'srcIp':              hop2,
        'dstIp':              root,
        'sourceRoute':        [],
    }
    hop2.sixlowpan.send(packet)

    frag0 = hop2.tsch.getTxQueue()[0]
    frag1 = hop2.tsch.getTxQueue()[1]
    
    # if frag0 is received, verify it is forwarded by hop1
    hop1.sixlowpan.recv(hop2, frag0)
    assert len(hop1.tsch.getTxQueue()) == 1
    assert hop1.tsch.getTxQueue()[0] == frag0
    
    # if frag1 is received, verify it is forwarded by hop1
    hop1.sixlowpan.recv(hop2, frag1)
    assert len(hop1.tsch.getTxQueue()) == 2
    assert hop1.tsch.getTxQueue()[0] == frag0
    assert hop1.tsch.getTxQueue()[1] == frag1

# out-of-order fragments are discarded
def test_ff_frag_out_of_order(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                             3,
            'conn_type':                                 'linear',
            'app_pkLength':                              180, # 2 frags per packet
            'fragmentation':                             'FragmentForwarding',
        },
        force_initial_routing_and_scheduling_state = True,
    )
    
    # root <- hop1 <- hop2
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    # send a long packet from hop2
    packet = {
        'asn':                0,
        'type':               d.APP_TYPE_DATA,
        'code':               None,
        'payload': {
            'asn_at_source':  0,
            'hops':           1,
            'length':         sim_engine.settings.app_pkLength,
        },
        'retriesLeft':        d.TSCH_MAXTXRETRIES,
        'smac':               hop2,
        'dmac':               hop1,
        'srcIp':              hop2,
        'dstIp':              root,
        'sourceRoute':        [],
    }
    hop2.sixlowpan.send(packet)

    frag0 = hop2.tsch.getTxQueue()[0]
    frag1 = hop2.tsch.getTxQueue()[1]
    
    # if frag1 is received first, verify it is discarded by hop1
    hop1.sixlowpan.recv(hop2, frag1)
    assert len(hop1.tsch.getTxQueue()) == 0
    
    # if frag0 is received, verify it is received and forwarded by hop1
    hop1.sixlowpan.recv(hop2, frag0)
    assert len(hop1.tsch.getTxQueue()) == 1
    assert hop1.tsch.getTxQueue()[0] == frag0

def test_app_frag_ff_forward_fragment_vrbtable_len(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
           'exec_numMotes'                            : 5,
           'app_pkLength'                             : 180, # 2 frags per packet
           'fragmentation'                            : 'FragmentForwarding',
           'sf_type'                                  : 'SSFSymmetric'
        },
        force_initial_routing_and_scheduling_state = True,
    )
    
    #              <- leaf1
    # root <- node <- leaf2
    #              <- leaf3
    root  = sim_engine.motes[0]
    node  = sim_engine.motes[1]
    leaf1 = sim_engine.motes[2]
    leaf2 = sim_engine.motes[3]
    leaf3 = sim_engine.motes[4]
    
    # send frame leaf1->node
    packet = {
        'asn':                0,
        'type':               d.APP_TYPE_DATA,
        'code':               None,
        'payload': {
            'asn_at_source':  0,
            'hops':           1,
            'length':         sim_engine.settings.app_pkLength,
        },
        'retriesLeft':        d.TSCH_MAXTXRETRIES,
        'smac':               leaf1,
        'dmac':               node,
        'srcIp':              leaf1,
        'dstIp':              root,
        'sourceRoute':        [],
    }
    leaf1.sixlowpan.send(packet)
    assert len(leaf1.tsch.getTxQueue()) == 2 # 2 frags
    
    # send frame leaf2->node
    packet['srcIp'] = leaf2
    packet['smac']  = leaf2
    leaf2.sixlowpan.send(packet)
    assert len(leaf2.tsch.getTxQueue()) == 2 # 2 frags
    
    # send frame leaf3->node
    packet['srcIp'] = leaf3
    packet['smac']  = leaf3
    leaf3.sixlowpan.send(packet)
    assert len(leaf3.tsch.getTxQueue()) == 2 # 2 frags
    
    # make sure node hasn't received anything yet
    assert len(node.tsch.getTxQueue()) == 0
    
    
    node.sixlowpan.recv(leaf1, leaf1.tsch.getTxQueue()[0])
    assert len(node.tsch.getTxQueue()) == 1
    
    node.sixlowpan.recv(leaf2, leaf2.tsch.getTxQueue()[0])
    assert len(node.tsch.getTxQueue()) == 2
    
    node.sixlowpan.recv(leaf3, leaf3.tsch.getTxQueue()[0])
    assert len(node.tsch.getTxQueue()) == 3
    
    leaf1.tsch.getTxQueue()[0]['payload']['datagram_tag'] += 1
    node.sixlowpan.recv(leaf1, leaf1.tsch.getTxQueue()[0])
    assert len(node.tsch.getTxQueue()) == 4


def test_app_frag_ff_forward_fragment_vrbtable_expiration(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
           
            'fragmentation'                            : 'FragmentForwarding',
            'fragmentation_ff_discard_vrb_entry_policy': [],
            'app_pkLength'                             : 180,
            'exec_numMotes'                            : 2,
            'sf_type'                                  : 'SSFSymmetric',
            'app_e2eAck'                               : False,
        }
    )
    root = sim_engine.motes[0]
    leaf = sim_engine.motes[1]

    packet = {
        'asn':                0,
        'type':               d.APP_TYPE_DATA,
        'code':               None,
        'payload': {
            'asn_at_source':  0,
            'hops':           1,
            'length':         sim_engine.settings.app_pkLength,
        },
        'retriesLeft':        d.TSCH_MAXTXRETRIES,
        'srcIp': leaf,
        'dstIp': root,
        'smac': leaf,
        'dmac': root,
        'sourceRoute':        [],
    }

    leaf.sixlowpan.send(packet)
    frag0 = leaf.tsch.getTxQueue()[0]
    frag1 = leaf.tsch.getTxQueue()[1]

    itag  = frag0['payload']['datagram_tag']

    sim_engine.asn = 100
    root.sixlowpan.recv(leaf, frag0)
    assert root.sixlowpan.fragmentation.vrb_table[leaf][itag]['expiration'] == 6100

    sim_engine.asn += int(60.0 / sim_engine.settings.tsch_slotDuration)
    root.sixlowpan.recv(leaf, frag0) # duplicate
    assert itag in root.sixlowpan.fragmentation.vrb_table[leaf]

    sim_engine.asn += 1
    root.sixlowpan.recv(leaf, frag1)

    assert leaf not in root.sixlowpan.fragmentation.vrb_table


def test_app_fragment_and_enqueue_packet_2(sim_engine):
    sim_engine = sim_engine(diff_config = {
           'fragmentation': 'FragmentForwarding',
                 'app_pkLength' : 180,
                 'exec_numMotes': 2,
                 'sf_type'      : 'SSFSymmetric'})
    root = sim_engine.motes[0]
    node = sim_engine.motes[1]
    packet = {
        'asn': 0,
        'type': d.APP_TYPE_DATA,
        'code': None,
        'payload': {
            'asn_at_source': 0,
            'hops'         : 1,
            'length'       : sim_engine.settings.app_pkLength,
            },
        'retriesLeft': d.TSCH_MAXTXRETRIES,
        'srcIp': node,
        'dstIp': root,
        'sourceRoute': []
    }
    assert len(node.tsch.getTxQueue()) == 0
    node.sixlowpan.send(packet)
    assert len(node.tsch.getTxQueue()) == 2

    frag0 = node.tsch.getTxQueue()[0]
    frag1 = node.tsch.getTxQueue()[1]

    assert frag0['asn'] == packet['asn']
    assert frag0['type'] == d.APP_TYPE_FRAG
    assert frag0['code'] == packet['code']
    assert frag0['payload']['length'] == 90
    assert frag0['payload']['asn_at_source'] == packet['payload']['asn_at_source']
    assert frag0['payload']['hops'] == packet['payload']['hops']
    assert frag0['payload']['datagram_offset'] == 0
    assert frag0['payload']['datagram_size'] == 180
    assert frag0['payload']['original_type'] == d.APP_TYPE_DATA
    assert 'datagram_tag' in frag0['payload']
    assert frag0['retriesLeft'] == packet['retriesLeft']
    assert frag0['srcIp'] == packet['srcIp']
    assert frag0['dstIp'] == packet['dstIp']
    assert frag0['sourceRoute'] == packet['sourceRoute']

    assert frag1['asn'] == packet['asn']
    assert frag1['type'] == d.APP_TYPE_FRAG
    assert frag1['code'] == packet['code']
    assert frag1['payload']['length'] == 90
    assert frag1['payload']['asn_at_source'] == packet['payload']['asn_at_source']
    assert frag1['payload']['hops'] == packet['payload']['hops']
    assert frag1['payload']['datagram_offset'] == 90
    assert frag1['payload']['datagram_size'] == 180
    assert frag1['payload']['datagram_tag'] == frag0['payload']['datagram_tag']
    assert frag0['payload']['original_type'] == d.APP_TYPE_DATA
    assert frag1['retriesLeft'] == packet['retriesLeft']
    assert frag1['srcIp'] == packet['srcIp']
    assert frag1['dstIp'] == packet['dstIp']
    assert frag1['sourceRoute'] == packet['sourceRoute']

def test_app_fragment_and_enqueue_packet_3(sim_engine):
    sim_engine = sim_engine(diff_config = {
           'fragmentation'           : 'FragmentForwarding',
                 'app_pkLength'            : 270,
                 'exec_numMotes'           : 3,
                 'conn_type'                : 'linear'})
    root = sim_engine.motes[0]
    node = sim_engine.motes[1]
    packet = {
        'asn': 0,
        'type': d.APP_TYPE_DATA,
        'code': None,
        'payload': {
            'asn_at_source': 0,
            'hops'         : 1,
            'length'       : sim_engine.settings.app_pkLength,
            },
        'retriesLeft': d.TSCH_MAXTXRETRIES,
        'srcIp': node,
        'dstIp': root,
        'sourceRoute': []
    }
    assert len(node.tsch.getTxQueue()) == 0
    node.sixlowpan.send(packet)
    assert len(node.tsch.getTxQueue()) == 3

    frag0 = node.tsch.getTxQueue()[0]
    frag1 = node.tsch.getTxQueue()[1]
    frag2 = node.tsch.getTxQueue()[2]

    assert frag0['asn'] == packet['asn']
    assert frag0['type'] == d.APP_TYPE_FRAG
    assert frag0['code'] == packet['code']
    assert frag0['payload']['length'] == 90
    assert frag0['payload']['asn_at_source'] == packet['payload']['asn_at_source']
    assert frag0['payload']['hops'] == packet['payload']['hops']
    assert frag0['payload']['datagram_offset'] == 0
    assert frag0['payload']['datagram_size'] == 270
    assert frag0['payload']['original_type'] == d.APP_TYPE_DATA
    assert 'datagram_tag' in frag0['payload']
    assert frag0['retriesLeft'] == packet['retriesLeft']
    assert frag0['srcIp'] == packet['srcIp']
    assert frag0['dstIp'] == packet['dstIp']
    assert frag0['sourceRoute'] == packet['sourceRoute']

    assert frag1['asn'] == packet['asn']
    assert frag1['type'] == d.APP_TYPE_FRAG
    assert frag1['code'] == packet['code']
    assert frag1['payload']['length'] == 90
    assert frag1['payload']['asn_at_source'] == packet['payload']['asn_at_source']
    assert frag1['payload']['hops'] == packet['payload']['hops']
    assert frag1['payload']['datagram_offset'] == 90
    assert frag1['payload']['datagram_size'] == 270
    assert frag1['payload']['original_type'] == d.APP_TYPE_DATA
    assert frag1['payload']['datagram_tag'] == frag0['payload']['datagram_tag']
    assert frag1['retriesLeft'] == packet['retriesLeft']
    assert frag1['srcIp'] == packet['srcIp']
    assert frag1['dstIp'] == packet['dstIp']
    assert frag1['sourceRoute'] == packet['sourceRoute']

    assert frag2['asn'] == packet['asn']
    assert frag2['type'] == d.APP_TYPE_FRAG
    assert frag2['code'] == packet['code']
    assert frag2['payload']['length'] == 90
    assert frag2['payload']['asn_at_source'] == packet['payload']['asn_at_source']
    assert frag2['payload']['hops'] == packet['payload']['hops']
    assert frag2['payload']['datagram_offset'] == 180
    assert frag2['payload']['datagram_size'] == 270
    assert frag2['payload']['original_type'] == d.APP_TYPE_DATA
    assert frag2['payload']['datagram_tag'] == frag0['payload']['datagram_tag']
    assert frag2['retriesLeft'] == packet['retriesLeft']
    assert frag2['srcIp'] == packet['srcIp']
    assert frag2['dstIp'] == packet['dstIp']
    assert frag2['sourceRoute'] == packet['sourceRoute']


class TestReassembly:
    def test_app_reass_packet_in_order(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_discard_vrb_entry_policy': [],
                     'app_pkLength'                             : 270,
                     'app_e2eAck'                               : False,
                     'exec_numMotes'                            : 3,
                     'sf_type'                                  : 'SSFSymmetric'})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        node.sixlowpan.send(packet)
        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        size = frag0['payload']['datagram_size']
        tag = frag0['payload']['datagram_tag']

        assert node not in root.sixlowpan.reassembly_buffers

        root.sixlowpan.recv(node, frag0)
        assert len(root.sixlowpan.reassembly_buffers[node]) == 1
        assert tag in root.sixlowpan.reassembly_buffers[node]
        assert root.sixlowpan.reassembly_buffers[node][tag] == {
            'expiration': 6000,
            'fragments' : [
                {
                    'datagram_offset': 0,
                    'fragment_length': 90
                }]}

        root.sixlowpan.recv(node, frag1)
        assert root.sixlowpan.reassembly_buffers[node][tag] == {
            'expiration': 6000,
            'fragments' : [
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


    def test_app_reass_packet_out_of_order(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_discard_vrb_entry_policy': [],
                     'app_pkLength'                             : 270,
                     'app_e2eAck'                               : False,
                     'exec_numMotes'                            : 3,
                     'sf_type'                                  : 'SSFSymmetric'})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        node.sixlowpan.send(packet)
        frag0 = node.tsch.getTxQueue()[0]
        frag1 = node.tsch.getTxQueue()[1]
        frag2 = node.tsch.getTxQueue()[2]

        tag = frag0['payload']['datagram_tag']

        assert node not in root.sixlowpan.reassembly_buffers

        root.sixlowpan.recv(node, frag0)
        assert len(root.sixlowpan.reassembly_buffers[node]) == 1
        assert tag in root.sixlowpan.reassembly_buffers[node]
        assert root.sixlowpan.reassembly_buffers[node][tag] == {
            'expiration': 6000,
            'fragments' : [
                {
                    'datagram_offset': 0,
                    'fragment_length': 90
                }]}

        root.sixlowpan.recv(node, frag2)
        assert root.sixlowpan.reassembly_buffers[node][tag] == {
            'expiration': 6000,
            'fragments' : [
                {
                    'datagram_offset': 0,
                    'fragment_length': 90
                },
                {
                    'datagram_offset': 180,
                    'fragment_length': 90
                }]}

        root.sixlowpan.recv(node, frag1)
        assert node not in root.sixlowpan.reassembly_buffers


class TestPacketFowarding:
    def test_forwarder(sim_engine):
        sim_engine = sim_engine(diff_config = {
               
            'fragmentation'                            : 'FragmentForwarding',
            'fragmentation_ff_discard_vrb_entry_policy': [],
            'fragmentation_ff_vrb_table_size'          : 50,
            'app_pkLength'                             : 180,
            'exec_numMotes'                            : 3,
            'conn_type'                                 : 'linear',
            'app_pkPeriod'                             : 0,
            'app_pkPeriodVar'                          : 0,
            'app_e2eAck'                               : False,
        })

        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]

        hop2.sixlowpan.send({
            'asn':           0,
            'type':          d.APP_TYPE_DATA,
            'code':          None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft':   d.TSCH_MAXTXRETRIES,
            'srcIp':         hop2,
            'dstIp':         root,
            'sourceRoute':   [],
            })
        frag0 = hop2.tsch.getTxQueue()[0]
        frag1 = hop2.tsch.getTxQueue()[1]

        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

        hop1.tsch.waitingFor = d.DIR_RX
        (isACKed,isNACKed) = hop1.radio.rxDone(
            type        = d.APP_TYPE_FRAG,
            code        = None,
            smac        = hop2,
            dmac        = [hop1],
            srcIp       = hop2,
            dstIp       = root,
            srcRoute    = [],
            payload     = frag0['payload']
        )
        assert (isACKed,isNACKed) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 1
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag1['payload']) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 2
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

    def test_e2e(sim_engine):
        one_second = 1
        sim_engine = sim_engine(diff_config = {
               
            'fragmentation'                            : 'FragmentForwarding',
            'fragmentation_ff_discard_vrb_entry_policy': [],
            'fragmentation_ff_vrb_table_size'          : 50,
            'app_pkLength'                             : 180,
            'exec_numMotes'                            : 3,
            'conn_type'                                 : 'linear',
            'sf_type'                                  : 'SSFSymmetric',
            'app_pkPeriod'                             : 0,
            'app_pkPeriodVar'                          : 0,
            'app_e2eAck'                               : False,
        })

        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]

        # send a packet from hop2
        hop2.app.pkPeriod = one_second
        hop2.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)
        assert len(sim_engine.events) == 11
        assert sim_engine.events[4][2] == hop2.app._action_mote_sendSinglePacketToDAGroot

        # execute all events
        cb = None
        asn0 = sim_engine.asn
        while len(sim_engine.events) > 0 or asn > (asn0 + (one_second / sim_engine.settings.tsch_slotDuration)):
            (asn, intraSlotOrder, cb, tag) = sim_engine.events.pop(0)
            sim_engine.asn = asn

            if cb == hop2.app._action_mote_sendSinglePacketToDAGroot:
                # not let the mote schedule another transmission
                hop2.app.pkPeriod = 0
                hop2.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)
                break
            else:
                cb()

        # application packet is scheduled to be sent [next asn, next asn + 1 sec] with app.pkPeriod==1
        assert asn <= (asn0 + (one_second / sim_engine.settings.tsch_slotDuration))

        # make sure there are two fragments added by app._action_mote_sendSinglePacketToDAGroot
        assert len(hop2.tsch.getTxQueue()) == 0
        hop2.app._action_mote_sendSinglePacketToDAGroot()
        assert len(hop2.tsch.getTxQueue()) == 2

        asn0 = sim_engine.asn
        assert SimEngine.SimLog.LOG_APP_RX['type'] not in root.motestats
        # two fragments should reach to the root within two slotframes
        while len(sim_engine.events) > 0:
            (asn, intraSlotOrder, cb, tag) = sim_engine.events.pop(0)
            if sim_engine.asn != asn:
                sim_engine.asn = asn
            cb()
            if(len(hop1.tsch.getTxQueue()) == 2):
                break
            if asn > (asn0 + (2 * sim_engine.settings.tsch_slotframeLength)):
                # timeout
                break

        # now hop1 has two fragments
        assert len(hop2.tsch.getTxQueue()) == 0
        assert len(hop1.tsch.getTxQueue()) == 0
        print root.motestats
        assert root.motestats[SimEngine.SimLog.LOG_APP_RX['type']] == 1

    def test_drop_fragment(sim_engine):
        params = {'fragmentation'                            : 'FragmentForwarding',
                  'fragmentation_ff_discard_vrb_entry_policy': [],
                  'fragmentation_ff_vrb_table_size'          : 50,
                  'app_pkLength'                             : 180,
                  'exec_numMotes'                            : 3,
                  'conn_type'                                 : 'linear',
                  'app_pkPeriod'                             : 0,
                  'app_pkPeriodVar'                          : 0,
                  'app_e2eAck'                               : False,
        }
        sim_engine = sim_engine(**params)
        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2.sixlowpan.send(packet)
        frag0 = hop2.tsch.getTxQueue()[0]
        frag1 = hop2.tsch.getTxQueue()[1]
        dup_frag0 = copy.copy(frag0)
        dup_frag0['payload'] = copy.deepcopy(frag0['payload'])

        #frag1 should be dropped at hop-1 if a relevant VRBtable entry is not available
        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.sixlowpan.reassembly_buffers) == 0
        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag1['payload']) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.sixlowpan.reassembly_buffers) == 0

        # duplicate frag0 should be dropped at hop-1
        assert len(hop1.tsch.getTxQueue()) == 0
        assert len(hop1.sixlowpan.reassembly_buffers) == 0
        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], frag0['payload']) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 1
        assert len(hop1.sixlowpan.reassembly_buffers) == 0
        hop1.tsch.waitingFor = d.DIR_RX
        assert hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                                 hop2, [hop1], hop2, root, [], dup_frag0['payload']) == (True, False)
        assert len(hop1.tsch.getTxQueue()) == 1
        assert len(hop1.sixlowpan.reassembly_buffers) == 0


    @pytest.mark.parametrize("vrb_table_size",
                             [10, 50])
    def test_vrb_table_size_limit_1(sim_engine, vrb_table_size):
        params = {'fragmentation'                            : 'FragmentForwarding',
                  'fragmentation_ff_discard_vrb_entry_policy': [],
                  'fragmentation_ff_vrb_table_size'          : vrb_table_size,
                  'app_pkLength'                             : 180,
                  'exec_numMotes'                            : 3,
                  'conn_type'                                 : 'linear',
                  'app_pkPeriod'                             : 0,
                  'app_pkPeriodVar'                          : 0,
                  'app_e2eAck'                               : False}
        sim_engine = sim_engine(**params)
        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]
        frag0 = {
            'type'             : d.APP_TYPE_FRAG,
            'dstIp'            : root,
            'payload'          : {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                'original_type': d.APP_TYPE_DATA,
                },
        }
        frag0['payload']['datagram_size'] = sim_engine.settings.app_pkLength
        frag0['payload']['datagram_offset'] = 0
        assert hop2 not in hop1.sixlowpan.fragmentation.vrb_table
        for i in range(0, vrb_table_size):
            frag = copy.copy(frag0)
            frag['payload'] = copy.deepcopy(frag0['payload'])
            frag['smac'] = i
            frag['payload']['datagram_tag'] = i
            hop1.sixlowpan.recv(hop2, frag)
        assert len(hop1.sixlowpan.fragmentation.vrb_table[hop2]) == vrb_table_size
        frag0['smac'] = 100
        frag0['payload']['datagram_tag'] = 100
        hop1.sixlowpan.recv(hop2, frag0)
        assert len(hop1.sixlowpan.fragmentation.vrb_table[hop2]) == vrb_table_size


class TestDatagramTag:
    def test_tag_on_its_fragments_1(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                  : 'FragmentForwarding',
                     'fragmentation_ff_vrb_table_size': 50,
                     'app_pkLength'                   : 180,
                     'exec_numMotes'                  : 2,
                     'conn_type'                       : 'linear'})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
                'length':         sim_engine.settings.app_pkLength,
            },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': node,
            'dstIp': root,
            'sourceRoute': []
        }
        assert len(node.tsch.getTxQueue()) == 0

        tag_init = node.sixlowpan._get_next_datagram_tag()

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

        assert tag0 == tag_init + 1
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0

    def test_tag_on_its_fragments_2(sim_engine):
        params = {'fragmentation'                            : 'FragmentForwarding',
                  'fragmentation_ff_discard_vrb_entry_policy': [],
                  'fragmentation_ff_vrb_table_size'          : 50,
                  'app_pkLength'                             : 180,
                  'exec_numMotes'                            : 3,
                  'sf_type'                                  : 'SSFSymmetric',
                  'app_pkPeriod'                             : 0,
                  'app_pkPeriodVar'                          : 0,
                  'app_e2eAck'                               : False}
        sim_engine = sim_engine(**params)
        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
                'length':         sim_engine.settings.app_pkLength,
            },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2.sixlowpan.send(packet)
        hop2.sixlowpan.send(packet)
        hop2.sixlowpan.send(packet)
        hop2.sixlowpan.send(packet)
        frag0_0 = hop2.tsch.getTxQueue()[0]
        frag1_0 = hop2.tsch.getTxQueue()[2]
        frag2_0 = hop2.tsch.getTxQueue()[4]
        frag3_0 = hop2.tsch.getTxQueue()[6]

        tag_init = hop1.sixlowpan._get_next_datagram_tag()

        hop1.tsch.waitingFor = d.DIR_RX
        hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag0_0['payload'])
        hop1.tsch.waitingFor = d.DIR_RX
        hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag1_0['payload'])

        hop1.sixlowpan.next_datagram_tag = 65535

        hop1.tsch.waitingFor = d.DIR_RX
        hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag2_0['payload'])
        hop1.tsch.waitingFor = d.DIR_RX
        hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag3_0['payload'])

        tag0 = hop1.tsch.getTxQueue()[0]['payload']['datagram_tag']
        tag1 = hop1.tsch.getTxQueue()[1]['payload']['datagram_tag']
        tag2 = hop1.tsch.getTxQueue()[2]['payload']['datagram_tag']
        tag3 = hop1.tsch.getTxQueue()[3]['payload']['datagram_tag']

        assert tag0 == tag_init + 1
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == 65535
        assert tag3 == 0

    def test_tag_on_its_fragments_3(sim_engine):
        params = {'fragmentation'                            : 'FragmentForwarding',
                  'fragmentation_ff_discard_vrb_entry_policy': [],
                  'fragmentation_ff_vrb_table_size'          : 50,
                  'app_pkLength'                             : 180,
                  'exec_numMotes'                            : 3,
                  'sf_type'                                  : 'SSFSymmetric',
                  'app_pkPeriod'                             : 0,
                  'app_pkPeriodVar'                          : 0,
                  'app_e2eAck'                               : False}
        sim_engine = sim_engine(**params)
        root = sim_engine.motes[0]
        hop1 = sim_engine.motes[1]
        hop2 = sim_engine.motes[2]
        packet1 = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
                'length':         sim_engine.settings.app_pkLength,
            },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': hop1,
            'dstIp': root,
            'sourceRoute': []
        }
        packet2 = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source':  0,
                'hops':           1,
                'length':         sim_engine.settings.app_pkLength,
            },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': hop2,
            'dstIp': root,
            'sourceRoute': []
        }
        hop2.sixlowpan.send(packet2)
        hop2.sixlowpan.send(packet2)
        frag0_0 = hop2.tsch.getTxQueue()[0]
        frag1_0 = hop2.tsch.getTxQueue()[2]

        tag_init = hop1.sixlowpan.next_datagram_tag

        hop1.sixlowpan.send(packet1)
        tag0 = hop1.tsch.getTxQueue()[0]['payload']['datagram_tag']

        hop1.tsch.waitingFor = d.DIR_RX
        hop1.radio.rxDone(d.APP_TYPE_FRAG, None,
                          hop2, [hop1], hop2, root, [], frag0_0['payload'])
        tag1 = hop1.tsch.getTxQueue()[2]['payload']['datagram_tag']

        hop1.sixlowpan.send(packet1)
        tag2 = hop1.tsch.getTxQueue()[3]['payload']['datagram_tag']

        assert tag0 == tag_init
        assert tag1 == (tag0 + 1) % 65536
        assert tag2 == (tag1 + 1) % 65536

class TestOptimization:
    def test_remove_vrb_table_entry_by_expiration(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_discard_vrb_entry_policy': [],
                     'fragmentation_ff_vrb_table_size'          : 50,
                     'app_pkLength'                             : 360,
                     'exec_numMotes'                            : 3,
                     'conn_type'                                 : 'linear'})

        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        leaf = sim_engine.motes[2]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload'          : {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                'original_type': d.APP_TYPE_DATA,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf.sixlowpan.send(packet)
        frag0 = leaf.tsch.getTxQueue()[0]
        frag1 = leaf.tsch.getTxQueue()[1]
        frag2 = leaf.tsch.getTxQueue()[2]
        frag3 = leaf.tsch.getTxQueue()[3]


        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

        node.sixlowpan.recv(leaf, frag0)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        node.sixlowpan.recv(leaf, frag3)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        sim_engine.asn += (60 / sim_engine.settings.tsch_slotDuration) + 1
        # VRB Table entry expires
        node.sixlowpan.recv(leaf, frag2)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

    def test_remove_vrb_table_entry_on_last_frag(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_vrb_table_size'          : 50,
                     'app_pkLength'                             : 270,
                     'exec_numMotes'                            : 3,
                     'conn_type'                                 : 'linear',
                     'fragmentation_ff_discard_vrb_entry_policy': ['last_fragment']})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        leaf = sim_engine.motes[2]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload'          : {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                'original_type': d.APP_TYPE_DATA,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf.sixlowpan.send(packet)
        frag0 = leaf.tsch.getTxQueue()[0]
        frag1 = leaf.tsch.getTxQueue()[1]
        frag2 = leaf.tsch.getTxQueue()[2]

        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

        node.sixlowpan.recv(leaf, frag0)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        node.sixlowpan.recv(leaf, frag2)
        # the VRB entry is removed by frag2 (last)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

    def test_remove_vrb_table_entry_on_missing_frag(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_vrb_table_size'          : 50,
                     'app_pkLength'                             : 360,
                     'exec_numMotes'                            : 3,
                     'conn_type'                                 : 'linear',
                     'fragmentation_ff_discard_vrb_entry_policy': ['missing_fragment']})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        leaf = sim_engine.motes[2]
        packet = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf.sixlowpan.send(packet)
        frag0 = leaf.tsch.getTxQueue()[0]
        frag1 = leaf.tsch.getTxQueue()[1]
        frag2 = leaf.tsch.getTxQueue()[2]
        frag3 = leaf.tsch.getTxQueue()[3]

        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

        node.sixlowpan.recv(leaf, frag0)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        # frag2 after frag0 indicates frag1 is missing
        node.sixlowpan.recv(leaf, frag2)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        node.sixlowpan.recv(leaf, frag1)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        node.sixlowpan.recv(leaf, frag3)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0


    def test_remove_vrb_table_entry_on_last_and_missing(sim_engine):
        sim_engine = sim_engine(diff_config = {
               'fragmentation'                            : 'FragmentForwarding',
                     'fragmentation_ff_vrb_table_size'          : 50,
                     'app_pkLength'                             : 360,
                     'exec_numMotes'                            : 3,
                     'conn_type'                                 : 'linear',
                     'fragmentation_ff_discard_vrb_entry_policy': ['last_fragment', 'missing_fragment']})
        root = sim_engine.motes[0]
        node = sim_engine.motes[1]
        leaf = sim_engine.motes[2]
        packet1 = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        packet2 = {
            'asn': 0,
            'type': d.APP_TYPE_DATA,
            'code': None,
            'payload': {
                'asn_at_source': 0,
                'hops'         : 1,
                'length'       : sim_engine.settings.app_pkLength,
                },
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': leaf,
            'dstIp': root,
            'smac': leaf,
            'sourceRoute': []
        }
        leaf.sixlowpan.send(packet1)
        frag1_0 = leaf.tsch.getTxQueue()[0]
        frag1_1 = leaf.tsch.getTxQueue()[1]
        frag1_2 = leaf.tsch.getTxQueue()[2]
        frag1_3_1 = leaf.tsch.getTxQueue()[3]
        frag1_3_2 = copy.copy(frag1_3_1)
        frag1_3_2['payload'] = copy.deepcopy(frag1_3_1['payload'])
        leaf.sixlowpan.send(packet2)
        frag2_0 = leaf.tsch.getTxQueue()[0]
        frag2_1 = leaf.tsch.getTxQueue()[1]
        frag2_2 = leaf.tsch.getTxQueue()[2]
        frag2_3 = leaf.tsch.getTxQueue()[3]

        node.original_radio_drop_packet = node.radio.drop_packet
        test_is_called = {'result': False}

        def test(self, pkt, reason):
            test_is_called['result'] = True
            assert reason == 'frag_no_vrb_entry'

        node.radio.drop_packet = types.MethodType(test, node)

        assert len(node.sixlowpan.fragmentation.vrb_table) == 0

        node.sixlowpan.recv(leaf, frag1_0)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        node.sixlowpan.recv(leaf, frag1_1)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        node.sixlowpan.recv(leaf, frag1_2)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        node.sixlowpan.recv(leaf, frag1_3_1)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        # the VRB entry is removed by frag1_3_1 (last)
        frag1_3_2['smac'] = leaf
        node.sixlowpan.recv(leaf, frag1_3_2)
        assert test_is_called['result'] is True
        node.radio.drop_packet = node.original_radio_drop_packet

        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        node.sixlowpan.recv(leaf, frag2_0)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 1
        # frag2 after frag0 indicates frag1 is missing
        node.sixlowpan.recv(leaf, frag2_2)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        node.sixlowpan.recv(leaf, frag2_1)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
        node.sixlowpan.recv(leaf, frag2_3)
        assert len(node.sixlowpan.fragmentation.vrb_table) == 0
