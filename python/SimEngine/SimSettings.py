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

import os

#============================ defines =========================================

#============================ body ============================================

class SimSettings(object):
    
    #======================== singleton pattern ===============================
    
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimSettings,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self,**kwargs):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        self.__dict__.update(kwargs)
    
    def setStartTime(self,startTime):
        self.startTime       = startTime
    
    def setCombinationKeys(self,combinationKeys):
        self.combinationKeys = combinationKeys
    
    def getOutputFile(self):
        # directory
        dirname   = os.path.join(
            'simData',
            '_'.join(['{0}_{1}'.format(k,getattr(self,k)) for k in self.combinationKeys]),
        )
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        
        # file
        datafilename         = os.path.join(
            dirname,
            'output_{0}_{1}.dat'.format(int(self.startTime), os.getpid()),
        )
        
        return datafilename
    
    def destroy(self):
        self._instance       = None
        self._init           = False
