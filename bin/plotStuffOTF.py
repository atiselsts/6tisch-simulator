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
import pprint

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
    #PLOT_LATENCY,
    #PLOT_NUMCELLS,
    #PLOT_OTFACTIVITY,
    PLOT_RELIABILITY,
]

PLOTYLABEL = {
    PLOT_LATENCY:       'end-to-end latency',
    PLOT_NUMCELLS:      'number of scheduled cells',
    PLOT_OTFACTIVITY:   'number of OTF add/remove operations',
    PLOT_RELIABILITY:   'end-to-end reliability',
}

pp = pprint.PrettyPrinter(indent=4)

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
    
    # infilepaths returns
    # res = {
    #       <----- numRuns ----->
    #    0: [12,12,1,12,12,12,12] ^
    #    1: [12,12,1,12,12,12,12] | numCycles
    #    2: [12,12,1,12,12,12,12] v
    #    ...
    # }
    
    if   plotType==PLOT_NUMCELLS:
        
        valuesPerCycle            = parseFiles(infilepaths,'numTxCells')
        
    elif plotType==PLOT_LATENCY:
        
        valuesPerCycle            = parseFiles(infilepaths,'aveQueueDelay')
        
    elif plotType==PLOT_OTFACTIVITY:
        
        otfAdd                    = parseFiles(infilepaths,'otfAdd')
        otfRemove                 = parseFiles(infilepaths,'otfRemove')
        assert sorted(otfAdd.keys())==sorted(otfRemove.keys())
        
        valuesPerCycle = {}
        for cycle in otfAdd.keys():
            assert len(otfAdd[cycle])==len(otfRemove[cycle])
            valuesPerCycle[cycle] = [a+r for (a,r) in zip(otfAdd[cycle],otfRemove[cycle])]
    
    elif plotType==PLOT_RELIABILITY:
        
        output  = []
        
        appGenerated              = parseFiles(infilepaths,'appGenerated')
        appReachesDagroot         = parseFiles(infilepaths,'appReachesDagroot')
        txQueueFill               = parseFiles(infilepaths,'txQueueFill')
        assert sorted(appGenerated.keys())==sorted(appReachesDagroot.keys())==sorted(txQueueFill.keys())
        
        valuesPerCycle = {}
        for cycle in appGenerated.keys():
            
            output  += ['\ncycle {0}\n'.format(cycle)]
            
            assert len(appGenerated[cycle])==len(appReachesDagroot[cycle])==len(txQueueFill[cycle])
            valuesPerCycle[cycle] = []
            
            for (g,r,q) in zip(appGenerated[cycle],appReachesDagroot[cycle],txQueueFill[cycle]):
                
                output  += ['g {0}'.format(g)]
                output  += ['r {0}'.format(r)]
                output  += ['q {0}'.format(q)]
                
                if g:
                    valuesPerCycle[cycle] += [1.0-((g-r-q)/g)]
                else:
                    valuesPerCycle[cycle] += [numpy.nan]
                
                
                valuesPerCycle[cycle] += [thisReliabilty]
        output  = '\n'.join(output)
        with open('poipoi.txt','w') as f:
            f.write(output)
        
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

def calcMeanConfInt(vals):
    assert type(vals)==list
    for val in vals:
        assert type(val) in [int,float]
    
    a         = 1.0*numpy.array(vals)
    se        = scipy.stats.sem(a)
    m         = numpy.mean(a)
    confint   = se * scipy.stats.t._ppf((1+CONFINT)/2., len(a)-1)
    
    return (m,confint)

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
                    x        = toPlot[0],
                    y        = toPlot[1],
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

def gatherPerCycleData(infilepaths,elemName):
    
    valuesPerCycle = {}
    for infilepath in infilepaths:
        
        # print
        print 'Parsing    {0} for {1}...'.format(infilepath,elemName),
        
        # find colnumelem, colnumcycle, colnumrunNum, processID
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('# '):
                    elems        = re.sub(' +',' ',line[2:]).split()
                    numcols      = len(elems)
                    colnumelem   = elems.index(elemName)
                    colnumcycle  = elems.index('cycle')
                    colnumrunNum = elems.index('runNum')
                    break
                
                if line.startswith('## '):
                    # processID
                    m = re.search('processID\s+=\s+([0-9]+)',line)
                    if m:
                        processID = int(m.group(1))
        
        assert colnumelem
        assert colnumcycle
        assert colnumrunNum
        assert processID
        
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
    
    return valuesPerCycle

def getSlotDuration(dataBins):
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        for filepath in filepaths:
            with open(filepath,'r') as f:
                for line in f:
                    if line.startswith('## '):
                        m = re.search('slotDuration\s+=\s+([\.0-9]+)',line)
                        if m:
                            return float(m.group(1))
    
