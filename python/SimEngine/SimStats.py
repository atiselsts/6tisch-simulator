#!/usr/bin/python
'''
\brief Collects and logs statistics about the ongoing simulation.

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
log = logging.getLogger('SimStats')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import SimEngine
import SimSettings

#============================ defines =========================================

#============================ body ============================================

class SimStats(object):
    
    #===== start singleton
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimStats,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton
    
    def __init__(self,runNum):
        
        #===== start singleton
        if self._init:
            return
        self._init = True
        #===== end singleton
        
        # store params
        self.runNum     = runNum
        
        # local variables
        self.engine     = SimEngine.SimEngine()
        self.settings   = SimSettings.SimSettings()
        
        # start file
        if self.runNum==0:
            self._fileWriteHeader()
        
        # schedule first events
        '''
        self.engine.scheduleAtAsn(
            asn         = 1,
            cb          = self._fileWriteHeader,
            uniqueTag   = (None,'_fileWriteHeader'),
        )
        '''
    
    def destroy(self):
        # destroy my own instance
        self._instance                      = None
        self._init                          = False
    
    #======================== private =========================================
    
    def _fileWriteHeader(self):
        output          = []
        output         += ['## {0} = {1}'.format(k,v) for (k,v) in self.settings.__dict__.items() if not k.startswith('_')]
        output         += ['\n']
        output          = '\n'.join(output)
        
        with open(self.settings.getOutputFile(),'a') as f:
            f.write(output)
