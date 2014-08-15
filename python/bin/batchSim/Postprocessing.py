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
import scipy.stats as ss
import math
import logging.config
import matplotlib
import matplotlib.cm as cm
import matplotlib.pyplot as plt

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
                if filenameSplit[0]=='postprocessing':
                   if len(filenameSplit)==4:
                        simRuns+=int(filenameSplit[-1])
                        f=open(subdirectory+'//'+filename)
                        lines=f.readlines()
                        f.close()
                        length=len(lines)
                        assert length%2==0
                        matrix+=[[[float(l) for l in line.strip().split('\t')] for line in lines[1:length/2]+lines[length/2+1:]]]
                   else:
                       os.remove(subdirectory+'//'+filename)
            if simRuns>0:
                matrix=numpy.array(matrix)/simRuns
                matrix=numpy.sum(matrix, axis=0)
                outputFile=subdirectory+'//postprocessing_{0}.dat'.format(simRuns)
                f=open(outputFile, 'w')
                f.write('# SUM VALUES\n')
                for line in matrix[:len(matrix)/2, :]:
                    formatString='\t'.join(['{{{0}}}'.format(i) for i in xrange(len(line))])
                    f.write(formatString.format(*tuple(line))+'\n')
                f.write('# SUM SQUARE VALUES\n')
                for line in matrix[len(matrix)/2:, :]:
                    formatString='\t'.join(['{{{0}}}'.format(i) for i in xrange(len(line))])
                    f.write(formatString.format(*tuple(line))+'\n')
                f.close()

def readDataForFigures(directory, columns=None):
    figures='figures'
    data={}
    control=None
    for dir in os.listdir(directory):
        subdirectory=os.path.join(directory, dir)
        identifier=tuple(dir.split('_')[1::2])
        data[identifier]={}
        if os.path.isdir(subdirectory):
            for filename in os.listdir(subdirectory):
                filenameSplit=filename.split('.')[0].split('_')
                if filenameSplit[0]=='postprocessing' and len(filenameSplit)==2:
                    simRuns=int(filenameSplit[-1])
                    f=open(subdirectory+'//'+filename)
                    lines=f.readlines()
                    f.close()
                    print subdirectory+'//'+filename
                    length=len(lines)
                    assert length%2==0
                    matrixAvg=[[float(l) for l in line.strip().split('\t')] for line in lines[1:length/2]]
                    matrixSqAvg=[[float(l) for l in line.strip().split('\t')] for line in lines[length/2+1:]]
                    matrixAvg=zip(*matrixAvg)
                    matrixSqAvg=zip(*matrixSqAvg)
                    if control==None:
                        control=len(matrixAvg)
                    else:
                        assert len(matrixAvg)==control
                    confidence=ss.t.interval(0.95, simRuns)[1]
                    for stat in xrange(len(matrixAvg)):
                        avg=numpy.array(matrixAvg[stat])
                        sqAvg=numpy.array(matrixSqAvg[stat])
                        err=numpy.sqrt((sqAvg-avg**2)/(simRuns-1))*confidence
                        data[identifier][stat]=[avg, err]
    if not os.path.exists(figures):
        os.makedirs(figures)
    if columns is None:
        columns=range(control)
    for column in columns:
        toplot=dict([(identifier, data[identifier][column]) for identifier in data.iterkeys()])
        plotFigure(toplot, figures, column)
    
def plotFigure(toplot, figures, column):
    plt.figure()
    plt.hold(True)
    colors = cm.rainbow(numpy.linspace(0, 1, len(toplot)))
    for en, i in enumerate(sorted(toplot.keys())):
        plt.errorbar(range(len(toplot[i][0])), toplot[i][0], yerr=toplot[i][1], label=' '.join(i), color=colors[en])
    plt.grid()
    plt.legend(loc=2, prop=matplotlib.font_manager.FontProperties(family='monospace', style='oblique', size='small'), labelspacing=0.0)
    plt.savefig('{0}/column_{1}.png'.format(figures, column))
    plt.close()
    
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
        readDataForFigures(directory, columns=None) #indicate the number related to each column you want to plot (column of the postprocessing files)

if __name__=="__main__":
    main()
