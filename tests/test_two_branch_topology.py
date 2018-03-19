"""
\brief Tests for TwoBranchTopology

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import SimEngine.SimEngine as SimEngine
import SimEngine.SimSettings as SimSettings
import SimEngine.Mote as Mote

def test_two_branch_topology_with_6_motes(motes):
    motes = motes(6, **{'topology': 'twoBranch'})
    assert len(motes) == 6
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[1].y == 0
    assert motes[2].x == 0.06 and motes[2].y == -0.03
    assert motes[3].x == 0.09 and motes[3].y == -0.03
    assert motes[4].x == 0.06 and motes[4].y == 0.03
    assert motes[5].x == 0.09 and motes[5].y == 0.03
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[1].PDR == {motes[0]: 1.0, motes[2]: 1.0, motes[4]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0, motes[3]: 1.0}
    assert motes[3].PDR == {motes[2]: 1.0}
    assert motes[4].PDR == {motes[1]: 1.0, motes[5]: 1.0}
    assert motes[5].PDR == {motes[4]: 1.0}
    assert motes[1].id in motes[0].RSSI
    assert motes[2].id in motes[0].RSSI
    assert motes[3].id in motes[0].RSSI
    assert motes[4].id in motes[0].RSSI
    assert motes[5].id in motes[0].RSSI
    assert motes[0].id in motes[1].RSSI
    assert motes[2].id in motes[1].RSSI
    assert motes[3].id in motes[1].RSSI
    assert motes[4].id in motes[1].RSSI
    assert motes[5].id in motes[1].RSSI
    assert motes[0].id in motes[2].RSSI
    assert motes[1].id in motes[2].RSSI
    assert motes[3].id in motes[2].RSSI
    assert motes[4].id in motes[2].RSSI
    assert motes[5].id in motes[2].RSSI
    assert motes[0].id in motes[3].RSSI
    assert motes[1].id in motes[3].RSSI
    assert motes[2].id in motes[3].RSSI
    assert motes[4].id in motes[3].RSSI
    assert motes[5].id in motes[3].RSSI
    assert motes[0].id in motes[4].RSSI
    assert motes[1].id in motes[4].RSSI
    assert motes[2].id in motes[4].RSSI
    assert motes[3].id in motes[4].RSSI
    assert motes[5].id in motes[4].RSSI
    assert motes[0].id in motes[5].RSSI
    assert motes[1].id in motes[5].RSSI
    assert motes[2].id in motes[5].RSSI
    assert motes[3].id in motes[5].RSSI
    assert motes[4].id in motes[5].RSSI


def test_two_branch_topology_with_9_motes(motes):
    motes = motes(9, **{'topology': 'twoBranch'})
    assert len(motes) == 9
    assert motes[0].x == 0 and motes[0].y == 0
    assert motes[1].x == 0.03 and motes[1].y == 0
    assert motes[2].x == 0.06 and motes[2].y == -0.03
    assert motes[3].x == 0.09 and motes[3].y == -0.03
    assert motes[4].x == 0.12 and motes[4].y == -0.03
    assert motes[5].x == 0.15 and motes[5].y == -0.03
    assert motes[6].x == 0.06 and motes[6].y == 0.03
    assert motes[7].x == 0.09 and motes[7].y == 0.03
    assert motes[8].x == 0.12 and motes[8].y == 0.03
    assert motes[0].PDR == {motes[1]: 1.0}
    assert motes[1].PDR == {motes[0]: 1.0, motes[2]: 1.0, motes[6]: 1.0}
    assert motes[2].PDR == {motes[1]: 1.0, motes[3]: 1.0}
    assert motes[3].PDR == {motes[2]: 1.0, motes[4]: 1.0}
    assert motes[4].PDR == {motes[3]: 1.0, motes[5]: 1.0}
    assert motes[5].PDR == {motes[4]: 1.0}
    assert motes[6].PDR == {motes[1]: 1.0, motes[7]: 1.0}
    assert motes[7].PDR == {motes[6]: 1.0, motes[8]: 1.0}
    assert motes[8].PDR == {motes[7]: 1.0}


def test_rpl_tree_builder(motes):
    motes = motes(6, **{'withJoin': False, 'topology': 'twoBranch'})

    assert motes[0].dagRoot == True
    assert motes[0].preferredParent == None
    assert motes[0].parents[(1,)] == [[0]]
    assert motes[0].parents[(2,)] == [[1]]
    assert motes[0].parents[(3,)] == [[2]]
    assert motes[0].parents[(4,)] == [[1]]
    assert motes[0].parents[(5,)] == [[4]]
    assert motes[0].rank == Mote.RPL_MIN_HOP_RANK_INCREASE
    assert motes[0].dagRank == 1

    assert motes[1].dagRoot == False
    assert motes[1].preferredParent == motes[0]
    assert motes[1].rank == Mote.RPL_MIN_HOP_RANK_INCREASE * 8
    assert motes[1].dagRank == 8

    assert motes[2].dagRoot == False
    assert motes[2].preferredParent == motes[1]
    assert motes[2].rank == Mote.RPL_MIN_HOP_RANK_INCREASE * 15
    assert motes[2].dagRank == 15

    assert motes[3].dagRoot == False
    assert motes[3].preferredParent == motes[2]
    assert motes[3].rank == Mote.RPL_MIN_HOP_RANK_INCREASE * 22
    assert motes[3].dagRank == 22

    assert motes[4].dagRoot == False
    assert motes[4].preferredParent == motes[1]
    assert motes[4].rank == Mote.RPL_MIN_HOP_RANK_INCREASE * 15
    assert motes[4].dagRank == 15

    assert motes[5].dagRoot == False
    assert motes[5].preferredParent == motes[4]
    assert motes[5].rank == Mote.RPL_MIN_HOP_RANK_INCREASE * 22
    assert motes[5].dagRank == 22


def test_two_branch_symmetric_schedule_installation(motes):
    motes = motes(7, **{'withJoin': False, 'topology': 'twoBranch'})

    assert motes[4].schedule[1]['ch'] == 0
    assert motes[4].schedule[1]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[1]['neighbor'] == motes[3]

    assert motes[6].schedule[2]['ch'] == 0
    assert motes[6].schedule[2]['dir'] == Mote.DIR_TX
    assert motes[6].schedule[2]['neighbor'] == motes[5]

    assert motes[3].schedule[1]['ch'] == 0
    assert motes[3].schedule[1]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[1]['neighbor'] == motes[4]
    assert motes[3].schedule[3]['ch'] == 0
    assert motes[3].schedule[3]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[3]['neighbor'] == motes[2]

    assert motes[5].schedule[2]['ch'] == 0
    assert motes[5].schedule[2]['dir'] == Mote.DIR_RX
    assert motes[5].schedule[2]['neighbor'] == motes[6]
    assert motes[5].schedule[4]['ch'] == 0
    assert motes[5].schedule[4]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[4]['neighbor'] == motes[1]

    assert motes[2].schedule[3]['ch'] == 0
    assert motes[2].schedule[3]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[3]['neighbor'] == motes[3]
    assert motes[2].schedule[5]['ch'] == 0
    assert motes[2].schedule[5]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[5]['neighbor'] == motes[1]

    assert motes[1].schedule[4]['ch'] == 0
    assert motes[1].schedule[4]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[4]['neighbor'] == motes[5]
    assert motes[1].schedule[5]['ch'] == 0
    assert motes[1].schedule[5]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[5]['neighbor'] == motes[2]
    assert motes[1].schedule[6]['ch'] == 0
    assert motes[1].schedule[6]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[6]['neighbor'] == motes[0]

    assert motes[0].schedule[6]['ch'] == 0
    assert motes[0].schedule[6]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[6]['neighbor'] == motes[1]


def test_two_branch_cascading_schedule_installation_1(motes):
    # un-event tree
    motes = motes(7, **{'withJoin': False, 'topology': 'twoBranch',
                        'cascadingScheduling': True})

    assert motes[6].schedule[1]['ch'] == 0
    assert motes[6].schedule[1]['dir'] == Mote.DIR_TX
    assert motes[6].schedule[1]['neighbor'] == motes[5]

    assert motes[5].schedule[1]['ch'] == 0
    assert motes[5].schedule[1]['dir'] == Mote.DIR_RX
    assert motes[5].schedule[1]['neighbor'] == motes[6]
    assert motes[5].schedule[2]['ch'] == 0
    assert motes[5].schedule[2]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[2]['neighbor'] == motes[1]

    assert motes[1].schedule[2]['ch'] == 0
    assert motes[1].schedule[2]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[2]['neighbor'] == motes[5]
    assert motes[1].schedule[3]['ch'] == 0
    assert motes[1].schedule[3]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[3]['neighbor'] == motes[0]

    assert motes[0].schedule[3]['ch'] == 0
    assert motes[0].schedule[3]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[3]['neighbor'] == motes[1]

    assert motes[5].schedule[4]['ch'] == 0
    assert motes[5].schedule[4]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[4]['neighbor'] == motes[1]

    assert motes[1].schedule[4]['ch'] == 0
    assert motes[1].schedule[4]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[4]['neighbor'] == motes[5]
    assert motes[1].schedule[5]['ch'] == 0
    assert motes[1].schedule[5]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[5]['neighbor'] == motes[0]

    assert motes[0].schedule[5]['ch'] == 0
    assert motes[0].schedule[5]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[5]['neighbor'] == motes[1]

    assert motes[4].schedule[6]['ch'] == 0
    assert motes[4].schedule[6]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[6]['neighbor'] == motes[3]

    assert motes[3].schedule[6]['ch'] == 0
    assert motes[3].schedule[6]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[6]['neighbor'] == motes[4]
    assert motes[3].schedule[7]['ch'] == 0
    assert motes[3].schedule[7]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[7]['neighbor'] == motes[2]

    assert motes[2].schedule[7]['ch'] == 0
    assert motes[2].schedule[7]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[7]['neighbor'] == motes[3]
    assert motes[2].schedule[8]['ch'] == 0
    assert motes[2].schedule[8]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[8]['neighbor'] == motes[1]

    assert motes[1].schedule[8]['ch'] == 0
    assert motes[1].schedule[8]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[8]['neighbor'] == motes[2]
    assert motes[1].schedule[9]['ch'] == 0
    assert motes[1].schedule[9]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[9]['neighbor'] == motes[0]

    assert motes[0].schedule[9]['ch'] == 0
    assert motes[0].schedule[9]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[9]['neighbor'] == motes[1]

    assert motes[3].schedule[10]['ch'] == 0
    assert motes[3].schedule[10]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[10]['neighbor'] == motes[2]

    assert motes[2].schedule[10]['ch'] == 0
    assert motes[2].schedule[10]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[10]['neighbor'] == motes[3]
    assert motes[2].schedule[11]['ch'] == 0
    assert motes[2].schedule[11]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[11]['neighbor'] == motes[1]

    assert motes[1].schedule[11]['ch'] == 0
    assert motes[1].schedule[11]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[11]['neighbor'] == motes[2]
    assert motes[1].schedule[12]['ch'] == 0
    assert motes[1].schedule[12]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[12]['neighbor'] == motes[0]

    assert motes[0].schedule[12]['ch'] == 0
    assert motes[0].schedule[12]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[12]['neighbor'] == motes[1]

    assert motes[2].schedule[13]['ch'] == 0
    assert motes[2].schedule[13]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[13]['neighbor'] == motes[1]

    assert motes[1].schedule[13]['ch'] == 0
    assert motes[1].schedule[13]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[13]['neighbor'] == motes[2]
    assert motes[1].schedule[14]['ch'] == 0
    assert motes[1].schedule[14]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[14]['neighbor'] == motes[0]

    assert motes[0].schedule[14]['ch'] == 0
    assert motes[0].schedule[14]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[14]['neighbor'] == motes[1]

    assert motes[1].schedule[15]['ch'] == 0
    assert motes[1].schedule[15]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[15]['neighbor'] == motes[0]

    assert motes[0].schedule[15]['ch'] == 0
    assert motes[0].schedule[15]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[15]['neighbor'] == motes[1]


def test_two_branch_cascading_schedule_installation_2(motes):
    # even tree
    motes = motes(8, **{'withJoin': False, 'topology': 'twoBranch',
                        'cascadingScheduling': True})

    assert motes[7].schedule[1]['ch'] == 0
    assert motes[7].schedule[1]['dir'] == Mote.DIR_TX
    assert motes[7].schedule[1]['neighbor'] == motes[6]

    assert motes[6].schedule[1]['ch'] == 0
    assert motes[6].schedule[1]['dir'] == Mote.DIR_RX
    assert motes[6].schedule[1]['neighbor'] == motes[7]
    assert motes[6].schedule[2]['ch'] == 0
    assert motes[6].schedule[2]['dir'] == Mote.DIR_TX
    assert motes[6].schedule[2]['neighbor'] == motes[5]

    assert motes[5].schedule[2]['ch'] == 0
    assert motes[5].schedule[2]['dir'] == Mote.DIR_RX
    assert motes[5].schedule[2]['neighbor'] == motes[6]
    assert motes[5].schedule[3]['ch'] == 0
    assert motes[5].schedule[3]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[3]['neighbor'] == motes[1]

    assert motes[1].schedule[3]['ch'] == 0
    assert motes[1].schedule[3]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[3]['neighbor'] == motes[5]
    assert motes[1].schedule[4]['ch'] == 0
    assert motes[1].schedule[4]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[4]['neighbor'] == motes[0]

    assert motes[0].schedule[4]['ch'] == 0
    assert motes[0].schedule[4]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[4]['neighbor'] == motes[1]

    assert motes[6].schedule[5]['ch'] == 0
    assert motes[6].schedule[5]['dir'] == Mote.DIR_TX
    assert motes[6].schedule[5]['neighbor'] == motes[5]

    assert motes[5].schedule[5]['ch'] == 0
    assert motes[5].schedule[5]['dir'] == Mote.DIR_RX
    assert motes[5].schedule[5]['neighbor'] == motes[6]
    assert motes[5].schedule[6]['ch'] == 0
    assert motes[5].schedule[6]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[6]['neighbor'] == motes[1]

    assert motes[1].schedule[6]['ch'] == 0
    assert motes[1].schedule[6]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[6]['neighbor'] == motes[5]
    assert motes[1].schedule[7]['ch'] == 0
    assert motes[1].schedule[7]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[7]['neighbor'] == motes[0]

    assert motes[0].schedule[7]['ch'] == 0
    assert motes[0].schedule[7]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[7]['neighbor'] == motes[1]

    assert motes[5].schedule[8]['ch'] == 0
    assert motes[5].schedule[8]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[8]['neighbor'] == motes[1]

    assert motes[1].schedule[8]['ch'] == 0
    assert motes[1].schedule[8]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[8]['neighbor'] == motes[5]
    assert motes[1].schedule[9]['ch'] == 0
    assert motes[1].schedule[9]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[9]['neighbor'] == motes[0]

    assert motes[0].schedule[9]['ch'] == 0
    assert motes[0].schedule[9]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[9]['neighbor'] == motes[1]

    assert motes[4].schedule[10]['ch'] == 0
    assert motes[4].schedule[10]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[10]['neighbor'] == motes[3]

    assert motes[3].schedule[10]['ch'] == 0
    assert motes[3].schedule[10]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[10]['neighbor'] == motes[4]
    assert motes[3].schedule[11]['ch'] == 0
    assert motes[3].schedule[11]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[11]['neighbor'] == motes[2]

    assert motes[2].schedule[11]['ch'] == 0
    assert motes[2].schedule[11]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[11]['neighbor'] == motes[3]
    assert motes[2].schedule[12]['ch'] == 0
    assert motes[2].schedule[12]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[12]['neighbor'] == motes[1]

    assert motes[1].schedule[12]['ch'] == 0
    assert motes[1].schedule[12]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[12]['neighbor'] == motes[2]
    assert motes[1].schedule[13]['ch'] == 0
    assert motes[1].schedule[13]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[13]['neighbor'] == motes[0]

    assert motes[0].schedule[13]['ch'] == 0
    assert motes[0].schedule[13]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[13]['neighbor'] == motes[1]

    assert motes[3].schedule[14]['ch'] == 0
    assert motes[3].schedule[14]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[14]['neighbor'] == motes[2]

    assert motes[2].schedule[14]['ch'] == 0
    assert motes[2].schedule[14]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[14]['neighbor'] == motes[3]
    assert motes[2].schedule[15]['ch'] == 0
    assert motes[2].schedule[15]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[15]['neighbor'] == motes[1]

    assert motes[1].schedule[15]['ch'] == 0
    assert motes[1].schedule[15]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[15]['neighbor'] == motes[2]
    assert motes[1].schedule[16]['ch'] == 0
    assert motes[1].schedule[16]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[16]['neighbor'] == motes[0]

    assert motes[0].schedule[16]['ch'] == 0
    assert motes[0].schedule[16]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[16]['neighbor'] == motes[1]

    assert motes[2].schedule[17]['ch'] == 0
    assert motes[2].schedule[17]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[17]['neighbor'] == motes[1]

    assert motes[1].schedule[17]['ch'] == 0
    assert motes[1].schedule[17]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[17]['neighbor'] == motes[2]
    assert motes[1].schedule[18]['ch'] == 0
    assert motes[1].schedule[18]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[18]['neighbor'] == motes[0]

    assert motes[0].schedule[18]['ch'] == 0
    assert motes[0].schedule[18]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[18]['neighbor'] == motes[1]

    assert motes[1].schedule[19]['ch'] == 0
    assert motes[1].schedule[19]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[19]['neighbor'] == motes[0]

    assert motes[0].schedule[19]['ch'] == 0
    assert motes[0].schedule[19]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[19]['neighbor'] == motes[1]


def test_two_branch_cascading_schedule_installation(motes):
    # even tree *without* random pick
    params = {'withJoin': False, 'topology': 'twoBranch',
              'cascadingScheduling': True}

    settings = SimSettings.SimSettings(**params)
    engine = SimEngine.SimEngine()
    motes1 = engine.motes
    engine.destroy()
    settings.destroy()

    settings = SimSettings.SimSettings(**params)
    engine = SimEngine.SimEngine()
    motes2 = engine.motes
    engine.destroy()
    settings.destroy()

    assert len(motes1) == len(motes2)
    for i, v in enumerate(motes1):
        assert len(motes1[i].schedule) == len(motes2[i].schedule)
        for j, cell in enumerate(motes1[i].schedule):
            if j not in motes1[i].schedule:
                continue

            cell1 = motes1[i].schedule[j]
            cell2 = motes2[i].schedule[j]

            if type(cell1['neighbor']) is list:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == Mote.DIR_TXRX_SHARED and
                       cell1['dir'] == cell2['dir'] and
                       (sorted(map(lambda x: x.id, cell1['neighbor'])) ==
                        sorted(map(lambda x: x.id, cell2['neighbor']))))
            else:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == cell2['dir'] and
                       cell1['neighbor'].id == cell2['neighbor'].id)
            assert ret is True


def test_two_branch_cascading_schedule_installation_4(motes):
    # even tree with random pick
    params = {'withJoin': False, 'topology': 'twoBranch',
              'cascadingScheduling': True,
              'schedulingMode': 'random-pick'}

    settings = SimSettings.SimSettings(**params)
    engine = SimEngine.SimEngine()
    motes1 = engine.motes
    engine.destroy()
    settings.destroy()

    settings = SimSettings.SimSettings(**params)
    engine = SimEngine.SimEngine()
    motes2 = engine.motes
    engine.destroy()
    settings.destroy()

    assert len(motes1) == len(motes2)
    prev_ret = True
    for i, v in enumerate(motes1):
        assert len(motes1[i].schedule) == len(motes2[i].schedule)
        for j, cell in enumerate(motes1[i].schedule):
            if j not in motes1[i].schedule:
                continue

            try:
                cell1 = motes1[i].schedule[j]
                cell2 = motes2[i].schedule[j]
            except KeyError:
                ret = False
                break

            if type(cell1['neighbor']) is list:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == Mote.DIR_TXRX_SHARED and
                       cell1['dir'] == cell2['dir'] and
                       (sorted(map(lambda x: x.id, cell1['neighbor'])) ==
                        sorted(map(lambda x: x.id, cell2['neighbor']))))
            else:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == cell2['dir'] and
                       cell1['neighbor'].id == cell2['neighbor'].id)

            ret = prev_ret and ret

        if ret is False:
            break

    # all schedules must not be the same
    assert ret is False
