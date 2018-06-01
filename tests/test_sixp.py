import copy
import types

import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine.Mote.sf import SchedulingFunctionBase

# =========================== helpers =========================================

COMMON_SIM_ENGINE_ARGS = {
    'diff_config': {
        'exec_numMotes'           : 2,
        'sf_class'                : 'SFNone',
        'conn_class'              : 'Linear',
        'app_pkPeriod'            : 0,
        'tsch_probBcast_ebDioProb': 0
    },
    'force_initial_routing_and_scheduling_state': True
}


class SchedulingFunctionTest(SchedulingFunctionBase):
    """Base class for scheduling functions defined here
    """

    # ======================= static values====================================

    DUMMY_CELL_LIST = {
        'slotOffset'   : 1,
        'channelOffset': 2
    }

    # ======================= public ==========================================

    def start(self):
        pass

    def stop(self):
        pass

    def indication_neighbor_added(self,neighbor_id):
        pass

    def indication_neighbor_deleted(self,neighbor_id):
        pass

    def indication_dedicated_tx_cell_elapsed(self,cell,used):
        pass

    def indication_parent_change(self, old_parent, new_parent):
        pass

    def detect_schedule_inconsistency(self, peerMac):
        pass

    def recv_request(self, packet):
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_REQUEST
        assert packet['app']['code'] in [
            d.SIXP_CMD_ADD,
            d.SIXP_CMD_DELETE,
            d.SIXP_CMD_RELOCATE
        ]

        self.mote.sixp.send_response(
            dstMac      = packet['mac']['srcMac'],
            return_code = d.SIXP_RC_SUCCESS,
            callback    = self._response_callback
        )

    # ======================= private ==========================================

    def _issue_add_request(self, peerMac, cellList):
        self.mote.sixp.send_request(
            dstMac   = peerMac,
            command  = d.SIXP_CMD_ADD,
            numCells = 0,
            cellList = cellList,
            callback = self._request_callback
        )

    def _issue_delete_request(self, peerMac, cellList):
        self.mote.sixp.send_request(
            dstMac   = peerMac,
            command  = d.SIXP_CMD_DELETE,
            numCells = 0,
            cellList = cellList,
            callback = self._request_callback
        )

    def _issue_relocate_request(self, peerMac, cellList):
        self.mote.sixp.send_request(
            dstMac             = peerMac,
            command            = d.SIXP_CMD_RELOCATE,
            numCells           = 0,
            relocationCellList = cellList,
            candidateCellList  = cellList,
            callback           = self._request_callback
        )

    def _request_callback(self, event, packet):
        raise NotImplementedError()

    @staticmethod
    def _response_callback(self, event, packet):
        raise NotImplementedError()


class SchedulingFunctionTwoStep(SchedulingFunctionTest):
    """This is an example scheduling function which supports 2-step
    ADD/DELETE/RELOCATE transactions.
    """
    # ======================= public ==========================================
    def issue_add_request(self, peerMac):
        self._issue_add_request(
            peerMac  = peerMac,
            cellList = self.DUMMY_CELL_LIST
        )

    def issue_delete_request(self, peerMac):
        self._issue_delete_request(
            peerMac  = peerMac,
            cellList = self.DUMMY_CELL_LIST
        )

    def issue_relocate_request(self, peerMac):
        self._issue_relocate_request(
            peerMac  = peerMac,
            cellList = self.DUMMY_CELL_LIST
        )

    def _request_callback(self, event, packet):
        # In a 2-step transaction, request_callback will receive
        # SIXP_CALLBACK_EVENT_PACKET_RECEPTION with a response packet
        assert event                    == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
        assert packet['app']['code']    == d.SIXP_RC_SUCCESS

    def _response_callback(self, event, packet):
        # In a 2-step transaction, response_callback will receive
        # SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION for the response packet
        assert event == d.SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
        assert packet['app']['code']    == d.SIXP_RC_SUCCESS


