#!/usr/bin/python
'''
\author Thomas Watteyne <watteyne@eecs.berkeley.edu>    
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
'''

#============================ adjust path =====================================

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Postprocessing')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import os
import time
import numpy
import logging.config

from argparse      import ArgumentParser

#============================ defines =========================================

#============================ main ============================================

def parseCliOptions():
    
    parser = ArgumentParser()
    
    parser.add_argument( '--post',
        dest         = 'post',
        action      = 'store_true',
        default     = False, 
        help         = 'Enables post-processing before plotting figures.',
    )
    
    opts           = parser.parse_args()
    
    return opts

def postprocessing(directory):
    for dir in os.listdir(directory):
        subdirectory=os.path.join(directory, dir)
        if os.path.isdir(subdirectory):
            simRuns=0
            matrix=[]
            for filename in os.listdir(subdirectory):
                filenameSplit=filename.split('.')[0].split('_')
                if filenameSplit=='postprocessing' and len(filenameSplit)==3:
                    simRuns+=int(filenameSplit[-1])
                    f=open(filename)
                    lines=f.readlines()
                    f.close()
                    length=len(lines)
                    assert length%2==0
                    matrix+=[[[float(l) for l in line.strip().split('\t')] for line in lines[1:length/2]+lines[length/2+1:]]]
            matrix=numpy.sum(matrix, axis=0)/simRuns

#    f=open(filename)
#    lines=f.readlines()
#    f.close()
#    while lines[0].startswith('#'):
#        lines.pop(0)
#    assert len(lines)==numRuns*cycles
#    matrixResults=numpy.array([[[float(l) for l in lines.pop(0).strip().split('\t')[2:]] for i in xrange(cycles)] for run in xrange(numRuns)])
#    # change matrixResults here for further analysi s 
#    sumValues=numpy.sum(matrixResults, axis=0)
#    sumSquareValues=numpy.sum(matrixResults**2, axis=0)
#    f=open(postprocessingFilename, 'w')
#    f.write('# SUM VALUES\n')
#    for line in sumValues:
#        formatString='\t'.join(['{{{0}:>5}}'.format(i) for i in xrange(len(line))])
#        f.write(formatString.format(*tuple(line))+'\n')
#    f.write('# SUM SQUARE VALUES\n')
#    for line in sumSquareValues:
#        formatString='\t'.join(['{{{0}:>5}}'.format(i) for i in xrange(len(line))])
#        f.write(formatString.format(*tuple(line))+'\n')
#    f.close()
    
def main():
    
    # initialize logging
    logging.config.fileConfig('logging.conf')
    
    directory='results'
    if not os.path.isdir(directory):
        print 'There are no simulation results to analyze.'
    else:
        # parse CLI options
        opts   = parseCliOptions()
        if opts.post:
            postprocessing(directory)
        
#        for numMotes in options.numMotesList:
#            for pkPeriod in options.pkPeriodList:
#                for pkPeriodVar in options.pkPeriodVarList:
#                    for otfThreshold in options.otfThresholdList:
#                        directory = os.path.join('results', \
#                            'numMotes_{0}_pkPeriod_{1}ms_pkPeriodVar_{2}%_otfThreshold_{3}cells'.format(numMotes,int(pkPeriod*1000),int(pkPeriodVar*100),otfThreshold))
#                        if not os.path.exists(directory):
#                            os.makedirs(directory)
#                        idfilename=int(time.time())
#                        filename='//output_{0}.dat'.format(idfilename)
#                        settings = SimSettings.SimSettings(\
#                                    numMotes=numMotes, \
#                                    pkPeriod=pkPeriod, \
#                                    pkPeriodVar=pkPeriodVar, \
#                                    otfThreshold=otfThreshold, \
#                                    outputFile=directory+filename, \
#                                    )
#                        # run the simulation runs
#                        for runNum in xrange(numRuns):
#                            
#                            # logging
#                            print('run {0}, start'.format(runNum))
#                            
#                            # create singletons
#                            propagation     = Propagation.Propagation()
#                            simengine       = SimEngine.SimEngine(runNum) # start simulation
#                            
#                            # wait for simulation to end
#                            simengine.join()
#                            
#                            # destroy singletons
#                            simengine.destroy()
#                            propagation.destroy()
#                            
#                            # logging
#                            print('run {0}, end'.format(runNum))
#                        
#                        postprocessingFilename='//postprocessing_{0}_{1}.dat'.format(idfilename, numRuns)
#                        postprocessing(directory+filename, directory+postprocessingFilename, numRuns, settings.numCyclesPerRun)
#                        settings.destroy()                       # destroy the SimSettings singleton

if __name__=="__main__":
    main()
