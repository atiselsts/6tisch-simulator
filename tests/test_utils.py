"""Provides helper functions for tests
"""
import os
import time

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

    # wait until simulator pauses or simulator dies
    while not (sim_engine.simPaused or sim_engine.is_alive()):
        time.sleep(POLLING_INTERVAL)