def plot_latency_vs_time(dataBins):
    
    prettyp=False
    
    slotDuration = getSlotDuration(dataBins)
    
    #===== gather and format data
    
    # gather raw data
    plotData = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        plotData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'aveLatency')
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('gather raw data'))
            f.write(pp.pformat(plotData))
    
    # convert slots to seconds
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        for cycle in perCycleData.keys():
            perCycleData[cycle] = [d*slotDuration for d in perCycleData[cycle]]
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('convert slots to seconds'))
            f.write(pp.pformat(plotData))
    
    # filter out 0 values
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        for cycle in perCycleData.keys():
            i=0
            while i<len(perCycleData[cycle]):
                if perCycleData[cycle][i]==0:
                    del perCycleData[cycle][i]
                else:
                    i += 1
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12],
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('filter out 0 values'))
            f.write(pp.pformat(plotData))
    
    # calculate mean and confidence interval
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        for cycle in perCycleData.keys():
            (m,confint) = calcMeanConfInt(perCycleData[cycle])
            perCycleData[cycle] = {
                'mean':      m,
                'confint':   confint,
            }
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: {'mean': 12, 'confint':12},
    #         1: {'mean': 12, 'confint':12},
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('calculate mean and confidence interval'))
            f.write(pp.pformat(plotData))
    
    # arrange to be plotted
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        x     = sorted(perCycleData.keys())
        y     = [perCycleData[i]['mean']    for i in x]
        yerr  = [perCycleData[i]['confint'] for i in x]
        assert len(x)==len(y)==len(yerr)
        
        plotData[(otfThreshold,pkPeriod)] = {
            'x':        x,
            'y':        y,
            'yerr':     yerr,
        }
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         'x':      [ 0, 1, 2, 3, 4, 5, 6],
    #         'y':      [12,12,12,12,12,12,12],
    #         'yerr':   [12,12,12,12,12,12,12],
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('arrange to be plotted'))
            f.write(pp.pformat(plotData))
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    
    COLORS = {
        0:    '#FF0000',
        4:    '#008000',
        10:   '#000080',
    }
    
    ECOLORS = {
        0:    '#FA8072',
        4:    '#00FF00',
        10:   '#00FFFF',
    }
    
    def plotLatencies(ax,plotData,period):
        ax.set_xlim(xmin=0,xmax=100)
        ax.set_ylim(ymin=0,ymax=1.6)
        ax.text(2,1.4,'packet period {0}s'.format(period))
        plots = []
        for th in [0,4,10]:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==period:
                    plots += [
                        ax.errorbar(
                            x        = data['x'],
                            y        = data['y'],
                            yerr     = data['yerr'],
                            color    = COLORS[th],
                            ecolor   = ECOLORS[th],
                            #marker   = mark[pkPeriodList.index(pkPeriod)],
                        )
                    ]
        return tuple(plots)
    
    SUBPLOTHEIGHT = 0.28
    
    # pkPeriod=1s
    ax01 = fig.add_axes([0.10, 0.10+2*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax01.get_xaxis().set_visible(False)
    plotLatencies(ax01,plotData,1)
    
    # pkPeriod=10s
    ax10 = fig.add_axes([0.10, 0.10+1*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax10.get_xaxis().set_visible(False)
    plotLatencies(ax10,plotData,10)
    ax10.set_ylabel('end-to-end latency (s)')
    
    # pkPeriod=60s
    ax20 = fig.add_axes([0.10, 0.10+0*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    (th0,th4,th10) = plotLatencies(ax20,plotData,60)
    ax20.set_xlabel('time (in slotframe cycles)')
    
    fig.legend(
        (th0,th4,th10),
        ('OTF threshold 0', 'OTF threshold 4','OTF threshold 10'),
        'upper right',
        prop={'size':8},
    )
    
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'latency_vs_time.png'))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'latency_vs_time.eps'))
    matplotlib.pyplot.close('all')

#============================ main ============================================

# latency_vs_time
# latency_vs_threshold
# numCells_vs_threshold
# numCells_vs_time
# otfActivity_vs_threshold
# otfActivity_vs_time
# reliability_vs_threshold
# reliability_vs_time

def binDataFiles():
    '''
    bin the data files according to the otfThreshold and pkPeriod.
    
    Returns a dictionaty of format:
    {
        (otfThreshold,pkPeriod): [
            filepath,
            filepath,
            filepath,
        ]
    }
    '''
    infilepaths    = glob.glob(os.path.join(DATADIR,'**','*.dat'))
    
    dataBins       = {}
    for infilepath in infilepaths:
        with open(infilepath,'r') as f:
            for line in f:
                if not line.startswith('## ') or not line.strip():
                    continue
                # otfThreshold
                m = re.search('otfThreshold\s+=\s+([\.0-9]+)',line)
                if m:
                    otfThreshold = float(m.group(1))
                # pkPeriod
                m = re.search('pkPeriod\s+=\s+([\.0-9]+)',line)
                if m:
                    pkPeriod     = float(m.group(1))
            if (otfThreshold,pkPeriod) not in dataBins:
                dataBins[(otfThreshold,pkPeriod)] = []
            dataBins[(otfThreshold,pkPeriod)] += [infilepath]
    
    output  = []
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        output         += ['otfThreshold={0} pkPeriod={1}'.format(otfThreshold,pkPeriod)]
        for f in filepaths:
            output     += ['   {0}'.format(f)]
    output  = '\n'.join(output)
    print output
    
    return dataBins

def main():
    
    dataBins = binDataFiles()
    
    plot_latency_vs_time(dataBins)
    
    '''
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
    '''

if __name__=="__main__":
    main()
