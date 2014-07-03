#!/usr/bin/python

'''
 @authors:
       Thomas Watteyne    <watteyne@eecs.berkeley.edu>    
       Xavier Vilajosana  <xvilajosana@uoc.edu> 
                          <xvilajosana@eecs.berkeley.edu>
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
        self.slotDuration    = 0.01 #KM 0.015
        self.numMotes        = None
        self.degree          = None
        self.channels        = None
        self.timeslots       = None
        self.traffic         = None
    