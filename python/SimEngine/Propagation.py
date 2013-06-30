#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Propagation')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import threading

class Propagation(object):
    
    def __init__(self):
        pass
        # store params
        
        
        # variables
        
        # initialize parent class
    
    def propagate(self):
        pass
