"""This test finds unused setting lines in config.json
"""

import inspect
import os
import re

from SimEngine import SimSettings


def test_config(sim_engine):

    sim_engine = sim_engine()

    # identify the root directory of the simulator
    root_dir = os.path.realpath(
        os.path.join(
            os.path.dirname(__file__),
            '..'
        )
    )

    # identify SimEngine directory
    sim_engine_dir = os.path.join(root_dir, 'SimEngine')

    # collect file paths to the core files
    core_files = []
    for root, dirs, files in os.walk(sim_engine_dir):
        for file in files:
            if file in ['SimSettings.py', 'SimConfig.py']:
                # skip SimSettings.py and SimConfig.py
                continue
            if re.match(r'^.+\.py$', file):
                core_files.append(
                    os.path.join(
                        root,
                        file
                    )
                )

    # collect setting keys in the default config.json; each key is converted
    # from a unicode string ('u' prefixed string) to a normal string
    keys_found_in_config_file = [
        '{0}'.format(key) for key in sim_engine.settings.__dict__.keys()
    ]
    # remove elements which are not configuration keys
    keys_found_in_config_file = [
        key for key in keys_found_in_config_file if (
            key not in [
                'cpuID',
                'run_id',
                'combinationKeys',
                'logRootDirectoryPath',
                'logDirectory'
            ]
        )
    ]
    # convert keys_found_in_config_file to a set
    keys_found_in_config_file = set(keys_found_in_config_file)

    # collect setting keys referred in the core files
    keys_found_in_core_files = set()
    sim_settings_methods = [
        name for name, _ in inspect.getmembers(
            SimSettings.SimSettings(),
            predicate=inspect.ismethod
        )
    ]

    for file_path in core_files:
        # put self.settings as the default setting variable
        settings_variables = set(['self.settings'])
        with open(file_path, 'r') as f:
            for line in f:
                # remote all the white spaces and the new line character
                line = line.rstrip()
                if   re.match(r'^import', line):
                    # skip import line
                    continue
                elif re.match(r'^\s*#', line):
                    # skip comment line
                    continue
                elif re.search(r'SimSettings', line):
                    if (
                            re.search(r'SimSettings\(\)\.__dict__', line)
                            and
                            re.search(r' for ', line)
                        ):
                        # this line looks like a 'for' statement; skip this line
                        continue
                    settings_variable = re.sub(r'^(.+)=.+SimSettings.+$', r'\1', line)
                    settings_variable = settings_variable.replace(' ', '')
                    settings_variables.add(settings_variable)
                elif (
                        (len(settings_variables) > 0)
                        and
                        re.search('|'.join(settings_variables), line)
                    ):
                    # identify a setting key in in this line
                    pattern = re.compile(
                        '(' + '|'.join(settings_variables) + ')' +
                        '\.(\w+)'
                    )
                    m = re.search(pattern, line)
                    key = m.group(2)
                    if   key in sim_settings_methods:
                        # it's class/instance method; skip it
                        continue
                    elif key == '__dict__':
                        # this is not a key; skip it
                        continue
                    else:
                        # add the key referred from a core file
                        keys_found_in_core_files.add(m.group(2))

    # ready to test; two sets should be identical
    assert keys_found_in_config_file == keys_found_in_core_files
