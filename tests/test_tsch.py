"""
Test for TSCH layer
"""

import copy
import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d

# frame_type having "True" in "first_enqueuing" can be enqueued to TX queue
# even if the queue is full.
@pytest.mark.parametrize("frame_type", [
    d.PKT_TYPE_DATA,
    d.PKT_TYPE_JOIN_REQUEST,
    d.PKT_TYPE_JOIN_RESPONSE,
    d.PKT_TYPE_FRAG,
    d.PKT_TYPE_DAO,
    d.PKT_TYPE_6P_ADD_REQUEST,
    d.PKT_TYPE_6P_DELETE_REQUEST,
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
    test_frame = {
        'type': frame_type,
        'mac': {
            'srcMac': hop1.id,
            'dstMac': root.id,
        }
    }
    
    # ensure queuing fails
    assert hop1.tsch.enqueue(test_frame) == False

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

@pytest.mark.parametrize('destination, packet_type, expected_cell_options', [
    ('parent',    d.PKT_TYPE_DATA, d.DIR_TX),
])
def test_tx_cell_selection(
        sim_engine,
        packet_type,
        destination,
        expected_cell_options
    ):

    # cell selection rules:
    #
    # - DIR_TX should be used for a unicast packet to a neighbor to whom a sender
    #   has a dedicated TX cell
    # - DIR_TXRX_SHARED should be used otherwise
    #
    # With force_initial_routing_and_scheduling_state True, each mote has one
    # shared (TX/RX/SHARED) cell and one TX cell to its parent.

    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'            : 3,
            'sf_type'                  : 'SSFSymmetric',
            'conn_type'                : 'linear',
            'app_pkPeriod'             : 0,
            'app_pkPeriodVar'          : 0,
            'tsch_probBcast_ebDioProb' : 0,
        },
        force_initial_routing_and_scheduling_state = True
    )

    parent = sim_engine.motes[0]
    mote   = sim_engine.motes[1]
    child  = sim_engine.motes[2]

    packet = {
        'type':         packet_type,
        'app': {
            'rank':     mote.rpl.rank,
        },
        'net': {
            'srcIp':    mote.id
        },
    }

    # With packet_type=d.PKT_TYPE_DATA, we'll test if the right cell is chosen
    # to send a fragment. Set 180 to packet_length so that the packet is
    # divided into two fragments.
    if packet_type == d.PKT_TYPE_DATA:
        packet['net']['packet_length'] = 180

    # set destination IPv6 address
    if   destination == 'broadcast':
        packet['net']['dstIp'] = d.BROADCAST_ADDRESS
    elif destination == 'parent':
        packet['net']['dstIp'] = parent.id
    elif destination == 'child':
        packet['net']['dstIp'] = child.id

    # send a packet to the target destination
    mote.sixlowpan.sendPacket(packet)

    # wait for long enough for the packet to be sent
    u.run_until_asn(sim_engine, 1000)

    # see logs
    logs = []

    # as mentioned above, we'll see logs for fragment packets when
    # packet_type=d.PKT_TYPE_DATA
    if packet_type == d.PKT_TYPE_DATA:
        test_packet_type = d.PKT_TYPE_FRAG
    else:
        test_packet_type = packet_type

    for log in u.read_log_file(filter=['prop.transmission']):
        if  (
                (log['packet']['mac']['srcMac'] == mote.id)
                and
                (log['packet']['type']          == test_packet_type)
            ):
            logs.append(log)

    # transmission could be more than one due to retransmission
    assert(len(logs) > 0)

    for log in logs:
        timeslot_offset = log['_asn'] % sim_engine.settings.tsch_slotframeLength
        assert mote.tsch.schedule[timeslot_offset]['dir'] == expected_cell_options

@pytest.fixture(params=[d.PKT_TYPE_EB, d.PKT_TYPE_DIO])
def fixture_adv_frame(request):
    return request.param

def test_network_advertisement(sim_engine, fixture_adv_frame):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'            : 1,
        }
    )

    u.run_until_asn(sim_engine, 1000)

    logs = u.read_log_file(filter=['prop.transmission'])
    # root should send more than one EB in a default simulation run
    assert len([l for l in logs if l['packet']['type'] == fixture_adv_frame]) > 0
