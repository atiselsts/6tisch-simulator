import sys
import pytest
from bin import runSim, plot

# ============================ parameters =====================================

SIM_PARAMETERS = [
    ['--numMote', '5', '--simDataDir', 'bin/simData']
]
PLOT_PARAMETERS = [
    ["-x", "cycle", '--inputfolder', 'bin/simData']
]

# ============================= fixtures ======================================

@pytest.fixture(params=SIM_PARAMETERS)
def sim_params(request):
    return request

@pytest.fixture(params=PLOT_PARAMETERS)
def plot_params(request):
    return request

# ============================== tests ========================================

def test_runSim(sim_params):
    sys.argv = [sys.argv[0]] + sim_params.param
    runSim.main()

def test_run_plot(plot_params):
    sys.argv = [sys.argv[0]] + plot_params.param
    options = plot.parse_args()
    plot.main(options)
