
# =========================== imports =========================================

import sys
import random
from abc import abstractmethod

import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SchedulingFunction(object):
    
    def __init__(self, mote):
        
        # store params
        self.mote            = mote
        
        # singletons (to access quicker than recreate every time)
        self.settings        = SimEngine.SimSettings.SimSettings()
        self.engine          = SimEngine.SimEngine.SimEngine()
        self.log             = SimEngine.SimLog.SimLog().log
        
        # local variables
    
    # === factory
    
    @classmethod
    def get_sf(cls, mote):
        settings = SimEngine.SimSettings.SimSettings()
        return getattr(sys.modules[__name__], settings.sf_type)(mote)
    
    # ======================= public ==========================================
    
    # === admin
    
    @abstractmethod
    def activate(self):
        '''
        tells SF when should start working
        '''
        raise NotImplementedError()
    
    # === indications from other layers
    
    @abstractmethod
    def indication_neighbor_added(self,neighbor_id):
        '''
        [from TSCH] just added a neighbor.
        '''
        raise NotImplementedError()
    
    @abstractmethod
    def indication_neighbor_deleted(self,neighbor_id):
        '''
        [from TSCH] just deleted a neighbor.
        '''
        raise NotImplementedError()
    
    @abstractmethod
    def indication_tx_cell_elapsed(self,cell,used):
        '''
        [from TSCH] just passed a dedicated TX cell. used=False means we didn't use it.
        '''
        raise NotImplementedError()
    
    @abstractmethod
    def indication_parent_change(self):
        '''
        [from RPL] decided to change parents.
        '''
        raise NotImplementedError()

class SFNone(SchedulingFunction):
    
    def __init__(self, mote):
        super(SFNone, self).__init__(mote)
    
    def activate(self):
        pass # do nothing
    
    def indication_neighbor_added(self,neighbor_id):
        pass # do nothing
    
    def indication_neighbor_deleted(self,neighbor_id):
        pass # do nothing
    
    def indication_tx_cell_elapsed(self,cell,used):
        pass # do nothing

    def indication_parent_change(self):
        pass # do nothing

class MSF(SchedulingFunction):

    def __init__(self, mote):
        # intialize parent class
        super(MSF, self).__init__(mote)
        
        # (additional) local variables
    
    # ======================= public ==========================================
    
    # === admin
    
    def activate(self):
        raise NotImplementedError() # TODO
    
    # === indications from other layers
    
    def indication_neighbor_added(self,neighbor_id):
        raise NotImplementedError() # TODO
    
    def indication_neighbor_deleted(self,neighbor_id):
        raise NotImplementedError() # TODO
    
    def indication_tx_cell_elapsed(self,cell,used):
        raise NotImplementedError() # TODO

    def indication_parent_change(self):
        raise NotImplementedError() # TODO
