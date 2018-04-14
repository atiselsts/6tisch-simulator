import sys
import pytest
import os
#from bin import runSim, plot
import subprocess

# ============================ parameters =====================================

SIM_PARAMETERS = [
    ['--config', 'bin/config.json']
]
PLOT_PARAMETERS = [
    []
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
    wd = os.getcwd()
    os.chdir("bin/")
    rc = subprocess.call("python runSim.py")
    os.chdir(wd)
    assert rc==100

def test_run_plot(plot_params):
    sys.argv = [sys.argv[0]] + plot_params.param
    options = plot.parse_args()
    plot.main(options)
