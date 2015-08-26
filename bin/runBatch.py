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

MIN_TOTAL_RUNRUNS = 8 # poipoi should be 100

def runOneSim(params):
    (cpuID,numRuns) = params
    command     = []
    command    += ['python runSim.py']
    command    += ['--numRuns 20'] # poipoi should be 100
    command    += ['--numRuns {0}'.format(numRuns)]
    command    += ['--cpuID {0}'.format(cpuID)]
    #command    += ['&']
    command     = ' '.join(command)
    os.system(command)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    num_cpus = multiprocessing.cpu_count()
    runsPerCpu = int(math.ceil(float(MIN_TOTAL_RUNRUNS)/float(num_cpus)))
    pool = multiprocessing.Pool(num_cpus)
    pool.map(runOneSim,[(i,runsPerCpu) for i in range(num_cpus)])
