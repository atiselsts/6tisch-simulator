"""
Tests for SimEngine.Mote.rpl
"""

import types

import pytest

import test_utils as u
import SimEngine.Mote.MoteDefines as d
import SimEngine.Mote.rpl as rpl

@pytest.fixture(params=['FullyMeshed','Linear'])
def fixture_conn_class(request):
    return request.param

def test_ranks_forced_state(sim_engine,fixture_conn_class):
    '''
    Verify the force_initial_routing_and_scheduling_state option
    create the expected RPL state.
    '''

    sim_engine = sim_engine(
        {
            'exec_numMotes': 3,
            'conn_class':    fixture_conn_class,
        },
        force_initial_routing_and_scheduling_state = True
    )

    root = sim_engine.motes[0]
    hop1 = sim_engine.motes[1]
    hop2 = sim_engine.motes[2]

    assert root.dagRoot is True
    assert root.rpl.getPreferredParent()      ==    None
    assert root.rpl._get_rank()               ==     256
    assert root.rpl.getDagRank()              ==       1

    assert hop1.dagRoot is False
    assert hop1.rpl.getPreferredParent()      == root.id
    assert hop1.rpl._get_rank()               ==     768
    assert hop1.rpl.getDagRank()              ==       3

    if   fixture_conn_class=='FullyMeshed':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == root.id
        assert hop2.rpl._get_rank()           ==     768
        assert hop2.rpl.getDagRank()          ==       3
    elif fixture_conn_class=='Linear':
        assert hop2.dagRoot is False
        assert hop2.rpl.getPreferredParent()  == hop1.id
        assert hop2.rpl._get_rank()           ==    1280
        assert hop2.rpl.getDagRank()          ==       5
    else:
        raise SystemError()

def test_source_route_calculation(sim_engine):

    sim_engine = sim_engine(
        {
            'exec_numMotes':      1,
        },
    )

    mote = sim_engine.motes[0]

    # assume DAOs have been receuved by all mote in this topology
    '''          4----5
                /
       0 ----- 1 ------ 2 ----- 3  NODAO  6 ---- 7
    '''
    mote.rpl.addParentChildfromDAOs(parent_id=0, child_id=1)
    mote.rpl.addParentChildfromDAOs(parent_id=1, child_id=4)
    mote.rpl.addParentChildfromDAOs(parent_id=4, child_id=5)
    mote.rpl.addParentChildfromDAOs(parent_id=1, child_id=2)
    mote.rpl.addParentChildfromDAOs(parent_id=2, child_id=3)
    # no DAO received for 6->3 link
    mote.rpl.addParentChildfromDAOs(parent_id=6, child_id=7)

    # verify all source routes
    assert mote.rpl.computeSourceRoute(1) == [1]
    assert mote.rpl.computeSourceRoute(2) == [1,2]
    assert mote.rpl.computeSourceRoute(3) == [1,2,3]
    assert mote.rpl.computeSourceRoute(4) == [1,4]
    assert mote.rpl.computeSourceRoute(5) == [1,4,5]
    assert mote.rpl.computeSourceRoute(6) == None
    assert mote.rpl.computeSourceRoute(7) == None


def test_upstream_routing(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes': 3,
            'conn_class'   : 'FullyMeshed',
        }
    )

    root  = sim_engine.motes[0]
    mote_1 = sim_engine.motes[1]
    mote_2 = sim_engine.motes[2]

    u.run_until_everyone_joined(sim_engine)

    # We're making the RPL topology of "root -- mote_1 (-- mote_2)"
    dio_from_root = root.rpl._create_DIO()
    dio_from_root['app']['rank'] = 256
    mote_1.rpl.action_receiveDIO(dio_from_root)
    assert mote_1.rpl.getPreferredParent() == root.id

    # Then, put mote_1 behind mote_2:    "root -- mote_2 -- mote_1"
    mote_2.rpl.action_receiveDIO(dio_from_root)
    dio_from_mote_2 = mote_2.rpl._create_DIO()

    dio_from_root['app']['rank'] = 65535
    mote_1.rpl.action_receiveDIO(dio_from_root)

    dio_from_mote_2['app']['rank'] = 256
    # make sure mote_1 has mote_2 in its 'Mote.neighbors'
    mote_1.neighbors_indicate_rx(dio_from_mote_2)
    # inject DIO from mote_2 to mote_1
    mote_1.rpl.action_receiveDIO(dio_from_mote_2)

    assert mote_1.rpl.getPreferredParent() == mote_2.id
    assert mote_2.rpl.getPreferredParent() == root.id

    # create a dummy packet, which is used to get the next hop
    dummy_packet = {
        'net': {
            'srcIp': mote_1.id,
            'dstIp': root.id
        }
    }

    # the next hop should be parent
    assert mote_1.rpl.findNextHopId(dummy_packet) == mote_1.rpl.getPreferredParent()


class TestOF0(object):
    def test_rank_computation(self, sim_engine):
        # https://tools.ietf.org/html/rfc8180#section-5.1.2
        sim_engine = sim_engine(
            diff_config = {
                'exec_numMotes'           : 6,
                'exec_numSlotframesPerRun': 10000,
                'app_pkPeriod'            : 0,
                'secjoin_enabled'         : False,
                'tsch_keep_alive_interval': 0,
                'conn_class'              : 'Linear',
            }
        )

        # shorthand
        motes = sim_engine.motes
        asn_at_end_of_simulation = (
            sim_engine.settings.tsch_slotframeLength *
            sim_engine.settings.exec_numSlotframesPerRun
        )

        # get the network ready to be test
        u.run_until_everyone_joined(sim_engine)
        assert sim_engine.getAsn() < asn_at_end_of_simulation

        def _returnStaticETX(self, neighbor_id):
            return 100.0 / 75
        for mote_id in range(1, len(motes)):
            mote = motes[mote_id]
            parent_id = mote_id - 1
            # override _estimateETX method so that it always returns
            # (numTx=100/numTxAck=75).
            mote.rpl._estimateETX = types.MethodType(_returnStaticETX, mote.rpl)
            assert mote.rpl._estimateETX(parent_id) == (100.0 / 75)
            # inject DIO to the mote
            dio = motes[parent_id].rpl._create_DIO()
            mote.rpl.action_receiveDIO(dio)

        # test using rank values in Figure 4 of RFC 8180
        assert motes[0].rpl._get_rank() == 256
        assert motes[0].rpl.getDagRank() == 1

        assert motes[1].rpl._get_rank() == 768
        assert motes[1].rpl.getDagRank() == 3

        assert motes[2].rpl._get_rank() == 1280
        assert motes[2].rpl.getDagRank() == 5

        assert motes[3].rpl._get_rank() == 1792
        assert motes[3].rpl.getDagRank() == 7

        assert motes[4].rpl._get_rank() == 2304
        assert motes[4].rpl.getDagRank() == 9

        assert motes[5].rpl._get_rank() == 2816
        assert motes[5].rpl.getDagRank() == 11
