#!/usr/bin/python

'''
 @authors:
       Thomas Watteyne    <watteyne@eecs.berkeley.edu>    
       Xavier Vilajosana  <xvilajosana@uoc.edu> 
                          <xvilajosana@eecs.berkeley.edu>
'''

import os
import sys
if __name__=='__main__':
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', '..'))

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('SimpleSim')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import logging.config

from optparse      import OptionParser

from SimEngine     import SimEngine, \
                          SimSettings
from SimGui        import SimGui

#============================ defines =========================================

#============================ main ============================================

def parseCliOptions():
    
    parser = OptionParser()
    
    parser.add_option( '--nm',
        dest       = 'numMotes',
        type       = 'int',
        default    = 10,
    )
    
    parser.add_option( '-d',
        dest       = 'degree',
        type       = 'int',
        default    = 5,
    )
    
    parser.add_option( '-c',
        dest       = 'channels',
        type       = 'int',
        default    = 16,
    )
    
    parser.add_option( '--ts',
        dest       = 'timeslots',
        type       = 'int',
        default    = 101,
    )
    
    parser.add_option( '--traffic',
        dest       = 'traffic',
        type       = 'int',
        default    = 0.5,
    )
    
    parser.add_option( '--op',
        dest       = 'overprovisioning',
        type       = 'float',
        default    = 1.0,
    )
    
    (opts, args)  = parser.parse_args()
    
    return opts.__dict__

def main():

    maxRunNum = 2
    
    logging.config.fileConfig('logging.conf')
    
    # retrieve the command line args
    args      = parseCliOptions()
    
    # instantiate a SimSettings
    settings  = SimSettings.SimSettings()
    for (k,v) in args.items():
        setattr(settings,k,v)
    
    for runNum in range(maxRunNum):
        # instantiate a SimEngine object
        print('start run num: {0}'.format(runNum))
        SimEngine.SimEngine.setCount()
        simengine = SimEngine.SimEngine()
        simengine.join()
        simengine._instance      = None
        simengine._init          = False
        print('end run num: {0}'.format(runNum))    
    # instantiate the GUI interface
    #gui       = SimGui.SimGui()

if __name__=="__main__":
    main()
