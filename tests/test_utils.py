"""Provides helper functions for tests
"""

import time

POLLING_INTERVAL = 0.100

def run_until_asn(sim_engine, target_asn):
    '''
    (re)start the simulator, run until some ASN, pause
    '''
    
    # arm a pause at the target ASN
    sim_engine.pauseAtAsn(target_asn)

    if sim_engine.is_alive():
        # resume
        sim_engine.play()
    else:
        # start for the first time
        sim_engine.start()

    # wait until simulator paused
    while not sim_engine.simPaused:
        time.sleep(POLLING_INTERVAL)
