#!/usr/bin/python
'''
\brief Entry point to start batch of simulations concurrently.

A number of command-line parameters are available to modify the simulation
settings. Use '--help' for a list of them.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
'''

#============================ adjust path =====================================

import os
import sys
import time
if __name__=='__main__':
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..'))

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('BatchSim')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import argparse
import subprocess

#============================ defines =========================================

#============================ body ============================================

def parseCliOptions():
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument( '--processIDs',
        dest       = 'processIDs',
        nargs      = '+',
        type       = int,
        default    = None,
        help       = 'IDs related to concurrent simulation processes.',
    )
    
    parser.add_argument( '--parameters',
        dest       = 'parameters',
        type       = str,
        default    = '',
        help       = 'Simulation parameters (bound in quotation marks).',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__ 

def main():
    
    # parse CLI options
    options        = parseCliOptions()
    
    processIDs=[]
    if options['processIDs']==None:
        command='python runSim.py {0}'.format(options['parameters'])
        p=subprocess.Popen(command, shell=True)
        processIDs+=[p]
    else:
        for processID in options['processIDs']:
            command='python runSim.py {0}'.format(options['parameters'], processID)
            p=subprocess.Popen(command, shell=True)
            processIDs+=[p]
    while True:
        try:
            time.sleep(100)
        except KeyboardInterrupt:
            for p in processIDs:
                p.kill()
            break
          

#============================ main ============================================

if __name__=="__main__":
    main()
