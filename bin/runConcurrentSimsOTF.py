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
import multiprocessing

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
    
    parser.add_argument( '--numRuns',
        dest       = 'numRuns',
        type       = int,
        default    = 2,
        help       = 'Number of simulation runs per each configurations.',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__
    
def main():
    
    # parse CLI options
    options        = parseCliOptions()
    
    if options['processIDs']==None:
        command='python runSim.py --numMotes 50 --squareSide 2.0 --pkPeriod 60 10 1 --otfThreshold 0 2 4 6 8 10 --numCyclesPerRun 100 --numRuns {0} --simDataDir simDataOTF'.format(options['numRuns'])
        os.system(command)
    else:
        for processID in options['processIDs']:
            command='python runSim.py --numMotes 50 --squareSide 2.0 --pkPeriod 60 10 1 --otfThreshold 0 2 4 6 8 10 --numCyclesPerRun 100 --numRuns {0} --processID {1} --simDataDir simDataOTF &'.format(options['numRuns'], processID)
            multiprocessing.Process(target=os.system(command)).start()

#============================ main ============================================

if __name__=="__main__":
    main()
