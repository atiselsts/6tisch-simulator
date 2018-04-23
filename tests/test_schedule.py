import SimEngine.Mote.Mote as Mote
import SimEngine.Mote.MoteDefines as d

def test_linear_symmetric_schedule_1(sim):

    sim = sim(
        **{
            'exec_numMotes': 3,
            'sf_type':       'SSF-symmetric',
            'top_type':      'linear',
        }
    )
    motes = sim.motes

    assert motes[0].numCellsToNeighbors == {}
    assert motes[0].numCellsFromNeighbors[motes[1]] == 1
    assert len(motes[0].schedule) == 2
    assert motes[0].tsch.getSchedule()[0]['ch'] == 0
    assert motes[0].tsch.getSchedule()[0]['dir'] == d.DIR_TXRX_SHARED
    assert motes[0].tsch.getSchedule()[0]['neighbor'] == [motes[1]]
    assert motes[0].tsch.getSchedule()[2]['ch'] == 0
    assert motes[0].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[2]['neighbor'] == motes[1]

    assert motes[1].numCellsToNeighbors[motes[0]] == 1
    assert motes[1].numCellsFromNeighbors[motes[2]] == 1
    assert len(motes[1].schedule) == 3
    assert motes[1].tsch.getSchedule()[0]['ch'] == 0
    assert motes[1].tsch.getSchedule()[0]['dir'] == d.DIR_TXRX_SHARED
    assert len(motes[1].tsch.getSchedule()[0]['neighbor']) == 2
    assert motes[0] in motes[1].tsch.getSchedule()[0]['neighbor']
    assert motes[2] in motes[1].tsch.getSchedule()[0]['neighbor']
    assert motes[1].tsch.getSchedule()[1]['ch'] == 0
    assert motes[1].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[1]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[2]['ch'] == 0
    assert motes[1].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[2]['neighbor'] == motes[0]

    assert motes[2].numCellsToNeighbors[motes[1]] == 1
    assert motes[2].numCellsFromNeighbors == {}
    assert len(motes[2].schedule) == 2
    assert motes[2].tsch.getSchedule()[0]['ch'] == 0
    assert motes[2].tsch.getSchedule()[0]['dir'] == d.DIR_TXRX_SHARED
    assert motes[2].tsch.getSchedule()[0]['neighbor'] == [motes[1]]
    assert motes[2].tsch.getSchedule()[1]['ch'] == 0
    assert motes[2].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[1]['neighbor'] == motes[1]

def test_linear_symmetric_schedule_2(sim):

    sim = sim(
        **{
            'exec_numMotes': 8,
            'sf_type':       'SSF-symmetric',
            'top_type':      'linear',
        }
    )
    motes = sim.motes

    assert motes[7].tsch.getSchedule()[1]['ch'] == 0
    assert motes[7].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[7].tsch.getSchedule()[1]['neighbor'] == motes[6]

    assert motes[6].tsch.getSchedule()[1]['ch'] == 0
    assert motes[6].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[6].tsch.getSchedule()[1]['neighbor'] == motes[7]
    assert motes[6].tsch.getSchedule()[2]['ch'] == 0
    assert motes[6].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[2]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[2]['ch'] == 0
    assert motes[5].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[2]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[3]['ch'] == 0
    assert motes[5].tsch.getSchedule()[3]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[3]['neighbor'] == motes[4]

    assert motes[4].tsch.getSchedule()[3]['ch'] == 0
    assert motes[4].tsch.getSchedule()[3]['dir'] == d.DIR_RX
    assert motes[4].tsch.getSchedule()[3]['neighbor'] == motes[5]
    assert motes[4].tsch.getSchedule()[4]['ch'] == 0
    assert motes[4].tsch.getSchedule()[4]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[4]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[4]['ch'] == 0
    assert motes[3].tsch.getSchedule()[4]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[4]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[5]['ch'] == 0
    assert motes[3].tsch.getSchedule()[5]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[5]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[5]['ch'] == 0
    assert motes[2].tsch.getSchedule()[5]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[5]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[6]['ch'] == 0
    assert motes[2].tsch.getSchedule()[6]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[6]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[6]['ch'] == 0
    assert motes[1].tsch.getSchedule()[6]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[6]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[7]['ch'] == 0
    assert motes[1].tsch.getSchedule()[7]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[7]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[7]['ch'] == 0
    assert motes[0].tsch.getSchedule()[7]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[7]['neighbor'] == motes[1]


