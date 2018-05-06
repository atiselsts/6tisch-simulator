import pytest
import time

from SimEngine import SimConfig,   \
                      SimSettings, \
                      SimLog,      \
                      SimEngine,   \
                      Connectivity
import SimEngine.Mote.MoteDefines as d
import test_utils                 as u

def pdr_not_null(c,p,engine):
    returnVal = False
    for channel in range(engine.settings.phy_numChans):
        if engine.connectivity.get_pdr(c.id,p.id,channel)>0:
            returnVal = True
    return returnVal

@pytest.fixture(params=[1,2,3,4,])
def repeat4times(request):
    return request.param

@pytest.fixture(scope="function")
def sim_engine(request):

    def create_sim_engine(diff_config={}, force_initial_routing_and_scheduling_state=False):
        
        engine = None
        
        # add a finalizer
        def fin():
            if engine:
                engine.connectivity.destroy()
                engine.destroy()
            sim_log.destroy()
            sim_settings.destroy()
        request.addfinalizer(fin)
        
        # get default configuration
        sim_config = SimConfig.SimConfig(u.CONFIG_FILE_PATH)
        config = sim_config.settings['regular']
        assert 'exec_numMotes' not in config
        config['exec_numMotes'] = sim_config.settings['combination']['exec_numMotes'][0]

        # update default configuration with parameters
        for (k,v) in diff_config.items():
            assert k in config
        config.update(**diff_config)

        # create sim settings
        sim_settings = SimSettings.SimSettings(**config)
        sim_settings.setStartTime(
            '{0}-{1:03d}'.format(
                time.strftime('%Y%m%d-%H%M%S'),
                int(round(time.time() * 1000))%1000
            )
        )
        sim_settings.setCombinationKeys([])

        # create sim log
        sim_log = SimEngine.SimLog.SimLog()
        sim_log.set_log_filters('all') # do not log

        # create sim engine
        engine = SimEngine.SimEngine()
        
        # force initial routing and schedule, if appropriate
        if force_initial_routing_and_scheduling_state:
            set_initial_routing_and_scheduling_state(engine)

        return engine

    return create_sim_engine
    

def set_initial_routing_and_scheduling_state(engine):

    # root is mote 0
    root = engine.motes[0]
    root.rpl.setRank(256)
    
    # all nodes are sync'ed, joined and activated
    for m in engine.motes:
        m.tsch.setIsSync(True)         # declare as sync'ed
        m.secjoin.setIsJoined(True)    # declare as joined
        m.activate_tsch_stack()        # activate the TSCH stack
    
    # start scheduling from slot offset 1 upwards
    cur_slot = 1

    # list all motes, indicate state as 'unseen' for all
    state = dict(zip(engine.motes, ['unseen']*len(engine.motes)))

    # start by having the root as 'active' mote
    state[root] = 'active'

    # loop over the motes, until all are 'seen'
    while state.values().count('seen')<len(state):

        # find an active mote, this is the 'parent' in this iteration
        parent = None
        for (k,v) in state.items():
            if v == 'active':
                parent = k
                break
        assert parent

        # for each of its children, set initial routing state and schedule
        for child in state.keys():
            if child == parent:
                continue
            if state[child] != 'unseen':
                continue
            if pdr_not_null(child,parent,engine):
                # there is a non-zero PDR on the child->parent link

                # set child's preferredparent to parent
                child.rpl.setPreferredParent(parent.id)
                # set child's rank
                child.rpl.setRank(parent.rpl.getRank()+512)
                # record the child->parent relationship at the root (for source routing)
                root.rpl.addParentChildfromDAOs(
                    child_id  = child.id,
                    parent_id = parent.id,
                )
                # add a cell from child to parent
                child.tsch.addCell(
                    slotOffset      = cur_slot,
                    channelOffset   = 0,
                    neighbor        = parent.id,
                    cellOptions     = [d.CELLOPTION_TX],
                )
                parent.tsch.addCell(
                    slotOffset      = cur_slot,
                    channelOffset   = 0,
                    neighbor        = child.id,
                    cellOptions     = [d.CELLOPTION_RX],
                )
                cur_slot += 1
                # add a minimal cells (one TX/RX/SHARED cell) to child
                child.tsch.add_minimal_cell()
                # mark child as active
                state[child]  = 'active'



        # mark parent as seen
        state[parent] = 'seen'
