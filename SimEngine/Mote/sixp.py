"""
"""

# =========================== imports =========================================

import random
import threading

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

class ScheduleFullError(Exception):
    pass

# =========================== helpers =========================================

# =========================== body ============================================

class SixP(object):
    
    CELLLIST_LENGTH = 5
    
    def __init__(self, mote):
        
        # store params
        self.mote                 = mote
        
        # singletons (to access quicker than recreate every time)
        self.engine               = SimEngine.SimEngine.SimEngine()
        self.settings             = SimEngine.SimSettings.SimSettings()
        self.log                  = SimEngine.SimLog.SimLog().log

        # local variables
        self.seqnum               = {} # indexed by neighborid

    #======================== public ==========================================

    # from upper layers
    
    def issue_ADD_REQUEST(self, neighborid, cb):
        
        # new 6P command, bump the seqnum
        if neighborid not in self.seqnum:
            self.seqnum[neighborid] = 0
        self.seqnum[neighborid] += 1
        
        # create celllist
        celllist = []
        for _ in range(self.CELLLIST_LENGTH):
            slotOffset = 0
            if len(self.mote.tsch.getSchedule())==self.settings.tsch_slotframeLength:
                raise ScheduleFullError()
            while slotOffset in self.mote.tsch.getSchedule():
                slotOffset = random.randint(1, self.settings.tsch_slotframeLength)
            channelOffset = random.randint(0, self.settings.phy_numChans-1)
            celllist += {
                'slotOffset':    slotOffset,
                'channelOffset': channelOffset,
            }
        
        # create join request
        addRequest = {
            'type':                     d.PKT_TYPE_6P_ADD_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          d.DIR_TX,
                'NumCells':             1,
                'CellList':             celllist,
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               neighborid,
            },
        }
        
        # log
        self.log(
            SimEngine.SimLog.LOG_6P_ADD_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   addRequest
            }
        )
        
        # enqueue
        self.mote.tsch.enqueue(addRequest)

    def issue_DELETE_REQUEST(self, neighborid, numCells, direction, cb):
        raise NotImplementedError()
    
    # from upper layers
    
    def receive(self,packet):
        raise NotImplementedError()