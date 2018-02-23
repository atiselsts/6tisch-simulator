"""
\brief fixture returning a list of Mote instances

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.SimEngine as SimEngine
import SimEngine.SimSettings as SimSettings


@pytest.fixture(scope="function")
def motes(request):

    def create_motes(num_motes, **kwargs):

        # Mote needs SimEngine has already instantiated when its constructor is
        # called
        params = {'numMotes': num_motes, 'topology': 'linear'}
        params['linearTopologyStaticScheduling'] = True

        # there are prerequisite parameters for Mote.Mote()
        params['pkPeriod'] = 0
        params['minRssi'] = 0
        params['withJoin'] = False
        params['slotframeLength'] = 101
        params['slotDuration'] = 0.010
        params['bayesianBroadcast'] = False

        # disable interference model
        params['noInterference'] = True

        # override by kwargs is any specified
        if kwargs:
            params.update(kwargs)

        settings = SimSettings.SimSettings(**params)
        engine = SimEngine.SimEngine()

        def fin():

            engine.destroy()
            settings.destroy()

        request.addfinalizer(fin)

        return engine.motes

    return create_motes
