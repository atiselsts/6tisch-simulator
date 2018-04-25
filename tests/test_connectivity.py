"""
Tests for SimEngine.Connectivity
"""

def print_matrix(matrix):
    # header
    print "\t",
    for source in matrix:
        print "{0}\t|".format(source),
    print "\n"
    for source in matrix:
        print "{0}\t|".format(source),
        for dest in matrix:
            print "{0}\t|".format(matrix[source][dest][11]['pdr']),
        print "\n"

def test_fill_connectivity_matrix_static_linear(sim):
    """ creates a static connectivity linear path
        0 <-- 1 <-- 2 <-- ... <-- num_motes
    """

    num_motes = 6
    engine = sim(**{'exec_numMotes': num_motes, 'conn_type': 'linear'})
    motes = engine.motes
    matrix = engine.connectivity.connectivity_matrix

    print_matrix(matrix)

    assert motes[0].dagRoot is True

    for i in range(0, num_motes-1):
        src = i
        dst = i+1
        for ch in range(engine.settings.phy_numChans):
            assert matrix[src][dst][ch]['pdr'] == 100
            assert matrix[src][dst][ch]['rssi'] == -10

def test_propagate(sim):
    engine = sim()
    engine.connectivity.propagate()
