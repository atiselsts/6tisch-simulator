#!/usr/bin/python
'''
\brief Plots timelines and topology figures from collected simulation data.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
'''

#============================ adjust path =====================================

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('plotTimelines')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import os
import re
import glob
import sys
import math

import numpy
import scipy
import scipy.stats

import logging.config
import matplotlib.pyplot
import argparse
import itertools

#============================ defines =========================================

DATADIR = 'simDataOTF'
CONFINT = 0.95

#============================ body ============================================

def parseCliOptions():
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument( '--elemNames',
        dest       = 'elemNames',
        nargs      = '+',
        type       = str,
        default    = [
#            'numTxCells', 'aveQueueDelay', 'OTFevent', 
            'PacketLoss'
        ],
        help       = 'Name of the elements to generate timeline figures for.',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__

def parseFiles(infilepaths,elemName):
    valuesPerCycle = {}
    for infilepath in infilepaths:
        
        # print
        print 'Parsing    {0}...'.format(infilepath),
        
        # find colnumelem, colnumcycle, colnumrunNum
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('# '):
                    elems        = re.sub(' +',' ',line[2:]).split()
                    numcols      = len(elems)
                    colnumelem   = elems.index(elemName)
                    colnumcycle  = elems.index('cycle')
                    colnumrunNum = elems.index('runNum')
                    break
        
        assert colnumelem
        assert colnumcycle
        assert colnumrunNum
        
        # parse data
        
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                m = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
                cycle  = int(m.group(colnumcycle+1))
                runNum = int(m.group(colnumrunNum+1))
                try:
                    elem         = float(m.group(colnumelem+1))
                except:
                    try:
                        elem     =   int(m.group(colnumelem+1))
                    except:
                        elem     =       m.group(colnumelem+1)
                #print 'cycle={0} runNum={1} elem={2}'.format(cycle,runNum,elem)
                if cycle not in valuesPerCycle:
                    valuesPerCycle[cycle] = []
                valuesPerCycle[cycle] += [elem]
        
        # print
        print 'done.'
    assert len(set([len(value) for value in valuesPerCycle.values()]))==1
    return valuesPerCycle

def genTimelineAvgs(infilepaths,elemName):
    if elemName=='OTFevent':
        otfAdd=parseFiles(infilepaths,'otfAdd')
        otfRemove=parseFiles(infilepaths,'otfRemove')
        valuesPerCycle={}
        for key in otfAdd.iterkeys():
            valuesPerCycle[key]=list(numpy.array(otfAdd[key]) + numpy.array(otfRemove[key]))
    elif elemName=='PacketLoss':
        appGenerated=parseFiles(infilepaths,'appGenerated')
        appReachesDagroot=parseFiles(infilepaths,'appReachesDagroot')
        txQueueFill=parseFiles(infilepaths,'txQueueFill')
        
        genCum=numpy.cumsum([appGenerated[key] for key in sorted(appGenerated.keys())], axis=0)
        reaCum=numpy.cumsum([appReachesDagroot[key] for key in sorted(appReachesDagroot.keys())], axis=0)
        txQueue=numpy.array([txQueueFill[key] for key in sorted(txQueueFill.keys())])
        
        toPutInDict=1-reaCum/(genCum-txQueue)
        valuesPerCycle=dict([(key, toPutInDict[key]) for key in sorted(appGenerated.keys())])
    else:
        valuesPerCycle=parseFiles(infilepaths,elemName)

    # calculate mean and confidence interval
    meanPerCycle    = {}
    confintPerCycle = {}
    for (k,v) in valuesPerCycle.items():
        a          = 1.0*numpy.array(v)
        n          = len(a)
        se         = scipy.stats.sem(a)
        m          = numpy.mean(a)
        confint    = se * scipy.stats.t._ppf((1+CONFINT)/2., n-1)
        meanPerCycle[k]      = m
        confintPerCycle[k]   = confint
    
    x         = sorted(meanPerCycle.keys())
    y         = [meanPerCycle[k] for k in x]
    yerr      = [confintPerCycle[k] for k in x]
    
    return [x, y, yerr]

def genPlotsOTF(keys, params, dictionary, dir, elemName):
    assert 'otfThreshold' in keys
    assert 'pkPeriod' in keys
    
    figureKeys=set(keys)-set(['otfThreshold', 'pkPeriod'])
    toBeTuple=keys[:]
    col=['r', 'g', 'b', 'm', 'c', 'y']
    mark=['o', '>', 'd']

    for p in itertools.product(*[params[k] for k in figureKeys]):
        outfilenameList=[]
        for (k,v) in zip(figureKeys,p):
            outfilenameList+=['{0}_{1}'.format(k, v)]
            toBeTuple[keys.index(k)]=v
        
        outfilename='_'.join(outfilenameList)+'_timeline_{}.png'.format(elemName)
        outfilepath    = os.path.join(dir,outfilename)
        
        # print
        print 'Generating {0}...'.format(outfilename),
        
        # plot
        matplotlib.pyplot.figure()
        matplotlib.pyplot.hold(True)
        otfThresholdList=sorted(params['otfThreshold'])
        pkPeriodList=sorted(params['pkPeriod'])
        for otfThreshold in otfThresholdList[0::2]:
            toBeTuple[keys.index('otfThreshold')]=otfThreshold
            for pkPeriod in pkPeriodList:
                toBeTuple[keys.index('pkPeriod')]=pkPeriod
                toPlot=dictionary[tuple(toBeTuple)]
                matplotlib.pyplot.errorbar(
                                            toPlot[0],toPlot[1],yerr=toPlot[2], color=col[otfThresholdList.index(otfThreshold)], marker=mark[pkPeriodList.index(pkPeriod)], \
                                            label='otfThresh={0}, pkPeriod={1}'.format(otfThreshold, pkPeriod)
                                            )
        matplotlib.pyplot.legend(loc=0, prop=matplotlib.font_manager.FontProperties(family='monospace', style='oblique', size='xx-small'), labelspacing=0.0)
        matplotlib.pyplot.hold(False)
        matplotlib.pyplot.savefig(outfilepath)
        matplotlib.pyplot.close('all')
        
        # print
        print 'done.'
        
        outfilename='_'.join(outfilenameList)+'_{}.png'.format(elemName)
        outfilepath    = os.path.join(dir,outfilename)
        
        # print
        print 'Generating {0}...'.format(outfilename),
        
        # plot
        matplotlib.pyplot.figure()
        matplotlib.pyplot.hold(True)
        otfThresholdList=sorted(params['otfThreshold'])
        pkPeriodList=sorted(params['pkPeriod'])
        for pkPeriod in pkPeriodList:
            toBeTuple[keys.index('pkPeriod')]=pkPeriod
            toPlot=[]
            for otfThreshold in otfThresholdList:
                toBeTuple[keys.index('otfThreshold')]=otfThreshold
                toPlot+=[zip(*dictionary[tuple(toBeTuple)])[-1]]
            toPlot=zip(*toPlot)
            matplotlib.pyplot.errorbar(
                                            otfThresholdList,toPlot[1],yerr=toPlot[2], color=col[pkPeriodList.index(pkPeriod)],  \
                                            label='pkPeriod={0}'.format(pkPeriod)
                                            )
        matplotlib.pyplot.legend(loc=0, prop=matplotlib.font_manager.FontProperties(family='monospace', style='oblique', size='xx-small'), labelspacing=0.0)
        matplotlib.pyplot.hold(False)
        matplotlib.pyplot.savefig(outfilepath)
        matplotlib.pyplot.close('all')
        
        # print
        print 'done.'


#============================ main ============================================

def main():
    
    # initialize logging
    logging.config.fileConfig('logging.conf')

    # verify there is some data to plot
    if not os.path.isdir(DATADIR):
        print 'There are no simulation results to analyze.'
        sys.exit(1)
    
    # parse CLI options
    options            = parseCliOptions()

    # plot figures
   
    for elemName in options['elemNames']:
        params={}
        numDirs=0
        keys=[]
        dictionary={}
        for dir in os.listdir(DATADIR):
            if os.path.isdir(os.path.join(DATADIR, dir)):
                numDirs+=1
                iterdir=iter(dir.split('_'))
                compare=[]
                toBeTuple=[]
                for i, item in [(l, eval(iterdir.next())) for l in iterdir]:
                    if i not in keys:
                        keys+=[i]
                    if i not in compare:
                        compare+=[i]
                    if not params.has_key(i):
                        params[i]=set()
                    params[i].update([item])
                    toBeTuple+=[item]
                assert keys==compare
                dictionary[tuple(toBeTuple)]=genTimelineAvgs(
                    infilepaths    = glob.glob(os.path.join(DATADIR, dir,'*.dat')),
                    elemName      = elemName,
                )
        assert numpy.product([len(value) for value in params.itervalues()])==numDirs
        genPlotsOTF(keys, params, dictionary, DATADIR, elemName)
    
if __name__=="__main__":
    main()
