import SimEngine.Mote as Mote

def test_linear_symmetric_schedule_1(sim):

    sim = sim(**{'exec_numMotes':3,
                 'sf_type': 'SSF-symmetric',
                 'top_type': 'linear'})
    motes = sim.motes

    assert motes[0].numCellsToNeighbors == {}
    assert motes[0].numCellsFromNeighbors[motes[1]] == 1
    assert len(motes[0].schedule) == 2
    assert motes[0].schedule[0]['ch'] == 0
    assert motes[0].schedule[0]['dir'] == Mote.DIR_TXRX_SHARED
    assert motes[0].schedule[0]['neighbor'] == [motes[1]]
    assert motes[0].schedule[2]['ch'] == 0
    assert motes[0].schedule[2]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[2]['neighbor'] == motes[1]

    assert motes[1].numCellsToNeighbors[motes[0]] == 1
    assert motes[1].numCellsFromNeighbors[motes[2]] == 1
    assert len(motes[1].schedule) == 3
    assert motes[1].schedule[0]['ch'] == 0
    assert motes[1].schedule[0]['dir'] == Mote.DIR_TXRX_SHARED
    assert len(motes[1].schedule[0]['neighbor']) == 2
    assert motes[0] in motes[1].schedule[0]['neighbor']
    assert motes[2] in motes[1].schedule[0]['neighbor']
    assert motes[1].schedule[1]['ch'] == 0
    assert motes[1].schedule[1]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[1]['neighbor'] == motes[2]
    assert motes[1].schedule[2]['ch'] == 0
    assert motes[1].schedule[2]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[2]['neighbor'] == motes[0]

    assert motes[2].numCellsToNeighbors[motes[1]] == 1
    assert motes[2].numCellsFromNeighbors == {}
    assert len(motes[2].schedule) == 2
    assert motes[2].schedule[0]['ch'] == 0
    assert motes[2].schedule[0]['dir'] == Mote.DIR_TXRX_SHARED
    assert motes[2].schedule[0]['neighbor'] == [motes[1]]
    assert motes[2].schedule[1]['ch'] == 0
    assert motes[2].schedule[1]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[1]['neighbor'] == motes[1]

def test_linear_symmetric_schedule_2(sim):

    sim = sim(**{'exec_numMotes':8,
                 'sf_type': 'SSF-symmetric',
                 'top_type': 'linear'})
    motes = sim.motes

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
    assert motes[5].schedule[3]['neighbor'] == motes[4]

    assert motes[4].schedule[3]['ch'] == 0
    assert motes[4].schedule[3]['dir'] == Mote.DIR_RX
    assert motes[4].schedule[3]['neighbor'] == motes[5]
    assert motes[4].schedule[4]['ch'] == 0
    assert motes[4].schedule[4]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[4]['neighbor'] == motes[3]

    assert motes[3].schedule[4]['ch'] == 0
    assert motes[3].schedule[4]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[4]['neighbor'] == motes[4]
    assert motes[3].schedule[5]['ch'] == 0
    assert motes[3].schedule[5]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[5]['neighbor'] == motes[2]

    assert motes[2].schedule[5]['ch'] == 0
    assert motes[2].schedule[5]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[5]['neighbor'] == motes[3]
    assert motes[2].schedule[6]['ch'] == 0
    assert motes[2].schedule[6]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[6]['neighbor'] == motes[1]

    assert motes[1].schedule[6]['ch'] == 0
    assert motes[1].schedule[6]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[6]['neighbor'] == motes[2]
    assert motes[1].schedule[7]['ch'] == 0
    assert motes[1].schedule[7]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[7]['neighbor'] == motes[0]

    assert motes[0].schedule[7]['ch'] == 0
    assert motes[0].schedule[7]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[7]['neighbor'] == motes[1]


