"""
Battery model.

Keeps track of charge consumed.
"""

# =========================== imports =========================================

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Batt(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self.chargeConsumed                 = 0 # charge consumed so far, in uC

    #======================== public ==========================================

    def logChargeConsumed(self, charge):

        self.chargeConsumed += charge

    #======================== private =========================================