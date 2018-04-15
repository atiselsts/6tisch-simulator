"""
\brief fixture returning a SimEngine instance

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

from SimEngine import SimSettings, SimEngine, Topology, sf

@pytest.fixture(scope="function")
def sim(request):

    def create_sim(**kwargs):

        params = {
            'exec_numMotes':                15,
            
            'app_pkPeriod':                 0,
            
            'rpl_dioPeriod':                0,
            'rpl_daoPeriod':                0,
            
            'frag_numFragments':            1,
            
            'sf_type':                      sf.DFLT_SF,
            'sf_msf_housekeepingPeriod':    60,
            'sf_msf_maxNumCells':           16,
            'sf_msf_highUsageThres':        12,
            'sf_msf_lowUsageThres':         4,
            'sf_msf_numCellsToAddRemove':   1,
            
            'secjoin_enabled':              False,
            
            'tsch_slotDuration':            0.010,
            'tsch_slotframeLength':         101,
            
            'top_type':                     Topology.DEFAULT_TOPOLOGY,
            'top_squareSide':               2.000,
            'top_fullyMeshed':              False,
            
            'prop_type':                    'pisterhack',
            
            'phy_noInterference':           True,
            'phy_minRssi':                  -97,
        }

        if kwargs:
            params.update(kwargs)

        settings = SimSettings.SimSettings(**params)
        engine = SimEngine.SimEngine(1)

        def fin():
            # We check the _init value to make sure the singletons were not already
            # deleted in the test
            if engine._init is True:
                engine.destroy()
            if settings._init is True:
                settings.destroy()

        request.addfinalizer(fin)

        return engine

    return create_sim
