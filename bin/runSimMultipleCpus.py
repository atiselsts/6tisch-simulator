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

MIN_TOTAL_RUNRUNS = 16 # poipoi should be 100

def runOneSim(params):
    (cpuID,numRuns) = params
    command     = []
    command    += ['python runSimOneCpu.py']
    command    += ['--otfThreshold 0 10']   # poipoi should be 0,1,2,6,8,10
    command    += ['--pkPeriod 60 1']       # poipoi should be 60.0,10.0,1.0
    command    += ['--numRuns {0}'.format(numRuns)]
    command    += ['--cpuID {0}'.format(cpuID)]
    #command    += ['&']
    command     = ' '.join(command)
    os.system(command)

def printProgress(num_cpus):
    while True:
        time.sleep(1)
        output     = []
        for cpu in range(num_cpus):
            with open('cpu{0}.templog'.format(cpu),'r') as f:
                output += ['[cpu {0}] {1}'.format(cpu,f.read())]
        allDone = True
        for line in output:
            if line.count('ended')==0:
                allDone = False
        output = '\n'.join(output)
        os.system('cls')
        print output
        if allDone:
            break
    for cpu in range(num_cpus):
        os.remove('cpu{0}.templog'.format(cpu))

if __name__ == '__main__':
    multiprocessing.freeze_support()
    num_cpus = multiprocessing.cpu_count()
    runsPerCpu = int(math.ceil(float(MIN_TOTAL_RUNRUNS)/float(num_cpus)))
    pool = multiprocessing.Pool(num_cpus)
    pool.map_async(runOneSim,[(i,runsPerCpu) for i in range(num_cpus)])
    printProgress(num_cpus)
    raw_input("Done. Press Enter to close.")
