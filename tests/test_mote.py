"""
\brief Tests for Mote

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import types

import SimEngine.Mote as Mote

def test_app_schedule_transmit(sim):

    sim = sim(
        **{
            'numMotes':                2,
            'pkPeriod':                0,
            'beaconPeriod':            0,
            'dioPeriod':               0,
            'daoPeriod':               0,
            'top_type':                'linear',
            'scheduling_function':     "SSF-cascading"
        }
    )
    node = sim.motes[1]
    # active TX cell event for node, active RX cell event for root, and
    # propagation event
    assert len(sim.events) == 3
    node.pkPeriod = 100
    node._app_schedule_sendSinglePacket(firstPacket=True)
    assert len(sim.events) == 4
    print sim.events[3][2]
    assert sim.events[3][2] == node._app_action_sendSinglePacket


def test_drop_join_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'joinAttemptTimeout': 0})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_JOIN}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node.join_sendJoinPacket('token', root)
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1


def test_drop_data_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedDataFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedDataFailedEnqueue'] == 0
    node._app_action_enqueueData()
    assert test_is_called['result'] is True
    assert node.motestats['droppedDataFailedEnqueue'] == 1


def test_drop_frag_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numFragments': 2})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    node._app_action_enqueueData()
    assert test_is_called['result'] is True


def test_drop_app_ack_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'downwardAcks': True})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': node, 'type': Mote.APP_TYPE_DATA, 'sourceRoute': []}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(root.txQueue) == i
        assert root._tsch_enqueue(packet) is True
        assert len(root.txQueue) == i + 1

    root.original_radio_drop_packet = root._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedAppAckFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    root._radio_drop_packet = types.MethodType(test, root)
    root._app_action_receivePacket(node, [1, 0, 1], 0)
    assert test_is_called['result'] is True


def test_drop_eb_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node._tsch_action_enqueueEB()
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1


def test_drop_dio_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node._rpl_action_enqueueDIO()
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1


def test_drop_dao_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.RPL_TYPE_DAO}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node._rpl_action_enqueueDAO()
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1


def test_drop_sixtop_request_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.IANA_6TOP_TYPE_REQUEST}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node._sixtop_enqueue_ADD_REQUEST(root, [], 1, Mote.DIR_TX, 1)
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1

    test_is_called = {'result': False}
    assert test_is_called['result'] is False
    node._sixtop_enqueue_DELETE_REQUEST(root, [], 1, Mote.DIR_TX, 1)
    assert test_is_called['result'] is True


def test_drop_sixtop_respnose_packet_tx_queue_full(sim):
    sim = sim(**{'numMotes': 2, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]

    packet = {'dstIp': root, 'type': Mote.IANA_6TOP_TYPE_RESPONSE}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    assert node.motestats['droppedFailedEnqueue'] == 0
    node._sixtop_enqueue_RESPONSE(root, [], Mote.IANA_6TOP_RC_SUCCESS, Mote.DIR_TX, 1)
    assert test_is_called['result'] is True
    assert node.motestats['droppedFailedEnqueue'] == 1


def test_drop_forwarding_frag_tx_queue_full(sim):
    sim = sim(**{'numMotes': 3, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numFragments': 2, 'enableFragmentForwarding': True,})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf = sim.motes[2]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    payload = [2, 0, 1]
    payload.append({'datagram_tag': 1, 'datagram_size': 2, 'datagram_offset': 0})
    node.waitingFor = Mote.DIR_RX
    node.radio_rxDone(type=Mote.APP_TYPE_FRAG, smac=leaf,
                      dmac=[node], srcIp=leaf, dstIp=root, payload=payload)
    assert test_is_called['result'] is True


def test_drop_forwarding_frag_vrb_table_full(sim):
    sim = sim(**{'numMotes': 3, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numFragments': 2, 'enableFragmentForwarding': True})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf = sim.motes[2]

    frag = {'smac': leaf, 'dstIp': root, 'payload': [2, 0, 1]}
    frag['payload'].append({'datagram_tag': 1, 'datagram_size': 2, 'datagram_offset': 0})

    node.vrbTable[leaf] = {}
    for i in range(0, Mote.FRAGMENT_FORWARDING_DEFAULT_MAX_VRB_ENTRY_NUM):
        # fill VRB Table
        node.vrbTable[leaf][i] = {'otag': 0, 'ts': 0}

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragVRBTableFull'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    node._app_is_frag_to_forward(frag)
    assert test_is_called['result'] is True


def test_drop_forwarding_frag_no_vrb_entry(sim):
    sim = sim(**{'numMotes': 3, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numFragments': 2, 'enableFragmentForwarding': True})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf = sim.motes[2]

    frag = {'smac': leaf, 'dstIp': root, 'payload': [2, 0, 1]}
    frag['payload'].append({'datagram_tag': 1, 'datagram_size': 2, 'datagram_offset': 1})

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragNoVRBEntry'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    node._app_is_frag_to_forward(frag)
    assert test_is_called['result'] is True


def test_drop_forwarding_data_tx_queue_full(sim):
    sim = sim(**{'numMotes': 3, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading'})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf = sim.motes[2]

    packet = {'dstIp': root, 'type': Mote.APP_TYPE_DATA}

    for i in range(0, 10):
        # fill txQueue, whose size is 10
        assert len(node.txQueue) == i
        assert node._tsch_enqueue(packet) is True
        assert len(node.txQueue) == i + 1

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedRelayFailedEnqueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)
    payload = [2, 0, 1]
    node.waitingFor = Mote.DIR_RX
    node.radio_rxDone(type=Mote.APP_TYPE_DATA, smac=leaf,
                      dmac=[node], srcIp=leaf, dstIp=root, payload=payload)
    assert test_is_called['result'] is True


def test_drop_frag_reassembly_queue_full(sim):
    sim = sim(**{'numMotes': 4, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numReassQueue': 1, 'numFragments': 2})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf1 = sim.motes[2]
    leaf2 = sim.motes[3]

    payload = [2, 0, 1]
    # fragment can be enqueued even if datagram_offset is not 0
    payload.append({'datagram_tag': 12345, 'datagram_size': 2, 'datagram_offset': 1})

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragReassQueueFull'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)

    assert len(node.reassQueue) == 0
    assert node._app_reass_packet(leaf1, payload) is False
    assert len(node.reassQueue) == 1
    assert leaf1 in node.reassQueue
    assert 12345 in node.reassQueue[leaf1]

    assert node._app_reass_packet(leaf2, payload) is False
    assert test_is_called['result'] is True
    assert len(node.reassQueue) == 1


def test_drop_frag_too_big_for_reassembly_queue(sim):
    sim = sim(**{'numMotes': 4, 'pkPeriod': 0,
                 'top_type': 'linear', 'scheduling_function': 'SSF-cascading',
                 'numReassQueue': 1, 'numFragments': 2})
    root = sim.motes[0]
    node = sim.motes[1]
    leaf1 = sim.motes[2]
    leaf2 = sim.motes[3]

    payload = [2, 0, 1]
    # fragment can be enqueued even if datagram_offset is not 0
    payload.append({'datagram_tag': 12345, 'datagram_size': 3, 'datagram_offset': 1})

    node.original_radio_drop_packet = node._radio_drop_packet
    test_is_called = {'result': False}

    def test(self, pkt, reason):
        test_is_called['result'] = True
        assert len(pkt) > 0
        assert reason == 'droppedFragTooBigForReassQueue'
        self.original_radio_drop_packet(pkt, reason)
        assert len(pkt) == 0

    node._radio_drop_packet = types.MethodType(test, node)

    assert len(node.reassQueue) == 0
    assert node._app_reass_packet(leaf1, payload) is False
    assert test_is_called['result'] is True
    assert len(node.reassQueue) == 0
