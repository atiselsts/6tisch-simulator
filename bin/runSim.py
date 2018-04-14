#!/usr/bin/python
"""
\brief Entry point to the simulator. Starts a batch of simulations concurrently.
\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Malisa Vucinic <malishav@gmail.com>
"""

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
log = logging.getLogger('runSim')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import time
import subprocess
import itertools
import logging.config
import threading
import math
import multiprocessing
import argparse

from SimEngine import SimConfig,   \
                      SimEngine,   \
                      SimSettings, \
                      SimStats,    \
                      Topology,    \
                      sf

#============================ helpers =========================================

def parseCliParams():

    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        '--gui',
        dest       = 'gui',
        action     = 'store_true',
        default    = False,
        help       = 'Display the GUI.',
    )
    parser.add_argument(
        '--config',
        dest       = 'config',
        action     = 'store',
        default    = 'config.json',
        help       = 'Location of the configuration file.',
    )
    cliparams      = parser.parse_args()
    return cliparams.__dict__

def printOrLog(cpuID, output, log):
    assert cpuID is not None
    
    if log:
        with open('cpu{0}.templog'.format(cpuID),'w') as f:
            f.write(output)
    else:
        print output

def runSimCombinations(params):
    '''
    Runs simulations for all combinations of simulation settings.
    This function may run independently on different cores.
    '''
    
    cpuID = params['cpuID']
    numRuns = params['numRuns']
    configfile = params['configfile']
    log = params['log']
    
    # sim config (need to re-load, as executing on different cores)
    simconfig = SimConfig.SimConfig(configfile)
    
    # record simulation start time
    simStartTime        = time.time()
    
    # compute all the simulation parameter combinations
    combinationKeys     = simconfig.settings.combination.keys()
    simParams           = []
    for p in itertools.product(*[simconfig.settings.combination[k] for k in combinationKeys]):
        simParam = {}
        for (k,v) in zip(combinationKeys,p):
            simParam[k] = v
        for (k,v) in simconfig.settings.regular.items():
            if k not in simParam:
                simParam[k] = v
        simParams      += [simParam]

    # run a simulation for each set of simParams
    for (simParamNum,simParam) in enumerate(simParams):
        
        # record run start time
        runStartTime = time.time()

        # run the simulation runs
        for runNum in xrange(numRuns):

            # print
            output  = 'parameters {0}/{1}, run {2}/{3}'.format(
               simParamNum+1,
               len(simParams),
               runNum+1,
               numRuns
            )
            printOrLog(cpuID, output, True)

            # create singletons
            settings         = SimSettings.SimSettings(cpuID=cpuID, runNum=runNum, **simParam)
            settings.setStartTime(runStartTime)
            settings.setCombinationKeys(combinationKeys)
            simengine        = SimEngine.SimEngine(cpuID=cpuID, runNum=runNum)
            simstats         = SimStats.SimStats(cpuID=cpuID, runNum=runNum, verbose=(not log))

            # start simulation run
            simengine.start()

            # wait for simulation run to end
            simengine.join()

            # destroy singletons
            simstats.destroy()
            simengine.destroy()
            settings.destroy()

        # print
        output  = 'simulation ended after {0:.0f}s ({1} runs).'.format(
            time.time()-simStartTime,
            numRuns
        )
        printOrLog(cpuID, output, True)

def printProgress(cpuIDs):
    while True:
        time.sleep(1)
        output     = []
        for cpuID in cpuIDs:
            try:
                with open('cpu{0}.templog'.format(cpuID),'r') as f:
                    output += ['[cpu {0}] {1}'.format(cpuID,f.read())]
            except IOError:
                output += ['[cpu {0}] no info (yet?)'.format(cpuID)]
        allDone = True
        for line in output:
            if line.count('ended')==0:
                allDone = False
        output = '\n'.join(output)
        os.system('cls' if os.name == 'nt' else 'clear')
        print output
        if allDone:
            break

#============================ main ============================================

def main():
    # initialize logging
    dir_path = os.path.dirname(os.path.realpath(__file__))
    logging.config.fileConfig(os.path.join(dir_path, 'logging.conf'))
    
    # cli params
    cliparams = parseCliParams()
    
    # sim config
    simconfig = SimConfig.SimConfig(cliparams['config'])
    assert simconfig.version == 0
    
    if cliparams['gui']:
        # with GUI, on a single core
        
        from SimGui import SimGui
        
        # create the GUI, single core
        gui        = SimGui.SimGui()

        # run simulation (in separate thread)
        simThread  = threading.Thread(
            target = runSimCombinations,
            args   = ((0, simconfig.execution.numRuns, simconfig.settings, False),)
        )
        simThread.start()
        
        # start GUI's mainloop (in main thread)
        gui.mainloop()
    
    else:
        # headless, on multiple cores 
        
        #=== run simulations
        
        # decide on number of cores
        multiprocessing.freeze_support()
        max_numCores = multiprocessing.cpu_count()
        if simconfig.execution.numCores == -1:
            numCores = max_numCores
        else:
            numCores = simconfig.execution.numCores
        assert numCores <= max_numCores
        
        if numCores==1:
            # run on single core
            
            runSimCombinations({
                'cpuID':          0,
                'numRuns':        simconfig.execution.numRuns,
                'configfile':     cliparams['config'],
                'log':            False,
            })
            
        else:
            # distribute runs on different cores
            runsPerCore = [int(math.floor(float(simconfig.execution.numRuns)/float(numCores)))]*numCores
            idx         = 0
            while sum(runsPerCore)<simconfig.execution.numRuns:
                runsPerCore[idx] += 1
                idx              += 1
            pool = multiprocessing.Pool(numCores)
            pool.map_async(
                runSimCombinations,
                [
                    {
                        'cpuID':      cpuID,
                        'numRuns':    runs,
                        'configfile': cliparams['config'],
                        'log':        True,
                    } for [cpuID,runs] in enumerate(runsPerCore)
                ]
            )
            
            # print progress, wait until done
            printProgress([i for i in range(numCores)])
            
            # cleanup
            for i in range(numCores):
                os.remove('cpu{0}.templog'.format(i))
        
        #=== post-simulation actions
        
        for c in simconfig.post:
            print 'calling "{0}"'.format(c)
            subprocess.call(c)
        
        raw_input("Done. Press Enter to exit.")
        
if __name__ == '__main__':
    main()
