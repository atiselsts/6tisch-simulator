#!/usr/bin/python
'''
\author Thomas Watteyne <watteyne@eecs.berkeley.edu>    
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
'''

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('SimSettings')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

#============================ defines =========================================

SQUARESIDE              = 1.000
NUMMOTES                = 10
NUMCHANS                = 16
SLOTDURATION            = 0.010
SLOTFRAMELENGTH         = 101
PKPERIOD                = 0.100
PKPERIODVAR             = 0.1
OTFTHRESHOLD            = 0
NUMCYCLESPERRUN         = 10
OUTPUTFILE              = 'output.dat'

#============================ body ============================================

class SimSettings(object):
    
    #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimSettings,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self, \
                squareSide = SQUARESIDE, \
                numMotes = NUMMOTES, \
                numChans = NUMCHANS, \
                slotDuration = SLOTDURATION, \
                slotframeLength = SLOTFRAMELENGTH, \
                pkPeriod = PKPERIOD, \
                pkPeriodVar = PKPERIODVAR, \
                otfThreshold = OTFTHRESHOLD, \
                numCyclesPerRun = NUMCYCLESPERRUN, \
                outputFile = OUTPUTFILE
                ):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        self.squareSide             = squareSide
        self.numMotes               = numMotes
        self.numChans               = numChans
        self.slotDuration           = slotDuration
        self.slotframeLength        = slotframeLength
        self.pkPeriod               = pkPeriod
        self.pkPeriodVar            = pkPeriodVar
        self.otfThreshold           = otfThreshold
        self.numCyclesPerRun        = numCyclesPerRun
        self.outputFile             = outputFile
    
    def destroy(self):
        self._instance       = None
        self._init           = False
