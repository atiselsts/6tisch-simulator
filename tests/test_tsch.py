"""
Test for TSCH layer
"""

import copy
import pytest
import types

import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog

# frame_type having "True" in "first_enqueuing" can be enqueued to TX queue
# even if the queue is full.
@pytest.mark.parametrize("frame_type", [
    d.PKT_TYPE_DATA,
    d.PKT_TYPE_FRAG,
    d.PKT_TYPE_JOIN_REQUEST,
    d.PKT_TYPE_JOIN_RESPONSE,
    # not DIO (generetaed by TSCH directly)
    d.PKT_TYPE_DAO,
    # not EB (generetaed by tsch directly)
    d.PKT_TYPE_SIXP,
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

    # prepare an additional frame
    test_frame = {
        'type': frame_type,
        'mac': {
            'srcMac': hop1.id,
            'dstMac': root.id,
        }
    }

    # make sure that queuing that frame fails
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
    mote.tsch.remove_frame_from_tx_queue(type=3)
    assert mote.tsch.txQueue == [
        {'type': 1},
        {'type': 2},
        # removed
        {'type': 4},
        # removed
        {'type': 5},
    ]

@pytest.mark.parametrize('destination, packet_type, expected_cellOptions', [
    ('parent',    d.PKT_TYPE_DATA, [d.CELLOPTION_TX]),
])
def test_tx_cell_selection(
        sim_engine,
        packet_type,
        destination,
        expected_cellOptions
    ):

    # cell selection rules:
    #
    # - [CELLOPTION_TX] should be used for a unicast packet to a neighbor to whom a sender
    #   has a dedicated TX cell
    # - [CELLOPTION_TX,CELLOPTION_RX,CELLOPTION_SHARED] should be used otherwise
    #
    # With force_initial_routing_and_scheduling_state True, each mote has one
    # shared (TX/RX/SHARED) cell and one TX cell to its parent.

    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'            : 3,
            'sf_class'                  : 'SFNone',
            'conn_class'               : 'Linear',
            'app_pkPeriod'             : 0,
            'app_pkPeriodVar'          : 0,
            'tsch_probBcast_ebProb'    : 0,
        },
        force_initial_routing_and_scheduling_state = True
    )

    parent = sim_engine.motes[0]
    mote   = sim_engine.motes[1]
    child  = sim_engine.motes[2]

    packet = {
        'type':         packet_type,
        'app': {
            'rank':     mote.rpl.get_rank(),
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

    for log in u.read_log_file(filter=['tsch.txdone']):
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
        assert mote.tsch.schedule[timeslot_offset]['cellOptions'] == expected_cellOptions

@pytest.fixture(params=[d.PKT_TYPE_EB, d.PKT_TYPE_DIO])
def fixture_adv_frame(request):
    return request.param

def test_network_advertisement(sim_engine, fixture_adv_frame):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                1,
            'exec_numSlotframesPerRun':     100, # with 101 slots per slotframe, that's 10,100 slot total
        }
    )

    u.run_until_asn(sim_engine, 10000)

    logs = u.read_log_file(filter=['tsch.txdone'])
    # root should send more than one EB in a default simulation run
    assert len([l for l in logs if l['packet']['type'] == fixture_adv_frame]) > 0


@pytest.fixture(params=['dedicated-cell', 'shared-cell'])
def cell_type(request):
    return request.param

def test_retransmission_count(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numSlotframesPerRun': 10,
            'exec_numMotes'           : 2,
            'app_pkPeriod'            : 0,
            'rpl_daoPeriod'           : 0,
            'tsch_probBcast_ebProb'   : 0,
            'secjoin_enabled'         : False,
            'tsch_keep_alive_interval': 0,
            'conn_class'              : 'Linear'
        },
        force_initial_routing_and_scheduling_state = True
    )

    # short-hands
    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    connectivity_matrix = sim_engine.connectivity.connectivity_matrix

    # stop DIO timer
    root.rpl.trickle_timer.stop()
    hop1.rpl.trickle_timer.stop()

    # set 0% of PDR to the link between the two motes
    for channel in range(sim_engine.settings.phy_numChans):
        connectivity_matrix[root.id][hop1.id][channel]['pdr'] = 0
        connectivity_matrix[hop1.id][root.id][channel]['pdr'] = 0

    # make hop1 send an application packet
    hop1.app._send_a_single_packet()

    # run the simulation
    u.run_until_end(sim_engine)

    # check the log
    tx_logs = u.read_log_file([SimLog.LOG_TSCH_TXDONE['type']])

    # hop1 should send out the frame six times: 1 for the initial transmission
    # and 5 for retransmissions
    assert len(tx_logs) == 1 + d.TSCH_MAXTXRETRIES
    for tx_log in tx_logs:
        assert tx_log['packet']['type'] == d.PKT_TYPE_DATA
        assert tx_log['packet']['net']['srcIp'] == hop1.id
        assert tx_log['packet']['app']['appcounter'] == 0

