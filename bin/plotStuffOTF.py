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

PLOT_LATENCY       = 'latency'
PLOT_NUMCELLS      = 'numCells'
PLOT_OTFACTIVITY   = 'otfActivity'
PLOT_RELIABILITY   = 'reliability'
PLOT_ALL           = [
    PLOT_LATENCY,
    PLOT_NUMCELLS,
    PLOT_OTFACTIVITY,
    PLOT_RELIABILITY,
]

PLOTYLABEL = {
    PLOT_LATENCY:       'end-to-end latency',
    PLOT_NUMCELLS:      'number of scheduled cells',
    PLOT_OTFACTIVITY:   'number of OTF add/remove operations',
    PLOT_RELIABILITY:   'end-to-end reliability',
}

#============================ body ============================================

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
                m       = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
                cycle   = int(m.group(colnumcycle+1))
                runNum  = int(m.group(colnumrunNum+1))
                try:
                    elem         = float(m.group(colnumelem+1))
                except:
                    try:
                        elem     =   int(m.group(colnumelem+1))
                    except:
                        elem     =       m.group(colnumelem+1)
                
                if cycle not in valuesPerCycle:
                    valuesPerCycle[cycle] = []
                valuesPerCycle[cycle] += [elem]
        
        # print
        print 'done.'
    
    assert len(set([len(value) for value in valuesPerCycle.values()]))==1
    return valuesPerCycle

def genTimelineAvgs(infilepaths,plotType):
    
    if   plotType==PLOT_NUMCELLS:
        
        valuesPerCycle            = parseFiles(infilepaths,'numTxCells')
        
    elif plotType==PLOT_LATENCY:
        
        valuesPerCycle            = parseFiles(infilepaths,'aveQueueDelay')
        
    elif plotType==PLOT_OTFACTIVITY:
        otfAdd                    = parseFiles(infilepaths,'otfAdd')
        otfRemove                 = parseFiles(infilepaths,'otfRemove')
        assert sorted(otfAdd.keys())==sorted(otfRemove.keys())
        
        valuesPerCycle = {}
        for k in otfAdd.keys():
            assert len(otfAdd[k])==len(otfRemove[k])
            valuesPerCycle[k]     = [x+y for (x,y) in zip(otfAdd[k],otfRemove[k])]
    
    elif plotType==PLOT_RELIABILITY:
        appGenerated              = parseFiles(infilepaths,'appGenerated')
        appReachesDagroot         = parseFiles(infilepaths,'appReachesDagroot')
        txQueueFill               = parseFiles(infilepaths,'txQueueFill')
        
        genCum                    = numpy.cumsum([appGenerated[key] for key in sorted(appGenerated.keys())], axis=0)
        reaCum                    = numpy.cumsum([appReachesDagroot[key] for key in sorted(appReachesDagroot.keys())], axis=0)
        txQueue                   = numpy.array([txQueueFill[key] for key in sorted(txQueueFill.keys())])
        
        toPutInDict               = reaCum/(genCum-txQueue)
        valuesPerCycle            = dict([(key, toPutInDict[key]) for key in sorted(appGenerated.keys())])
    
    else:
        raise SystemError()
    
    # calculate mean and confidence interval
    meanPerCycle                  = {}
    confintPerCycle               = {}
    for (k,v) in valuesPerCycle.items():
        a                         = 1.0*numpy.array(v)
        n                         = len(a)
        se                        = scipy.stats.sem(a)
        m                         = numpy.mean(a)
        confint                   = se * scipy.stats.t._ppf((1+CONFINT)/2., n-1)
        meanPerCycle[k]           = m
        confintPerCycle[k]        = confint
    
    x         = sorted(meanPerCycle.keys())
    y         = [meanPerCycle[k] for k in x]
    yerr      = [confintPerCycle[k] for k in x]
    
    return [x, y, yerr]

