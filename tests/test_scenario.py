import pytest

import test_utils as u
from SimEngine import SimConfig

#============================ fixtures ========================================

@pytest.fixture(params=['up', 'down', 'up-down'])
def fixture_data_flow(request):
    return request.param

@pytest.fixture(params=[10, 100, 1000])
def fixture_app_pkLength(request):
    return request.param

@pytest.fixture(params=["PerHopReassembly","FragmentForwarding"])
def fixture_fragmentation(request):
    return request.param

@pytest.fixture(params=[True,False])
def fixture_ff_vrb_policy_missing_fragment(request):
    return request.param

@pytest.fixture(params=[True,False])
def fixture_ff_vrb_policy_last_fragment(request):
    return request.param

#============================ helpers =========================================

#============================ tests ===========================================

def test_vanilla_scenario(
        sim_engine,
        fixture_data_flow,
        fixture_app_pkLength,
        fixture_fragmentation,
        fixture_ff_vrb_policy_missing_fragment,
        fixture_ff_vrb_policy_last_fragment
    ):
    '''
    Let the network form, send data packets up and down.
    '''
    
    # initialize the simulator
    fragmentation_ff_discard_vrb_entry_policy = []
    if fixture_ff_vrb_policy_missing_fragment:
        fragmentation_ff_discard_vrb_entry_policy += ['missing_fragment']
    if fixture_ff_vrb_policy_last_fragment:
        fragmentation_ff_discard_vrb_entry_policy += ['last_fragment']
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes':                               5,
            'app_pkLength' :                               fixture_app_pkLength,
            'fragmentation':                               fixture_fragmentation,
            'fragmentation_ff_discard_vrb_entry_policy':   fragmentation_ff_discard_vrb_entry_policy,
        },
    )
    
    # give the network time to form
    raise NotImplementedError()
    
    # verify the network has formed
    raise NotImplementedError() # RPL: preferred parents
    raise NotImplementedError() # RPL: rank
    raise NotImplementedError() # tsch: dedicated cells
    
    # pick a "datamote" which will send/receive data
    raise NotImplementedError()
    
    # send data upstream (datamote->root)
    if data_flows.find("up"):
        # inject data at the datamote
        raise NotImplementedError()
        
        # give the data time to reach the root
        raise NotImplementedError()
        
        # verify it got to the root
        raise NotImplementedError()
    
    # send data downstream (root->datamote)
    if data_flows.find("down"):
        # inject data at the root
        raise NotImplementedError()
        
        # give the data time to reach the datamote
        raise NotImplementedError()
        
        # verify it got to the datamote
        raise NotImplementedError()
