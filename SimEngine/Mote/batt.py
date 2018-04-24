"""
Battery model.

Keeps track of charge consumed.
"""

# =========================== imports =========================================

# Simulator-wide modules
import SimEngine

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('batt')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Batt(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote
        
        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        
        # local variables
        self.chargeConsumed                 = 0 # charge consumed so far, in uC

    #======================== public ==========================================
    
    def logChargeConsumed(self, charge):
        
        self.chargeConsumed += charge
        
        self.engine.log(
            SimEngine.SimLog.LOG_CHARGE_CONSUMED,
            {"mote_id": self.mote.id, "charge": charge}
        )
    
    #======================== private =========================================