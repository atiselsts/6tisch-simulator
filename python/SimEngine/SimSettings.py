#!/usr/bin/python
'''
\author Thomas Watteyne <watteyne@eecs.berkeley.edu>    
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
'''

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('SimSettings')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

class SimSettings(object):
    
    #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimSettings,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        self.slotDuration         = 0.010
        self.squareSide           = None
        self.numMotes             = None
        self.numChans             = None
        self.slotframeLength      = None
        self.pkPeriod             = None
        self.pkPeriodVar          = None
        self.otfThreshold         = None
        self.numCyclesPerRun      = None
        self.numRuns              = None