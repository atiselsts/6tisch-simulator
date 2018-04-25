import pytest
import time

from SimEngine import SimEngine

@pytest.fixture(scope="function")
def sim(request):

    def create_sim(**kwargs):

        params = {
            'exec_numMotes':                             15,
            'exec_simDataDir':                           "simData",
            "exec_numSlotframesPerRun":                  101,

            'app_pkPeriod':                              0,
            'app_pkLength':                              90,
            'app_burstNumPackets':                       0,

            'rpl_dioPeriod':                             0,
            'rpl_daoPeriod':                             0,

            'fragmentation':                             'FragmentForwarding',
            'fragmentation_ff_vrb_table_size':           50,
            'fragmentation_ff_discard_vrb_entry_policy': [],
            'tsch_max_payload_len':                      90,

            'sf_type':                                   "MSF",
            'sf_msf_housekeepingPeriod':                 60,
            'sf_msf_maxNumCells':                        16,
            'sf_msf_highUsageThres':                     12,
            'sf_msf_lowUsageThres':                      4,
            'sf_msf_numCellsToAddRemove':                1,
            'sf_ssf_initMethod':                         None,

            'secjoin_enabled':                           False,
            "secjoin_numExchanges":                      2,
            "secjoin_joinTimeout":                       60,

            'tsch_slotDuration':                         0.010,
            'tsch_slotframeLength':                      101,
            'tsch_probBcast_ebProb':                     0.33,
            'tsch_probBcast_dioProb':                    0.33,

            'conn_type':                                 'fully_meshed',

            'phy_noInterference':                        True,
            'phy_minRssi':                               -97,
            'phy_numChans':                              16
        }

        if kwargs:
            params.update(kwargs)

        start_time = time.strftime("%Y%m%d-%H%M%S")
        combination_key = []

        settings = SimEngine.SimSettings.SimSettings(**params)
        settings.setStartTime(start_time)
        settings.setCombinationKeys(combination_key)
        engine   = SimEngine.SimEngine(1)

        # start simulation run
        engine.start()

        # wait for simulation run to end
        engine.join()

        def fin():
            engine.destroy()
            settings.destroy()

        request.addfinalizer(fin)

        return engine

    return create_sim