"""Provides helper functions for tests
"""
import json
import os
import time
import types

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

    # flush the internal log buffer so that test code can see data in the log
    # files.
    SimEngine.SimLog.SimLog().flush()

def run_until_end(sim_engine):
    """
    (re)start the simulator, run until the simulation ends
    """
    slotframe_length = sim_engine.settings.tsch_slotframeLength
    num_slotframes   = sim_engine.settings.exec_numSlotframesPerRun
    asn_at_end       = slotframe_length * num_slotframes
    run_until_asn(sim_engine, asn_at_end)

def run_until_everyone_joined(sim_engine):
    """
    (re)start the simulator, run until every mote gets joined
    """

    # this list is shared among all the motes; collect all the motes who have
    # already joined
    joined_node_set = set(
        [
            mote for mote in sim_engine.motes if mote.secjoin.getIsJoined()
        ]
    )

    def new_setIsJoined(self, newState):
        self.original_setIsJoined(newState)
        # update joined_node_set
        if newState is True:
            joined_node_set.add(self.mote.id)
        elif self.mote_id in joined_node_set:
            joined_node_set.remove(self.mote_id)
        else:
            # newState == False and self.mote_id not in joined_node_set
            # do nothing
            pass

        # stop the simulator if it's time to do
        if len(joined_node_set) == len(sim_engine.motes):
            sim_engine.pauseAtAsn(sim_engine.getAsn() + 1)

    # install new_setIsJoined to the motes
    for mote in sim_engine.motes:
        mote.secjoin.original_setIsJoined = mote.secjoin.setIsJoined
        mote.secjoin.setIsJoined = types.MethodType(
            new_setIsJoined,
            mote.secjoin
        )

    # run until the simulator is paused
    run_until_end(sim_engine)

def read_log_file(filter=[], after_asn=0):
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
            if (log["_asn"] >= after_asn) and ((len(filter) == 0) or (log['_type'] in filter)):
                logs.append(log)

    return logs
