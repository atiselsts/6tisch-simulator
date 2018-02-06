"""
\brief fixture returning a SimEngine instance

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.SimEngine as SimEngine
import SimEngine.SimSettings as SimSettings


@pytest.fixture(scope="function")
def sim(request):

    def create_sim(**kwargs):

        params = {}

        # mandatory parameters to create a SimEngine instance
        params['pkPeriod'] = 0
        params['minRssi'] = 0
        params['withJoin'] = False
        params['slotframeLength'] = 101
        params['slotDuration'] = 0.010
        params['bayesianBroadcast'] = False
        params['numCyclesPerRun'] = 101

        # disable interference model
        params['noInterference'] = True

        if kwargs:
            params.update(kwargs)

        settings = SimSettings.SimSettings(**params)
        engine = SimEngine.SimEngine(1)

        def fin():

            engine.destroy()
            settings.destroy()

        request.addfinalizer(fin)

        return engine

    return create_sim
