import json

import test_utils as u
from SimEngine.SimConfig import SimConfig


def test_generate_config(sim_engine):
    sim_engine = sim_engine()
    settings = sim_engine.settings

    # prepare expected_config
    with open(u.CONFIG_FILE_PATH, 'r') as f:
        expected_config = json.load(f)

    # adjust 'regular' field:
    # put first values in combination settings to 'regular' field as well as
    # empty the combination field
    if 'combination' in expected_config['settings']:
        comb_keys = expected_config['settings']['combination'].keys()

        while len(comb_keys) > 0:
            key = comb_keys.pop(0)
            value = expected_config['settings']['combination'][key][0]
            assert key  not in expected_config['settings']['regular']
            expected_config['settings']['regular'][key] = value
            del expected_config['settings']['combination'][key]
        expected_config
    # make 'exec_numMotes' a combination setting so that a directory for a log
    # file is properly made. SimSettings needs one combination at least. See
    # SimSettings.getOutputFile()
    expected_config['settings']['combination'] = {
        'exec_numMotes': [
            expected_config['settings']['regular']['exec_numMotes']
        ]
    }
    del expected_config['settings']['regular']['exec_numMotes']

    # adjust 'post' field
    expected_config['post'] = []

    # adjust 'log' related fields
    expected_config['log_directory_name'] = 'startTime'
    expected_config['logging'] = 'all'

    # make sure the 'execution' field is fine
    expected_config['execution']['numCPUs'] == 1
    expected_config['execution']['numRuns'] == 1

    # set a random value
    expected_config['settings']['regular']['exec_randomSeed'] = (
        sim_engine.random_seed
    )

    # ready to test
    config = SimConfig.generate_config(
        settings_dict = settings.__dict__,
        random_seed   = sim_engine.random_seed
    )
    assert config == expected_config