def test_retransmission_backoff_algorithm(sim_engine, cell_type):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numSlotframesPerRun': 10000,
            'exec_numMotes'           : 2,
            'app_pkPeriod'            : 0,
            'secjoin_enabled'         : False
        }
    )
    sim_log = SimLog.SimLog()

    # filter logs to make this test faster; we need only SimLog.LOG_TSCH_TXDONE
    sim_log.set_log_filters([SimLog.LOG_TSCH_TXDONE['type']])

    # for quick access
    root  = sim_engine.motes[0]
    hop_1 = sim_engine.motes[1]
    slotframe_length = sim_engine.settings.tsch_slotframeLength

    # increase TSCH_MAXTXRETRIES so that we can have enough retransmission
    # samples to validate
    d.TSCH_MAXTXRETRIES = 100

    #== test setup ==

    u.run_until_everyone_joined(sim_engine)

    # make hop_1 ready to send an application packet
    assert hop_1.dodagId is None
    dio = root.rpl._create_DIO()
    hop_1.rpl.action_receiveDIO(dio)
    assert hop_1.dodagId is not None

    # make root ignore all the incoming frame for this test
    def ignoreRx(self, packet):
        self.waitingFor = None
        isACKed         = False
        return isACKed
    root.tsch.rxDone = types.MethodType(ignoreRx, root.tsch)

    if cell_type == 'dedicated-cell':
        # allocate one TX=1/RX=1/SHARED=1 cell to the motes as their dedicate cell.
        cellOptions   = [d.CELLOPTION_TX, d.CELLOPTION_RX, d.CELLOPTION_SHARED]

        assert len(root.tsch.getTxRxSharedCells(hop_1.id)) == 0
        root.tsch.addCell(1, 1, hop_1.id, cellOptions)
        assert len(root.tsch.getTxRxSharedCells(hop_1.id)) == 1

        assert len(hop_1.tsch.getTxRxSharedCells(root.id)) == 0
        hop_1.tsch.addCell(1, 1, root.id, cellOptions)
        assert len(hop_1.tsch.getTxRxSharedCells(root.id)) == 1

    # make sure hop_1 send a application packet when the simulator starts
    hop_1.tsch.txQueue = []
    hop_1.app._send_a_single_packet()
    assert len(hop_1.tsch.txQueue) == 1

    #== start test ==
    asn_starting_test = sim_engine.getAsn()
    # run the simulator until hop_1 drops the packet or the simulation ends
    def drop_packet(self, packet, reason):
        if packet['type'] == d.PKT_TYPE_DATA:
            # pause the simulator
            sim_engine.pauseAtAsn(sim_engine.getAsn() + 1)
    hop_1.drop_packet = types.MethodType(drop_packet, hop_1)
    u.run_until_end(sim_engine)

    # confirm
    # - hop_1 sent the application packet to the root
    # - retransmission backoff worked
    logs = u.read_log_file(
        filter     = [SimLog.LOG_TSCH_TXDONE['type']],
        after_asn  = asn_starting_test
    )
    app_data_tx_logs = []
    for log in logs:
        if (
                (log['_mote_id'] == hop_1.id)
                and
                (log['packet']['mac']['dstMac'] == root.id)
                and
                (log['packet']['type'] == d.PKT_TYPE_DATA)
            ):
            app_data_tx_logs.append(log)

    assert len(app_data_tx_logs) == 1 + d.TSCH_MAXTXRETRIES

    # all transmission should have happened only on the dedicated cell if it's
    # available (it shouldn't transmit a unicast frame to the root on the
    # minimal (shared) cell.
    if   cell_type == 'dedicated-cell':
        expected_cell_offset, _ = hop_1.tsch.getTxRxSharedCells(root.id).items()[0]
    elif cell_type == 'shared-cell':
        expected_cell_offset = 0   # the minimal (shared) cell
    else:
        raise NotImplementedError()

    for log in app_data_tx_logs:
        slot_offset = log['_asn'] % slotframe_length
        assert slot_offset == expected_cell_offset

    # retransmission should be performed after backoff wait; we should see gaps
    # between consecutive retransmissions. If all the gaps are 101 slots, that
    # is, one slotframe, this means there was no backoff wait between
    # transmissions.
    timestamps = [log['_asn'] for log in app_data_tx_logs]
    diffs = map(lambda x: x[1] - x[0], zip(timestamps[:-1], timestamps[1:]))
    assert len([diff for diff in diffs if diff != slotframe_length]) > 0

def test_eb_by_root(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes': 1
        }
    )

    root = sim_engine.motes[0]
    eb = root.tsch._create_EB()

    # From Section 6.1 of RFC 8180:
    #   ...
    #   DAGRank(rank(0))-1 = 0 is compliant with 802.15.4's requirement of
    #   having the root use Join Metric = 0.
    assert eb['app']['join_metric'] == 0
