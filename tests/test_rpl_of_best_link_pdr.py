import copy

import SimEngine.Mote.MoteDefines as d
import tests.test_utils as u

def create_dio(mote):
    dio = mote.rpl._create_DIO()
    dio['mac'] = {
        'srcMac': mote.get_mac_addr(),
        'dstMac': d.BROADCAST_ADDRESS
    }
    return dio

def test_free_run(sim_engine):
    sim_engine = sim_engine(
        diff_config = {'rpl_of': 'OFBestLinkPDR'}
    )
    u.run_until_end(sim_engine)


def test_parent_selection(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'  : 4,
            'conn_class'     : 'FullyMeshed',
            'phy_numChans'   : 1,
            'rpl_of'         : 'OFBestLinkPDR',
            'secjoin_enabled': False
        }
    )

    # shorthands
    connectivity_matrix = sim_engine.connectivity.matrix
    mote_0 = sim_engine.motes[0]
    mote_1 = sim_engine.motes[1]
    mote_2 = sim_engine.motes[2]
    mote_3 = sim_engine.motes[3]
    channel = d.TSCH_HOPPING_SEQUENCE[0]

    # disable the link between mote 0 and mote 3
    for src_id, dst_id in [
            (mote_0.id, mote_3.id),
            (mote_3.id, mote_0.id)
        ]:
        connectivity_matrix.set_pdr(src_id, dst_id, channel, 0.0)

    # degrade link PDRs to 30%:
    # - between mote 0 and mote 2
    # - between mote 3 and mote 1
    for src_id, dst_id in [
            (mote_0.id, mote_2.id),
            (mote_2.id, mote_0.id),
            (mote_1.id, mote_3.id),
            (mote_3.id, mote_1.id),
        ]:
        connectivity_matrix.set_pdr(src_id, dst_id, channel, 0.3)

    # now we have links shown below, () denotes link PDR:
    #
    #         [mote_0]
    #        /        \
    #     (1.0)      (0.3)
    #      /            \
    # [mote_1]--(1.0)--[mote_2]
    #      \            /
    #     (0.3)      (1.0)
    #        \        /
    #         [mote_3]

    # get all the motes synchronized
    eb = mote_0.tsch._create_EB()
    mote_1.tsch._action_receiveEB(eb)
    mote_2.tsch._action_receiveEB(eb)
    mote_3.tsch._action_receiveEB(eb)

    # make sure all the motes don't have their parents
    for mote in sim_engine.motes:
        assert mote.rpl.getPreferredParent() is None

    # test starts
    # step 1: make mote_1 and mote_2 connect to mote_0
    dio = create_dio(mote_0)
    mote_1.sixlowpan.recvPacket(dio)
    mote_2.sixlowpan.recvPacket(dio)
    assert mote_1.rpl.of.preferred_parent['mote_id'] == mote_0.id
    assert mote_2.rpl.of.preferred_parent['mote_id'] == mote_0.id

    # step 2: give a DIO of mote_1 to mote_2; then mote_2 should
    # switch its parent to mote_0
    dio = create_dio(mote_1)
    mote_2.sixlowpan.recvPacket(dio)
    assert mote_2.rpl.of.preferred_parent['mote_id'] == mote_1.id

    # step 3: give a DIO of mote_2 to mote_1; mote_1 should stay at
    # mote_0
    dio = create_dio(mote_2)
    mote_1.sixlowpan.recvPacket(dio)
    assert mote_1.rpl.of.preferred_parent['mote_id'] == mote_0.id

    # step 4: give a DIO of mote_1 to mote_3; mote_3 should connect to
    # mote_1
    dio = create_dio(mote_1)
    mote_3.sixlowpan.recvPacket(dio)
    assert mote_3.rpl.of.preferred_parent['mote_id'] == mote_1.id

    # step 5: give a DIO of mote_2 to mote_3; mote_3 should switch to
    # mote_2
    dio = create_dio(mote_2)
    mote_3.sixlowpan.recvPacket(dio)
    assert mote_3.rpl.of.preferred_parent['mote_id'] == mote_2.id

    # step 6: give a DIO of mote_0 to mote_3; mote_3 should stay at
    # mote_2
    dio = create_dio(mote_0)
    mote_3.sixlowpan.recvPacket(dio)
    assert dio['app']['rank'] < create_dio(mote_2)['app']['rank']
    assert mote_3.rpl.of.preferred_parent['mote_id'] == mote_2.id

    # step 7: give a fake DIO to mote_2 which has a very low rank and
    # mote_3's MAC address as its source address. mote_2 should ignore
    # this DIO to prevent a routing loop and stay at mote_1
    dio = create_dio(mote_3)
    dio['app']['rank'] = 0
    mote_2.sixlowpan.recvPacket(dio)
    assert mote_2.rpl.of.preferred_parent['mote_id'] == mote_1.id