class SchedulingFunctionThreeStep(SchedulingFunctionTest):
    """This is an example scheduling function which supports 3-step
    ADD/DELETE/RELOCATE transactions. These request packet has empty
    cell list.
    """
    # ======================= public ==========================================
    def issue_add_request(self, peerMac):
        self._issue_add_request(
            peerMac  = peerMac,
            cellList = [] # empty cell list
        )

    def issue_delete_request(self, peerMac):
        self._issue_delete_request(
            peerMac  = peerMac,
            cellList = [] # empty cell list
        )

    def issue_relocate_request(self, peerMac):
        self._issue_relocate_request(
            peerMac  = peerMac,
            cellList = [] # empty cell list
        )

    def _request_callback(self, event, packet):
        # In a 3-step transaction, request_callback will receive
        # SIXP_CALLBACK_EVENT_PACKET_RECEPTION with a response packet as well
        # as in a 2-step transaction.
        assert event                    == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
        assert packet['app']['code']    == d.SIXP_RC_SUCCESS

        self.mote.sixp.send_confirmation(
            dstMac      = packet['mac']['srcMac'],
            return_code = d.SIXP_RC_SUCCESS,
            callback    = self._confirmation_callback
        )

    def _response_callback(self, event, packet):
        # In a 3-step transaction, response_callback will receive
        # SIXP_CALLBACK_EVENT_PACKET_RECEPTION with a *confirmation* packet
        # instead of SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION for the response
        assert event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_CONFIRMATION
        assert packet['app']['code']    == d.SIXP_RC_SUCCESS

    def _confirmation_callback(self, event, packet):
        # confirmation_callback will receive
        # SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION with the confirmation packet
        assert event == d.SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION
        assert packet['type']           == d.PKT_TYPE_SIXP
        assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_CONFIRMATION
        assert packet['app']['code']    == d.SIXP_RC_SUCCESS


def install_sf(motes, sf_class):
    for mote in motes:
        mote.sf = sf_class(mote)

# =========================== fixtures =========================================

SCHEDULING_FUNCTIONS = [
    SchedulingFunctionTwoStep,
    SchedulingFunctionThreeStep
]
@pytest.fixture(params=SCHEDULING_FUNCTIONS)
def scheduling_function(request):
    return request.param

# =========================== tests ===========================================


class TestTransaction:

    def test_transaciton_type(self, sim_engine, scheduling_function):

        sim_engine = sim_engine(**COMMON_SIM_ENGINE_ARGS)

        # install the test scheduling function to the motes
        install_sf(sim_engine.motes, scheduling_function)

        # trigger an ADD transaction
        sim_engine.motes[0].sf.issue_add_request(sim_engine.motes[1].id)
        u.run_until_asn(sim_engine, 1000)

        # trigger a DELETE transaction
        sim_engine.motes[0].sf.issue_delete_request(sim_engine.motes[1].id)
        u.run_until_asn(sim_engine, sim_engine.getAsn() + 1000)

        # trigger a RELOCATE transaction
        sim_engine.motes[0].sf.issue_relocate_request(sim_engine.motes[1].id)
        u.run_until_asn(sim_engine, sim_engine.getAsn() + 1000)

        # done
        assert True

    def test_concurrent_transactions(self, sim_engine):
        """6P must return RC_ERR_BUSY when it receives a request from a peer
        with whom it has already another transaction in process.
        """

        sim_engine = sim_engine(**COMMON_SIM_ENGINE_ARGS)

        # for quick access
        initiator = sim_engine.motes[0]
        responder = sim_engine.motes[1]

        # trigger an ADD transaction, which will terminate by timeout on the
        # initiator.sfinitiator's side
        initiator.sixp.send_request(
            dstMac        = responder.id,
            command       = d.SIXP_CMD_ADD,
            cellList      = [],
            timeout_value = 1
        )

        # wait a little bit
        u.run_until_asn(sim_engine, 200)

        # now responder should have a transaction; issue a DELETE request,
        # which should cause RC_ERR_BUSY
        result = {'is_callback_called': False}
        def request_callback(event, packet):
            result['is_callback_called'] = True
            assert event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION
            assert packet['type'] == d.PKT_TYPE_SIXP
            assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
            assert packet['app']['code']    == d.SIXP_RC_ERR_BUSY
        initiator.sixp.send_request(
            dstMac   = responder.id,
            command  = d.SIXP_CMD_DELETE,
            cellList = [],
            callback = request_callback
        )

        # wait a little bit
        u.run_until_asn(sim_engine, sim_engine.getAsn() + 200)

        assert result['is_callback_called'] is True

    def test_timeout(self, sim_engine):
        sim_engine = sim_engine(**COMMON_SIM_ENGINE_ARGS)

        # for quick access
        mote_0 = sim_engine.motes[0]
        mote_1 = sim_engine.motes[1]

        # test timeout on the initiator side
        result = {'is_request_callback_called': False}
        def request_callback(event, packet):
            assert event  == d.SIXP_CALLBACK_EVENT_TIMEOUT
            assert packet is None
            result['is_request_callback_called'] = True
        mote_0.sixp.send_request(
            dstMac   = mote_1.id,
            command  = d.SIXP_CMD_COUNT,
            callback = request_callback
        )

        # test timeout on the responder side
        result['is_response_callback_called'] = False
        def response_callback(event, packet):
            assert event  == d.SIXP_CALLBACK_EVENT_TIMEOUT
            assert packet is None
            result['is_response_callback_called'] = True
        def recv_request(self, packet):
            # fill up the TX queue so that the response will not be sent.
            for _ in range(0, d.TSCH_QUEUE_SIZE):
                # enqueue dummy packets, which are generated from the incoming
                # packet
                dummy_packet = copy.deepcopy(packet)
                dummy_packet['mac']['dstMac'] = dummy_packet['mac']['srcMac']
                dummy_packet['mac']['srcMac'] = self.mote.id
                mote_1.tsch.enqueue(dummy_packet)
            self.mote.sixp.send_response(
                dstMac      = packet['mac']['srcMac'],
                return_code = d.SIXP_RC_SUCCESS,
                callback    = response_callback
            )
        mote_1.sf.recv_request = types.MethodType(
            recv_request,
            mote_1.sf
        )

        # run the simulator
        u.run_until_end(sim_engine)

        assert result['is_request_callback_called']  is True
        assert result['is_response_callback_called'] is True


