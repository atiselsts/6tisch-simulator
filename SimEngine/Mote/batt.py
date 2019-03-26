"""
Battery model.

Keeps track of charge consumed.
"""

# =========================== imports =========================================

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Batt(object):

    def __init__(self, mote):

        # store params
        self.mote            = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine          = SimEngine.SimEngine.SimEngine()
        self.settings        = SimEngine.SimSettings.SimSettings()
        self.log             = SimEngine.SimLog.SimLog().log

        # local variables
        self.chargeConsumed  = 0 # charge consumed so far, in uC

        if self.settings.charge_log_period_s > 0:
            # schedule the event only when charge_log_period_s is
            # larger than zero
            self._schedule_log_charge()

    #======================== public ==========================================

    def logChargeConsumed(self, charge):

        self.chargeConsumed += charge

    #======================== private =========================================

    def _schedule_log_charge(self):
        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn() + int(float(self.settings.charge_log_period_s)/self.settings.tsch_slotDuration),
            cb               = self._action_log_charge,
            uniqueTag        = (self.mote.id, '_action_log_charge'),
            intraSlotOrder   = d.INTRASLOTORDER_ADMINTASKS,
        )

    def _action_log_charge(self):

        # log
        self.log(
            SimEngine.SimLog.LOG_BATT_CHARGE,
            {
                "_mote_id":   self.mote.id,
                "charge":     self.chargeConsumed,
            }
        )

        # schedule next
        self._schedule_log_charge()