def test_linear_cascading_schedule_installation(sim):
    sim = sim(
        **{
            'exec_numMotes': 8,
            'top_type':      'linear',
            'sf_type':       'SSF-cascading',
        }
    )
    motes = sim.motes

    assert motes[7].tsch.getSchedule()[1]['ch'] == 0
    assert motes[7].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[7].tsch.getSchedule()[1]['neighbor'] == motes[6]

    assert motes[6].tsch.getSchedule()[1]['ch'] == 0
    assert motes[6].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[6].tsch.getSchedule()[1]['neighbor'] == motes[7]
    assert motes[6].tsch.getSchedule()[2]['ch'] == 0
    assert motes[6].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[2]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[2]['ch'] == 0
    assert motes[5].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[2]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[3]['ch'] == 0
    assert motes[5].tsch.getSchedule()[3]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[3]['neighbor'] == motes[4]

    assert motes[4].tsch.getSchedule()[3]['ch'] == 0
    assert motes[4].tsch.getSchedule()[3]['dir'] == d.DIR_RX
    assert motes[4].tsch.getSchedule()[3]['neighbor'] == motes[5]
    assert motes[4].tsch.getSchedule()[4]['ch'] == 0
    assert motes[4].tsch.getSchedule()[4]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[4]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[4]['ch'] == 0
    assert motes[3].tsch.getSchedule()[4]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[4]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[5]['ch'] == 0
    assert motes[3].tsch.getSchedule()[5]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[5]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[5]['ch'] == 0
    assert motes[2].tsch.getSchedule()[5]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[5]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[6]['ch'] == 0
    assert motes[2].tsch.getSchedule()[6]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[6]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[6]['ch'] == 0
    assert motes[1].tsch.getSchedule()[6]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[6]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[7]['ch'] == 0
    assert motes[1].tsch.getSchedule()[7]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[7]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[7]['ch'] == 0
    assert motes[0].tsch.getSchedule()[7]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[7]['neighbor'] == motes[1]

    assert motes[6].tsch.getSchedule()[8]['ch'] == 0
    assert motes[6].tsch.getSchedule()[8]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[8]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[8]['ch'] == 0
    assert motes[5].tsch.getSchedule()[8]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[8]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[9]['ch'] == 0
    assert motes[5].tsch.getSchedule()[9]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[9]['neighbor'] == motes[4]

    assert motes[4].tsch.getSchedule()[9]['ch'] == 0
    assert motes[4].tsch.getSchedule()[9]['dir'] == d.DIR_RX
    assert motes[4].tsch.getSchedule()[9]['neighbor'] == motes[5]
    assert motes[4].tsch.getSchedule()[10]['ch'] == 0
    assert motes[4].tsch.getSchedule()[10]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[10]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[10]['ch'] == 0
    assert motes[3].tsch.getSchedule()[10]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[10]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[11]['ch'] == 0
    assert motes[3].tsch.getSchedule()[11]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[11]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[11]['ch'] == 0
    assert motes[2].tsch.getSchedule()[11]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[11]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[12]['ch'] == 0
    assert motes[2].tsch.getSchedule()[12]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[12]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[12]['ch'] == 0
    assert motes[1].tsch.getSchedule()[12]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[12]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[13]['ch'] == 0
    assert motes[1].tsch.getSchedule()[13]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[13]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[13]['ch'] == 0
    assert motes[0].tsch.getSchedule()[13]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[13]['neighbor'] == motes[1]

    assert motes[5].tsch.getSchedule()[14]['ch'] == 0
    assert motes[5].tsch.getSchedule()[14]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[14]['neighbor'] == motes[4]

    assert motes[4].tsch.getSchedule()[14]['ch'] == 0
    assert motes[4].tsch.getSchedule()[14]['dir'] == d.DIR_RX
    assert motes[4].tsch.getSchedule()[14]['neighbor'] == motes[5]
    assert motes[4].tsch.getSchedule()[15]['ch'] == 0
    assert motes[4].tsch.getSchedule()[15]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[15]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[15]['ch'] == 0
    assert motes[3].tsch.getSchedule()[15]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[15]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[16]['ch'] == 0
    assert motes[3].tsch.getSchedule()[16]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[16]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[16]['ch'] == 0
    assert motes[2].tsch.getSchedule()[16]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[16]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[17]['ch'] == 0
    assert motes[2].tsch.getSchedule()[17]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[17]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[17]['ch'] == 0
    assert motes[1].tsch.getSchedule()[17]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[17]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[18]['ch'] == 0
    assert motes[1].tsch.getSchedule()[18]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[18]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[18]['ch'] == 0
    assert motes[0].tsch.getSchedule()[18]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[18]['neighbor'] == motes[1]

    assert motes[4].tsch.getSchedule()[19]['ch'] == 0
    assert motes[4].tsch.getSchedule()[19]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[19]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[19]['ch'] == 0
    assert motes[3].tsch.getSchedule()[19]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[19]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[20]['ch'] == 0
    assert motes[3].tsch.getSchedule()[20]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[20]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[20]['ch'] == 0
    assert motes[2].tsch.getSchedule()[20]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[20]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[21]['ch'] == 0
    assert motes[2].tsch.getSchedule()[21]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[21]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[21]['ch'] == 0
    assert motes[1].tsch.getSchedule()[21]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[21]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[22]['ch'] == 0
    assert motes[1].tsch.getSchedule()[22]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[22]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[22]['ch'] == 0
    assert motes[0].tsch.getSchedule()[22]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[22]['neighbor'] == motes[1]

    assert motes[3].tsch.getSchedule()[23]['ch'] == 0
    assert motes[3].tsch.getSchedule()[23]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[23]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[23]['ch'] == 0
    assert motes[2].tsch.getSchedule()[23]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[23]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[24]['ch'] == 0
    assert motes[2].tsch.getSchedule()[24]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[24]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[24]['ch'] == 0
    assert motes[1].tsch.getSchedule()[24]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[24]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[25]['ch'] == 0
    assert motes[1].tsch.getSchedule()[25]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[25]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[25]['ch'] == 0
    assert motes[0].tsch.getSchedule()[25]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[25]['neighbor'] == motes[1]

    assert motes[2].tsch.getSchedule()[26]['ch'] == 0
    assert motes[2].tsch.getSchedule()[26]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[26]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[26]['ch'] == 0
    assert motes[1].tsch.getSchedule()[26]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[26]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[27]['ch'] == 0
    assert motes[1].tsch.getSchedule()[27]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[27]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[27]['ch'] == 0
    assert motes[0].tsch.getSchedule()[27]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[27]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[28]['ch'] == 0
    assert motes[1].tsch.getSchedule()[28]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[28]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[28]['ch'] == 0
    assert motes[0].tsch.getSchedule()[28]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[28]['neighbor'] == motes[1]