class TestSeqNum:

    @pytest.fixture(params=[0, 1, 2, 100, 200, 254, 255])
    def initial_seqnum(self, request):
        return request.param

    def test_seqnum_increment(self, sim_engine, initial_seqnum):
        sim_engine = sim_engine(**COMMON_SIM_ENGINE_ARGS)

        # install a test SF
        install_sf(sim_engine.motes, SchedulingFunctionTwoStep)

        # for quick access
        mote_0 = sim_engine.motes[0]
        mote_1 = sim_engine.motes[1]

        # set initial SeqNum
        mote_0.sixp.seqnum_table[mote_1.id] = initial_seqnum
        mote_1.sixp.seqnum_table[mote_0.id] = initial_seqnum

        # execute one transaction
        mote_0.sf.issue_add_request(mote_1.id)

        # wait a little bit
        u.run_until_asn(sim_engine, 500)

        # check the SeqNums both of the motes maintain
        if initial_seqnum == 255:
            expected_seqnum = 1
        else:
            expected_seqnum = initial_seqnum + 1
        assert mote_0.sixp.seqnum_table[mote_1.id] == expected_seqnum
        assert mote_1.sixp.seqnum_table[mote_0.id] == expected_seqnum

    def test_schedule_inconsistency(self, sim_engine, initial_seqnum):
        sim_engine = sim_engine(**COMMON_SIM_ENGINE_ARGS)

        # for quick access
        mote_0 = sim_engine.motes[0]
        mote_1 = sim_engine.motes[1]

        # set initial SeqNum; the motes have different initial SeqNum
        mote_0.sixp.seqnum_table[mote_1.id] = initial_seqnum
        mote_1.sixp.seqnum_table[mote_0.id] = initial_seqnum + 1

        # prepare assertion
        result = {'is_schedule_inconsistency_detected': False}
        def detect_schedule_inconsistency(self, peerMac):
            assert peerMac == mote_0.id
            result['is_schedule_inconsistency_detected'] = True
        mote_1.sf.detect_schedule_inconsistency = types.MethodType(
            detect_schedule_inconsistency,
            mote_1.sf
        )

        # send a request which causes the responder to detect schedule
        # inconsistency. the initiator should receive RC_ERR_SEQNUM.
        result['is_rc_err_seqnum_received'] = False
        def request_callback(event, packet):
            assert event == d.SIXP_CALLBACK_EVENT_PACKET_RECEPTION
            assert packet['app']['msgType'] == d.SIXP_MSG_TYPE_RESPONSE
            assert packet['app']['code']    == d.SIXP_RC_ERR_SEQNUM
            result['is_rc_err_seqnum_received'] = True
        mote_0.sixp.send_request(
            dstMac   = mote_1.id,
            command  = d.SIXP_CMD_COUNT,
            callback = request_callback
        )

        # wait a little bit
        u.run_until_asn(sim_engine, 500)

        assert result['is_schedule_inconsistency_detected'] is True
        assert result['is_rc_err_seqnum_received']          is True
