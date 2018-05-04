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

# =========================== helpers =========================================

# =========================== body ============================================

class SixP(object):

    def __init__(self, mote):

        pass

    #======================== public ==========================================

    # from upper layers
    
    def send_ADD_REQUEST(self, neighborid, numCells, direction, cb):
        raise NotImplementedError()

    def send_ADD_REQUEST(self, neighborid, numCells, direction, cb):
        raise NotImplementedError()
    
    # from upper layers
    
    def receive(self,packet):
        raise NotImplementedError()