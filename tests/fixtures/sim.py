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
            # prerequisite parameters for SimEngine
            'numMotes': 15,
            'withJoin': False,

            # prerequisite parameters for Topology
            'top_fullyMeshed': False,
            'top_squareSide': 2.000,
            'top_type': Topology.DEFAULT_TOPOLOGY,

            # prerequisite parameters for Schedule
            'scheduling_function': sf.DEFAULT_SCHEDULING_FUNCTION,
            'msfHousekeepingPeriod': 60,
            'msfMaxNumCells': 16,
            'msfLimNumCellsUsedHigh': 12,
            'msfLimNumCellsUsedLow': 4,
            'msfNumCellsToAddOrRemove': 1,

            # prerequisite parameters for Propagation
            'prop_type': 'pisterhack',
            'slotDuration': 0.010,
            'slotframeLength': 101,
            'noInterference': True,
            'minRssi': -97,

            # there are prerequisite parameters for Mote
            'pkPeriod': 0,
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
