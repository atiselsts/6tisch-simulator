"""
Test for TSCH layer
"""

import copy
import pytest

import SimEngine.Mote.MoteDefines as d

# frame_type having "True" in "first_enqueuing" can be enqueued to TX queue
# even if the queue is full.
@pytest.mark.parametrize("frame_type", [
    d.APP_TYPE_DATA,
    d.APP_TYPE_ACK,
    d.APP_TYPE_JOIN,
    d.NET_TYPE_FRAG,
    d.RPL_TYPE_DIO,
    d.RPL_TYPE_DAO,
    d.TSCH_TYPE_EB,
    d.IANA_6TOP_TYPE_REQUEST,
    d.IANA_6TOP_TYPE_RESPONSE,
])
def test_enqueue_under_full_tx_queue(sim_engine,frame_type):
    """
    Test Tsch.enqueue(self) under the situation when TX queue is full
    """
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                         3,
        },
        force_initial_routing_and_scheduling_state = True
    )

    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    # fill the TX queue with dummy frames
    dummy_frame = {'type': 'dummy_frame_type'}
    for _ in range(0, d.TSCH_QUEUE_SIZE):
        hop1.tsch.txQueue.append(dummy_frame)
    assert len(hop1.tsch.txQueue) == d.TSCH_QUEUE_SIZE

    # prepare a test_frame
    test_frame = {'type': frame_type,'app': {},'net': {}}
    '''
    if (
            (frame_type == d.RPL_TYPE_DIO) or
            (frame_type == d.TSCH_TYPE_EB)
       ):
        # always broadcast
        test_frame['dstIp']       = d.BROADCAST_ADDRESS
    elif frame_type == d.APP_TYPE_ACK:
        # always downstream frame
        test_frame['dstIp']       = hop2
        test_frame['sourceRoute'] = root.rpl.computeSourceRoute(hop2.id)
    else:
        # this frame_type is used for either upstream or downstream. in this
        # test, it's treated as upstream. dstIp is set with root.
        test_frame['dstIp']       = root
    '''

    # ensure queuing fails
    assert hop1.tsch.enqueue(copy.deepcopy(test_frame)) == False

def test_removeTypeFromQueue(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes': 1,
        },
    )
    
    mote = sim_engine.motes[0]
    
    mote.tsch.txQueue = [
        {'type': 1},
        {'type': 2},
        {'type': 3},
        {'type': 4},
        {'type': 3},
        {'type': 5},
    ]
    mote.tsch.removeTypeFromQueue(type=3)
    assert mote.tsch.txQueue == [
        {'type': 1},
        {'type': 2},
        # removed
        {'type': 4},
        # removed
        {'type': 5},
    ]
