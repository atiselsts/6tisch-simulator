"""
\brief fixture returning a SimSettings instance

\author Yasuyuki Tanaka <yasuyuki.tanaka@inria.fr>
"""

import pytest

import SimEngine.SimSettings as SimSettings


@pytest.fixture(scope="function")
def settings(request):

    def create_settings(**kwargs):

        params = {}

        # prerequisite parameters for RandomTopology
        params['fullyMeshed'] = False
        params['squareSide'] = 2.000

        if kwargs:
            params = kwargs

        # make sure there is no settings before creating one
        settings = SimSettings.SimSettings()
        settings.destroy()

        settings = SimSettings.SimSettings(**params)

        def fin():

            settings.destroy()

        request.addfinalizer(fin)
        return settings

    return create_settings
