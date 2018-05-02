"""Provides helper functions for tests
"""
import json
import os
import time

import SimEngine

POLLING_INTERVAL = 0.100

ROOT_DIR         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CONFIG_FILE_PATH = os.path.join(ROOT_DIR, 'bin/config.json')

def run_until_asn(sim_engine, target_asn):
    """
    (re)start the simulator, run until some ASN, pause
    """
    
    # arm a pause at the target ASN
    sim_engine.pauseAtAsn(target_asn)

    if sim_engine.is_alive():
        # resume
        sim_engine.play()
    else:
        # start for the first time
        sim_engine.start()
    
    # wait until simulator pauses
    while not sim_engine.simPaused:
        # wait...
        time.sleep(POLLING_INTERVAL)

        # ensure the simulator hasn't crashed
        if sim_engine.exc:
            raise sim_engine.exc
        
        # ensure the simulation hasn't finished
        assert sim_engine.is_alive()

def read_log_file(filter=[]):
    """return contents in a log file as a list of log objects

    You can get only logs which match types specified in "filter"
    argument
    """
    sim_settings = SimEngine.SimSettings.SimSettings()
    logs = []
    with open(sim_settings.getOutputFile(), 'r') as f:
        # discard the first line, that contains configuration
        f.readline()
        for line in f:
            log = json.loads(line)
            if (len(filter) == 0) or (log['_type'] in filter):
                logs.append(log)

    return logs