def test_linear_cascading_schedule_installation(sim):
    sim = sim(**{'exec_numMotes': 8,
                 'top_type': 'linear',
                 'sf_type': 'SSF-cascading'})
    motes = sim.motes

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
    assert motes[5].schedule[3]['neighbor'] == motes[4]

    assert motes[4].schedule[3]['ch'] == 0
    assert motes[4].schedule[3]['dir'] == Mote.DIR_RX
    assert motes[4].schedule[3]['neighbor'] == motes[5]
    assert motes[4].schedule[4]['ch'] == 0
    assert motes[4].schedule[4]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[4]['neighbor'] == motes[3]

    assert motes[3].schedule[4]['ch'] == 0
    assert motes[3].schedule[4]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[4]['neighbor'] == motes[4]
    assert motes[3].schedule[5]['ch'] == 0
    assert motes[3].schedule[5]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[5]['neighbor'] == motes[2]

    assert motes[2].schedule[5]['ch'] == 0
    assert motes[2].schedule[5]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[5]['neighbor'] == motes[3]
    assert motes[2].schedule[6]['ch'] == 0
    assert motes[2].schedule[6]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[6]['neighbor'] == motes[1]

    assert motes[1].schedule[6]['ch'] == 0
    assert motes[1].schedule[6]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[6]['neighbor'] == motes[2]
    assert motes[1].schedule[7]['ch'] == 0
    assert motes[1].schedule[7]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[7]['neighbor'] == motes[0]

    assert motes[0].schedule[7]['ch'] == 0
    assert motes[0].schedule[7]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[7]['neighbor'] == motes[1]

    assert motes[6].schedule[8]['ch'] == 0
    assert motes[6].schedule[8]['dir'] == Mote.DIR_TX
    assert motes[6].schedule[8]['neighbor'] == motes[5]

    assert motes[5].schedule[8]['ch'] == 0
    assert motes[5].schedule[8]['dir'] == Mote.DIR_RX
    assert motes[5].schedule[8]['neighbor'] == motes[6]
    assert motes[5].schedule[9]['ch'] == 0
    assert motes[5].schedule[9]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[9]['neighbor'] == motes[4]

    assert motes[4].schedule[9]['ch'] == 0
    assert motes[4].schedule[9]['dir'] == Mote.DIR_RX
    assert motes[4].schedule[9]['neighbor'] == motes[5]
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

    assert motes[5].schedule[14]['ch'] == 0
    assert motes[5].schedule[14]['dir'] == Mote.DIR_TX
    assert motes[5].schedule[14]['neighbor'] == motes[4]

    assert motes[4].schedule[14]['ch'] == 0
    assert motes[4].schedule[14]['dir'] == Mote.DIR_RX
    assert motes[4].schedule[14]['neighbor'] == motes[5]
    assert motes[4].schedule[15]['ch'] == 0
    assert motes[4].schedule[15]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[15]['neighbor'] == motes[3]

    assert motes[3].schedule[15]['ch'] == 0
    assert motes[3].schedule[15]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[15]['neighbor'] == motes[4]
    assert motes[3].schedule[16]['ch'] == 0
    assert motes[3].schedule[16]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[16]['neighbor'] == motes[2]

    assert motes[2].schedule[16]['ch'] == 0
    assert motes[2].schedule[16]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[16]['neighbor'] == motes[3]
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

    assert motes[4].schedule[19]['ch'] == 0
    assert motes[4].schedule[19]['dir'] == Mote.DIR_TX
    assert motes[4].schedule[19]['neighbor'] == motes[3]

    assert motes[3].schedule[19]['ch'] == 0
    assert motes[3].schedule[19]['dir'] == Mote.DIR_RX
    assert motes[3].schedule[19]['neighbor'] == motes[4]
    assert motes[3].schedule[20]['ch'] == 0
    assert motes[3].schedule[20]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[20]['neighbor'] == motes[2]

    assert motes[2].schedule[20]['ch'] == 0
    assert motes[2].schedule[20]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[20]['neighbor'] == motes[3]
    assert motes[2].schedule[21]['ch'] == 0
    assert motes[2].schedule[21]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[21]['neighbor'] == motes[1]

    assert motes[1].schedule[21]['ch'] == 0
    assert motes[1].schedule[21]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[21]['neighbor'] == motes[2]
    assert motes[1].schedule[22]['ch'] == 0
    assert motes[1].schedule[22]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[22]['neighbor'] == motes[0]

    assert motes[0].schedule[22]['ch'] == 0
    assert motes[0].schedule[22]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[22]['neighbor'] == motes[1]

    assert motes[3].schedule[23]['ch'] == 0
    assert motes[3].schedule[23]['dir'] == Mote.DIR_TX
    assert motes[3].schedule[23]['neighbor'] == motes[2]

    assert motes[2].schedule[23]['ch'] == 0
    assert motes[2].schedule[23]['dir'] == Mote.DIR_RX
    assert motes[2].schedule[23]['neighbor'] == motes[3]
    assert motes[2].schedule[24]['ch'] == 0
    assert motes[2].schedule[24]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[24]['neighbor'] == motes[1]

    assert motes[1].schedule[24]['ch'] == 0
    assert motes[1].schedule[24]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[24]['neighbor'] == motes[2]
    assert motes[1].schedule[25]['ch'] == 0
    assert motes[1].schedule[25]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[25]['neighbor'] == motes[0]

    assert motes[0].schedule[25]['ch'] == 0
    assert motes[0].schedule[25]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[25]['neighbor'] == motes[1]

    assert motes[2].schedule[26]['ch'] == 0
    assert motes[2].schedule[26]['dir'] == Mote.DIR_TX
    assert motes[2].schedule[26]['neighbor'] == motes[1]

    assert motes[1].schedule[26]['ch'] == 0
    assert motes[1].schedule[26]['dir'] == Mote.DIR_RX
    assert motes[1].schedule[26]['neighbor'] == motes[2]
    assert motes[1].schedule[27]['ch'] == 0
    assert motes[1].schedule[27]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[27]['neighbor'] == motes[0]

    assert motes[0].schedule[27]['ch'] == 0
    assert motes[0].schedule[27]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[27]['neighbor'] == motes[1]

    assert motes[1].schedule[28]['ch'] == 0
    assert motes[1].schedule[28]['dir'] == Mote.DIR_TX
    assert motes[1].schedule[28]['neighbor'] == motes[0]

    assert motes[0].schedule[28]['ch'] == 0
    assert motes[0].schedule[28]['dir'] == Mote.DIR_RX
    assert motes[0].schedule[28]['neighbor'] == motes[1]

def test_two_branch_symmetric_schedule_installation(sim):
    sim = sim(**{'exec_numMotes':7,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-symmetric'})
    motes = sim.motes

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


def test_two_branch_cascading_schedule_installation_1(sim):
    # un-event tree
    sim = sim(**{'exec_numMotes':7,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-cascading'})
    motes = sim.motes

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


def test_two_branch_cascading_schedule_installation_2(sim):
    # even tree
    sim = sim(**{'exec_numMotes':8,
                 'top_type': 'twoBranch',
                 'sf_type': 'SSF-cascading'})
    motes = sim.motes

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


def test_two_branch_cascading_schedule_installation_4(sim):
    # even tree with random pick
    sim1 = sim(**{'top_type': 'twoBranch',
                  'sf_type': 'SSF-cascading',
                  'ssf_init_method': 'random-pick'})
    motes1 = sim1.motes
    sim1.destroy()

    sim2 = sim(**{'top_type': 'twoBranch',
                  'sf_type': 'SSF-cascading',
                  'ssf_init_method': 'random-pick'})
    motes2 = sim2.motes

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
