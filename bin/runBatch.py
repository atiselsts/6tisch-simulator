#!/usr/bin/python
'''
\brief Start batch of simulations concurrently.
Workload is distributed equally among CPU cores.
\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
'''

import os
import time
import math
import multiprocessing

MIN_TOTAL_RUNRUNS = 100

def runOneSimulation(params):
    (processID,numRuns) = params
    command     = []
    command    += ['python runSim.py']
    command    += ['--numRuns {0}'.format(numRuns)]
    command    += ['--processID {0}'.format(processID)]
    #command    += ['&']
    command     = ' '.join(command)
    os.system(command)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    num_cpus = multiprocessing.cpu_count()
    runsPerCpu = int(math.ceil(float(MIN_TOTAL_RUNRUNS)/float(num_cpus)))
    pool = multiprocessing.Pool(num_cpus)
    pool.map_async(runOneSimulation,[(i,runsPerCpu) for i in range(num_cpus)])
    while True:
        try:
            print 'poipoi'
            time.sleep(100)
        except KeyboardInterrupt:
            print 'interrupt'
            pool.terminate()
            break
