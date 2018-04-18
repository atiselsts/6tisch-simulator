"""
\brief fixture returning a SimEngine instance

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

from SimEngine import SimSettings, \
                      SimEngine

@pytest.fixture(scope="function")
def sim(request):

    def create_sim(**kwargs):

        params = {
            'exec_numMotes':                15,
            
            'app_pkPeriod':                 0,
            'app_burstNumPackets':          0,
            
            'rpl_dioPeriod':                0,
            'rpl_daoPeriod':                0,
            
            'frag_numFragments':            1,
            'frag_ff_enable':               False,
            'frag_ff_options':              [],
            'frag_ff_vrbtablesize':         50,
            'frag_ph_numReassBuffs':        1,
            
            'sf_type':                      "MSF",
            'sf_msf_housekeepingPeriod':    60,
            'sf_msf_maxNumCells':           16,
            'sf_msf_highUsageThres':        12,
            'sf_msf_lowUsageThres':         4,
            'sf_msf_numCellsToAddRemove':   1,
            'sf_ssf_initMethod':            None,
            
            'secjoin_enabled':              False,
            
            'tsch_slotDuration':            0.010,
            'tsch_slotframeLength':         101,
            'tsch_ebPeriod_sec':            0,
            
            'top_type':                     'random',
            'top_squareSide':               2.000,
            'top_fullyMeshed':              False,
            
            'prop_type':                    'pisterhack',
            
            'phy_noInterference':           True,
            'phy_minRssi':                  -97,
        }

        if kwargs:
            params.update(kwargs)

        settings = SimSettings.SimSettings(**params)
        engine   = SimEngine.SimEngine(1)

        def fin():
            engine.destroy()
            settings.destroy()

        request.addfinalizer(fin)

        return engine

    return create_sim
