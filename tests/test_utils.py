"""Provides helper methods for tests
"""

import time


POLLING_INTERVAL = 0.100


def run_until_at_asn(sim_engine, target_asn):
    sim_engine.pauseAtAsn(target_asn)

    if sim_engine.is_alive():
        sim_engine.play() # resume
    else:
        # state of sim_engine becomes Alive after calling start()
        sim_engine.start()

    # wait for sim_engine to get paused
    while not sim_engine.simPaused:
        time.sleep(POLLING_INTERVAL)