def genPlotsOTF(keys, params, dictionary, dir, plotType):
    assert 'otfThreshold'    in keys
    assert 'pkPeriod'        in keys
    
    figureKeys     = set(keys)-set(['otfThreshold', 'pkPeriod'])
    toBeTuple      = keys[:]
    col            = ['r', 'g', 'b', 'm', 'c', 'y']
    mark           = ['o', '>', 'd']

    for p in itertools.product(*[params[k] for k in figureKeys]):
        outfilenameList = []
        for (k,v) in zip(figureKeys,p):
            outfilenameList           += ['{0}_{1}'.format(k, v)]
            toBeTuple[keys.index(k)]   = v
        
        #===== vs. time
        
        outfilename          = '{0}_vs_time'.format(plotType)
        outfilepath          = os.path.join(dir,outfilename)
        
        # print
        print 'Generating {0}...'.format(outfilename),
        
        # plot
        matplotlib.pyplot.figure()
        matplotlib.pyplot.hold(True)
        otfThresholdList     = sorted(params['otfThreshold'])
        pkPeriodList         = sorted(params['pkPeriod'])
        for otfThreshold in otfThresholdList[0::2]:
            toBeTuple[keys.index('otfThreshold')]=otfThreshold
            for pkPeriod in pkPeriodList:
                toBeTuple[keys.index('pkPeriod')]=pkPeriod
                toPlot=dictionary[tuple(toBeTuple)]
                matplotlib.pyplot.errorbar(
                    toPlot[0],
                    toPlot[1],
                    yerr     = toPlot[2],
                    color    = col[otfThresholdList.index(otfThreshold)],
                    marker   = mark[pkPeriodList.index(pkPeriod)],
                    label    = 'otfThresh={0}, pkPeriod={1:.0f}s'.format(otfThreshold, pkPeriod),
                )
        matplotlib.pyplot.legend(
            loc              = 0,
            prop             = matplotlib.font_manager.FontProperties(family='monospace', style='oblique', size='xx-small'),
            labelspacing     = 0.0,
        )
        matplotlib.pyplot.hold(False)
        matplotlib.pyplot.xlabel('slotframe cycle')
        matplotlib.pyplot.ylabel(PLOTYLABEL[plotType])
        matplotlib.pyplot.savefig(outfilepath+'.png')
        matplotlib.pyplot.savefig(outfilepath+'.eps')
        matplotlib.pyplot.close('all')
        
        # print
        print 'done.'
        
        #===== vs. threshold
        
        outfilename          = '{0}_vs_threshold'.format(plotType)
        outfilepath          = os.path.join(dir,outfilename)
        
        # print
        print 'Generating {0}...'.format(outfilename),
        
        # plot
        matplotlib.pyplot.figure()
        matplotlib.pyplot.hold(True)
        otfThresholdList     = sorted(params['otfThreshold'])
        pkPeriodList         = sorted(params['pkPeriod'])
        for pkPeriod in pkPeriodList:
            toBeTuple[keys.index('pkPeriod')]=pkPeriod
            toPlot           = []
            for otfThreshold in otfThresholdList:
                toBeTuple[keys.index('otfThreshold')]=otfThreshold
                toPlot      += [zip(*dictionary[tuple(toBeTuple)])[-1]]
            toPlot=zip(*toPlot)
            matplotlib.pyplot.errorbar(
                otfThresholdList,
                toPlot[1],
                yerr         = toPlot[2],
                color        = col[pkPeriodList.index(pkPeriod)],
                label        = 'pkPeriod={0}'.format(pkPeriod),
            )
        matplotlib.pyplot.legend(
            loc              = 0,
            prop             = matplotlib.font_manager.FontProperties(family='monospace', style='oblique', size='xx-small'),
            labelspacing     = 0.0,
        )
        matplotlib.pyplot.hold(False)
        matplotlib.pyplot.xlabel('OTF threshold')
        matplotlib.pyplot.ylabel(PLOTYLABEL[plotType])
        matplotlib.pyplot.savefig(outfilepath+'.png')
        matplotlib.pyplot.savefig(outfilepath+'.eps')
        matplotlib.pyplot.close('all')
        
        # print
        print 'done.'

#============================ main ============================================

def main():
    
    # verify there is some data to plot
    if not os.path.isdir(DATADIR):
        print 'There are no simulation results to analyze.'
        sys.exit(1)
    
    # plot figures
    for plotType in PLOT_ALL:
        print '\n   {0}\n'.format(plotType)
        keys       = []
        params     = {}
        dictionary = {}
        numDirs    = 0
        for dir in os.listdir(DATADIR):
            if os.path.isdir(os.path.join(DATADIR, dir)):
                numDirs          += 1
                iterdir           = iter(dir.split('_'))
                compare           = []
                toBeTuple         = []
                for i, item in [(l, eval(iterdir.next())) for l in iterdir]:
                    if i not in keys:
                        keys     += [i]
                    if i not in compare:
                        compare  += [i]
                    if not params.has_key(i):
                        params[i] = set()
                    params[i].update([item])
                    toBeTuple    += [item]
                assert keys==compare
                dictionary[tuple(toBeTuple)] = genTimelineAvgs(
                    infilepaths   = glob.glob(os.path.join(DATADIR, dir,'*.dat')),
                    plotType      = plotType,
                )
        assert numpy.product([len(value) for value in params.itervalues()])==numDirs
        genPlotsOTF(keys, params, dictionary, DATADIR, plotType)

if __name__=="__main__":
    main()