def test_two_branch_symmetric_schedule_installation(sim):
    sim = sim(**{'exec_numMotes': 7,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-symmetric'})
    motes = sim.motes

    assert motes[4].tsch.getSchedule()[1]['ch'] == 0
    assert motes[4].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[1]['neighbor'] == motes[3]

    assert motes[6].tsch.getSchedule()[2]['ch'] == 0
    assert motes[6].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[2]['neighbor'] == motes[5]

    assert motes[3].tsch.getSchedule()[1]['ch'] == 0
    assert motes[3].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[1]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[3]['ch'] == 0
    assert motes[3].tsch.getSchedule()[3]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[3]['neighbor'] == motes[2]

    assert motes[5].tsch.getSchedule()[2]['ch'] == 0
    assert motes[5].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[2]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[4]['ch'] == 0
    assert motes[5].tsch.getSchedule()[4]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[4]['neighbor'] == motes[1]

    assert motes[2].tsch.getSchedule()[3]['ch'] == 0
    assert motes[2].tsch.getSchedule()[3]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[3]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[5]['ch'] == 0
    assert motes[2].tsch.getSchedule()[5]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[5]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[4]['ch'] == 0
    assert motes[1].tsch.getSchedule()[4]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[4]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[5]['ch'] == 0
    assert motes[1].tsch.getSchedule()[5]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[5]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[6]['ch'] == 0
    assert motes[1].tsch.getSchedule()[6]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[6]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[6]['ch'] == 0
    assert motes[0].tsch.getSchedule()[6]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[6]['neighbor'] == motes[1]


def test_two_branch_cascading_schedule_installation_1(sim):
    # un-event tree
    sim = sim(**{'exec_numMotes': 7,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-cascading'})
    motes = sim.motes

    assert motes[6].tsch.getSchedule()[1]['ch'] == 0
    assert motes[6].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[1]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[1]['ch'] == 0
    assert motes[5].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[1]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[2]['ch'] == 0
    assert motes[5].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[2]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[2]['ch'] == 0
    assert motes[1].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[2]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[3]['ch'] == 0
    assert motes[1].tsch.getSchedule()[3]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[3]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[3]['ch'] == 0
    assert motes[0].tsch.getSchedule()[3]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[3]['neighbor'] == motes[1]

    assert motes[5].tsch.getSchedule()[4]['ch'] == 0
    assert motes[5].tsch.getSchedule()[4]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[4]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[4]['ch'] == 0
    assert motes[1].tsch.getSchedule()[4]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[4]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[5]['ch'] == 0
    assert motes[1].tsch.getSchedule()[5]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[5]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[5]['ch'] == 0
    assert motes[0].tsch.getSchedule()[5]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[5]['neighbor'] == motes[1]

    assert motes[4].tsch.getSchedule()[6]['ch'] == 0
    assert motes[4].tsch.getSchedule()[6]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[6]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[6]['ch'] == 0
    assert motes[3].tsch.getSchedule()[6]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[6]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[7]['ch'] == 0
    assert motes[3].tsch.getSchedule()[7]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[7]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[7]['ch'] == 0
    assert motes[2].tsch.getSchedule()[7]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[7]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[8]['ch'] == 0
    assert motes[2].tsch.getSchedule()[8]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[8]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[8]['ch'] == 0
    assert motes[1].tsch.getSchedule()[8]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[8]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[9]['ch'] == 0
    assert motes[1].tsch.getSchedule()[9]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[9]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[9]['ch'] == 0
    assert motes[0].tsch.getSchedule()[9]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[9]['neighbor'] == motes[1]

    assert motes[3].tsch.getSchedule()[10]['ch'] == 0
    assert motes[3].tsch.getSchedule()[10]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[10]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[10]['ch'] == 0
    assert motes[2].tsch.getSchedule()[10]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[10]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[11]['ch'] == 0
    assert motes[2].tsch.getSchedule()[11]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[11]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[11]['ch'] == 0
    assert motes[1].tsch.getSchedule()[11]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[11]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[12]['ch'] == 0
    assert motes[1].tsch.getSchedule()[12]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[12]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[12]['ch'] == 0
    assert motes[0].tsch.getSchedule()[12]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[12]['neighbor'] == motes[1]

    assert motes[2].tsch.getSchedule()[13]['ch'] == 0
    assert motes[2].tsch.getSchedule()[13]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[13]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[13]['ch'] == 0
    assert motes[1].tsch.getSchedule()[13]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[13]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[14]['ch'] == 0
    assert motes[1].tsch.getSchedule()[14]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[14]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[14]['ch'] == 0
    assert motes[0].tsch.getSchedule()[14]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[14]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[15]['ch'] == 0
    assert motes[1].tsch.getSchedule()[15]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[15]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[15]['ch'] == 0
    assert motes[0].tsch.getSchedule()[15]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[15]['neighbor'] == motes[1]


def test_two_branch_cascading_schedule_installation_2(sim):
    # even tree
    sim = sim(**{'exec_numMotes': 8,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-cascading'})
    motes = sim.motes

    assert motes[7].tsch.getSchedule()[1]['ch'] == 0
    assert motes[7].tsch.getSchedule()[1]['dir'] == d.DIR_TX
    assert motes[7].tsch.getSchedule()[1]['neighbor'] == motes[6]

    assert motes[6].tsch.getSchedule()[1]['ch'] == 0
    assert motes[6].tsch.getSchedule()[1]['dir'] == d.DIR_RX
    assert motes[6].tsch.getSchedule()[1]['neighbor'] == motes[7]
    assert motes[6].tsch.getSchedule()[2]['ch'] == 0
    assert motes[6].tsch.getSchedule()[2]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[2]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[2]['ch'] == 0
    assert motes[5].tsch.getSchedule()[2]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[2]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[3]['ch'] == 0
    assert motes[5].tsch.getSchedule()[3]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[3]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[3]['ch'] == 0
    assert motes[1].tsch.getSchedule()[3]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[3]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[4]['ch'] == 0
    assert motes[1].tsch.getSchedule()[4]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[4]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[4]['ch'] == 0
    assert motes[0].tsch.getSchedule()[4]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[4]['neighbor'] == motes[1]

    assert motes[6].tsch.getSchedule()[5]['ch'] == 0
    assert motes[6].tsch.getSchedule()[5]['dir'] == d.DIR_TX
    assert motes[6].tsch.getSchedule()[5]['neighbor'] == motes[5]

    assert motes[5].tsch.getSchedule()[5]['ch'] == 0
    assert motes[5].tsch.getSchedule()[5]['dir'] == d.DIR_RX
    assert motes[5].tsch.getSchedule()[5]['neighbor'] == motes[6]
    assert motes[5].tsch.getSchedule()[6]['ch'] == 0
    assert motes[5].tsch.getSchedule()[6]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[6]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[6]['ch'] == 0
    assert motes[1].tsch.getSchedule()[6]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[6]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[7]['ch'] == 0
    assert motes[1].tsch.getSchedule()[7]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[7]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[7]['ch'] == 0
    assert motes[0].tsch.getSchedule()[7]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[7]['neighbor'] == motes[1]

    assert motes[5].tsch.getSchedule()[8]['ch'] == 0
    assert motes[5].tsch.getSchedule()[8]['dir'] == d.DIR_TX
    assert motes[5].tsch.getSchedule()[8]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[8]['ch'] == 0
    assert motes[1].tsch.getSchedule()[8]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[8]['neighbor'] == motes[5]
    assert motes[1].tsch.getSchedule()[9]['ch'] == 0
    assert motes[1].tsch.getSchedule()[9]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[9]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[9]['ch'] == 0
    assert motes[0].tsch.getSchedule()[9]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[9]['neighbor'] == motes[1]

    assert motes[4].tsch.getSchedule()[10]['ch'] == 0
    assert motes[4].tsch.getSchedule()[10]['dir'] == d.DIR_TX
    assert motes[4].tsch.getSchedule()[10]['neighbor'] == motes[3]

    assert motes[3].tsch.getSchedule()[10]['ch'] == 0
    assert motes[3].tsch.getSchedule()[10]['dir'] == d.DIR_RX
    assert motes[3].tsch.getSchedule()[10]['neighbor'] == motes[4]
    assert motes[3].tsch.getSchedule()[11]['ch'] == 0
    assert motes[3].tsch.getSchedule()[11]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[11]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[11]['ch'] == 0
    assert motes[2].tsch.getSchedule()[11]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[11]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[12]['ch'] == 0
    assert motes[2].tsch.getSchedule()[12]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[12]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[12]['ch'] == 0
    assert motes[1].tsch.getSchedule()[12]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[12]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[13]['ch'] == 0
    assert motes[1].tsch.getSchedule()[13]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[13]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[13]['ch'] == 0
    assert motes[0].tsch.getSchedule()[13]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[13]['neighbor'] == motes[1]

    assert motes[3].tsch.getSchedule()[14]['ch'] == 0
    assert motes[3].tsch.getSchedule()[14]['dir'] == d.DIR_TX
    assert motes[3].tsch.getSchedule()[14]['neighbor'] == motes[2]

    assert motes[2].tsch.getSchedule()[14]['ch'] == 0
    assert motes[2].tsch.getSchedule()[14]['dir'] == d.DIR_RX
    assert motes[2].tsch.getSchedule()[14]['neighbor'] == motes[3]
    assert motes[2].tsch.getSchedule()[15]['ch'] == 0
    assert motes[2].tsch.getSchedule()[15]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[15]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[15]['ch'] == 0
    assert motes[1].tsch.getSchedule()[15]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[15]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[16]['ch'] == 0
    assert motes[1].tsch.getSchedule()[16]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[16]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[16]['ch'] == 0
    assert motes[0].tsch.getSchedule()[16]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[16]['neighbor'] == motes[1]

    assert motes[2].tsch.getSchedule()[17]['ch'] == 0
    assert motes[2].tsch.getSchedule()[17]['dir'] == d.DIR_TX
    assert motes[2].tsch.getSchedule()[17]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[17]['ch'] == 0
    assert motes[1].tsch.getSchedule()[17]['dir'] == d.DIR_RX
    assert motes[1].tsch.getSchedule()[17]['neighbor'] == motes[2]
    assert motes[1].tsch.getSchedule()[18]['ch'] == 0
    assert motes[1].tsch.getSchedule()[18]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[18]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[18]['ch'] == 0
    assert motes[0].tsch.getSchedule()[18]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[18]['neighbor'] == motes[1]

    assert motes[1].tsch.getSchedule()[19]['ch'] == 0
    assert motes[1].tsch.getSchedule()[19]['dir'] == d.DIR_TX
    assert motes[1].tsch.getSchedule()[19]['neighbor'] == motes[0]

    assert motes[0].tsch.getSchedule()[19]['ch'] == 0
    assert motes[0].tsch.getSchedule()[19]['dir'] == d.DIR_RX
    assert motes[0].tsch.getSchedule()[19]['neighbor'] == motes[1]

def test_two_branch_cascading_schedule_installation(sim):
    # even tree *without* random pick
    sim1 = sim(**{
        'top_type': 'twoBranch',
        'sf_type': 'SSF-cascading'})

    motes1 = sim1.motes
    sim1.destroy()

    sim2 = sim(**{
        'top_type': 'twoBranch',
        'sf_type': 'SSF-cascading'})
    motes2 = sim2.motes

    assert len(motes1) == len(motes2)
    for i, v in enumerate(motes1):
        assert len(motes1[i].schedule) == len(motes2[i].schedule)
        for j in motes1[i].schedule.keys():
            assert j in motes2[i].schedule

            cell1 = motes1[i].tsch.getSchedule()[j]
            cell2 = motes2[i].tsch.getSchedule()[j]

            if type(cell1['neighbor']) is list:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == d.DIR_TXRX_SHARED and
                       cell1['dir'] == cell2['dir'] and
                       (sorted(map(lambda x: x.id, cell1['neighbor'])) ==
                        sorted(map(lambda x: x.id, cell2['neighbor']))))
            else:
                ret = (cell1['ch'] == cell2['ch'] and
                       cell1['dir'] == cell2['dir'] and
                       cell1['neighbor'].id == cell2['neighbor'].id)
            assert ret is True


def test_two_branch_cascading_schedule_installation_4(sim):
    # even tree with random pick
    sim1 = sim(**{'top_type': 'twoBranch',
                  'sf_type': 'SSF-cascading',
                  'sf_ssf_initMethod': 'random-pick'})
    motes1 = sim1.motes
    sim1.destroy()

    sim2 = sim(**{'top_type': 'twoBranch',
                  'sf_type': 'SSF-cascading',
                  'sf_ssf_initMethod': 'random-pick'})
    motes2 = sim2.motes

    ret = False
    assert len(motes1) == len(motes2)
    for i, v in enumerate(motes1):
        assert len(motes1[i].schedule) == len(motes2[i].schedule)

        for j in motes1[i].schedule.keys():
            # the motes in the first simulation should have different timeslot
            # allocacations from the motes in the second simulation
            if j not in motes2[i].schedule:
                ret = True
                break

    assert ret is True
