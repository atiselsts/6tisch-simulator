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

COLORS_TH = {
    0:   '#FF0000',
    4:   '#008000',
    10:  '#000080',
}

LINESTYLE_TH = {
    0:   '--',
    4:   '-.',
    10:  ':',
}

ECOLORS_TH = {
    0:   '#FA8072',
    4:   '#00FF00',
    10:  '#00FFFF',
}

COLORS_PERIOD = {
    1:   '#FF0000',
    10:  '#008000',
    60:  '#000080',
}

LINESTYLE_PERIOD = {
    1:   '--',
    10:  '-.',
    60:  ':',
}

ECOLORS_PERIOD = {
    1:   '#FA8072',
    10:  '#00FF00',
    60:  '#00FFFF',
}

pp = pprint.PrettyPrinter(indent=4)

#============================ helpers =========================================

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

def gatherPerRunData(infilepaths,elemName):
    
    valuesPerRun = {}
    for infilepath in infilepaths:
        
        # print
        print 'Parsing {0} for {1}...'.format(infilepath,elemName),
        
        # find colnumelem, colnumrunNum, processID
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('# '):
                    elems        = re.sub(' +',' ',line[2:]).split()
                    numcols      = len(elems)
                    colnumelem   = elems.index(elemName)
                    colnumrunNum = elems.index('runNum')
                    break
                
                if line.startswith('## '):
                    # processID
                    m = re.search('processID\s+=\s+([0-9]+)',line)
                    if m:
                        processID = int(m.group(1))
        
        assert colnumelem
        assert colnumrunNum
        assert processID
        
        # parse data
        
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                m       = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
                runNum  = int(m.group(colnumrunNum+1))
                try:
                    elem         = float(m.group(colnumelem+1))
                except:
                    try:
                        elem     =   int(m.group(colnumelem+1))
                    except:
                        elem     =       m.group(colnumelem+1)
                
                if (processID,runNum) not in valuesPerRun:
                    valuesPerRun[processID,runNum] = []
                valuesPerRun[processID,runNum] += [elem]
        
        # print
        print 'done.'
    
    return valuesPerRun

def gatherPerCycleData(infilepaths,elemName):
    
    valuesPerCycle = {}
    for infilepath in infilepaths:
        
        # print
        print 'Parsing {0} for {1}...'.format(infilepath,elemName),
        
        # find colnumelem, colnumcycle
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('# '):
                    elems        = re.sub(' +',' ',line[2:]).split()
                    numcols      = len(elems)
                    colnumelem   = elems.index(elemName)
                    colnumcycle  = elems.index('cycle')
                    break
        
        assert colnumelem
        assert colnumcycle
        
        # parse data
        
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                m       = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
                cycle   = int(m.group(colnumcycle+1))
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

def calcMeanConfInt(vals):
    assert type(vals)==list
    for val in vals:
        assert type(val) in [int,float]
    
    a         = 1.0*numpy.array(vals)
    se        = scipy.stats.sem(a)
    m         = numpy.mean(a)
    confint   = se * scipy.stats.t._ppf((1+CONFINT)/2., len(a)-1)
    
    return (m,confint)

def getSlotDuration(dataBins):
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        for filepath in filepaths:
            with open(filepath,'r') as f:
                for line in f:
                    if line.startswith('## '):
                        m = re.search('slotDuration\s+=\s+([\.0-9]+)',line)
                        if m:
                            return float(m.group(1))

#============================ plotters ========================================

def plot_vs_time(plotData,ymin,ymax,ylabel,filename):
    
    prettyp   = False
    
    #===== format data
    
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
    
    def plotForEachThreshold(ax,plotData,period):
        ax.set_xlim(xmin=0,xmax=100)
        ax.set_ylim(ymin=ymin,ymax=ymax)
        ax.text(2,0.9*ymax,'packet period {0}s'.format(period))
        plots = []
        for th in [0,4,10]:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==period:
                    plots += [
                        ax.errorbar(
                            x        = data['x'],
                            y        = data['y'],
                            yerr     = data['yerr'],
                            color    = COLORS_TH[th],
                            ls       = LINESTYLE_TH[th],
                            ecolor   = ECOLORS_TH[th],
                        )
                    ]
        return tuple(plots)
    
    SUBPLOTHEIGHT = 0.28
    
    # pkPeriod=1s
    ax01 = fig.add_axes([0.10, 0.10+2*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax01.get_xaxis().set_visible(False)
    plotForEachThreshold(ax01,plotData,1)
    
    # pkPeriod=10s
    ax10 = fig.add_axes([0.10, 0.10+1*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax10.get_xaxis().set_visible(False)
    plotForEachThreshold(ax10,plotData,10)
    ax10.set_ylabel(ylabel)
    
    # pkPeriod=60s
    ax20 = fig.add_axes([0.10, 0.10+0*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    (th0,th4,th10) = plotForEachThreshold(ax20,plotData,60)
    ax20.set_xlabel('time (in slotframe cycles)')
    
    fig.legend(
        (th0,th4,th10),
        ('OTF threshold 0 cells', 'OTF threshold 4 cells','OTF threshold 10 cells'),
        'upper right',
        prop={'size':8},
    )
    
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.png'.format(filename)))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.eps'.format(filename)))
    matplotlib.pyplot.close('all')

def plot_vs_threshold(plotData,ymin,ymax,ylabel,filename):
    
    prettyp   = False
    
    #===== format data
    
    # collapse all cycles
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        temp = []
        for (k,v) in perCycleData.items():
            temp += v
        plotData[(otfThreshold,pkPeriod)] = temp
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = [12,12,12,12,12,12,12,12,12],
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('collapse all cycles'))
            f.write(pp.pformat(plotData))
    
    # calculate mean and confidence interval
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        (m,confint) = calcMeanConfInt(perCycleData)
        plotData[(otfThreshold,pkPeriod)] = {
            'mean':      m,
            'confint':   confint,
        }
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {'mean': 12, 'confint':12},
    # }
    
    if prettyp:
        with open('poipoi.txt','a') as f:
            f.write('\npoipoipoipoi {0}\n'.format('calculate mean and confidence interval'))
            f.write(pp.pformat(plotData))
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    matplotlib.pyplot.ylim(ymin=ymin,ymax=ymax)
    matplotlib.pyplot.xlabel('OTF threshold (cells)')
    matplotlib.pyplot.ylabel(ylabel)
    for period in [1,10,60]:
        
        d = {}
        for ((otfThreshold,pkPeriod),data) in plotData.items():
            if pkPeriod==period:
                d[otfThreshold] = data
        x     = sorted(d.keys())
        y     = [d[k]['mean'] for k in x]
        yerr  = [d[k]['confint'] for k in x]
        
        matplotlib.pyplot.errorbar(
            x        = x,
            y        = y,
            yerr     = yerr,
            color    = COLORS_PERIOD[period],
            ls       = LINESTYLE_PERIOD[period],
            ecolor   = ECOLORS_PERIOD[period],
            label    = 'packet period {0}s'.format(period)
        )
    matplotlib.pyplot.legend(prop={'size':10})
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.png'.format(filename)))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.eps'.format(filename)))
    matplotlib.pyplot.close('all')

#===== latency

def gather_latency_data(dataBins):
    
    prettyp   = False
    
    # gather raw data
    plotData  = {}
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
    slotDuration = getSlotDuration(dataBins)
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
    
    return plotData

def plot_latency_vs_time(dataBins):
    
    plotData  = gather_latency_data(dataBins)
    
    plot_vs_time(
        plotData = plotData,
        ymin     = 0,
        ymax     = 1.6,
        ylabel   = 'end-to-end latency (s)',
        filename = 'latency_vs_time',
    )

def plot_latency_vs_threshold(dataBins):
    
    plotData  = gather_latency_data(dataBins)
    
    plot_vs_threshold(
        plotData   = plotData,
        ymin       = 0,
        ymax       = 1.6,
        ylabel     = 'end-to-end latency (s)',
        filename   = 'latency_vs_threshold',
    )

#===== numCells

def gather_numCells_data(dataBins):
    
    prettyp   = False
    
    # gather raw data
    plotData  = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        plotData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'numTxCells')
    
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
    
    return plotData

def plot_numCells_vs_time(dataBins):
    
    plotData  = gather_numCells_data(dataBins)
    
    plot_vs_time(
        plotData = plotData,
        ymin     = 0,
        ymax     = 600,
        ylabel   = 'number of scheduled cells',
        filename = 'numCells_vs_time',
    )

def plot_numCells_vs_threshold(dataBins):
    
    plotData  = gather_numCells_data(dataBins)
    
    plot_vs_threshold(
        plotData   = plotData,
        ymin       = 0,
        ymax       = 600,
        ylabel     = 'number of scheduled cells',
        filename   = 'numCells_vs_threshold',
    )

#===== otfActivity

def plot_otfActivity_vs_time(dataBins):
    
    prettyp   = False
    
    # gather raw add/remove data
    otfAddData     = {}
    otfRemoveData  = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        otfAddData[   (otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'otfAdd')
        otfRemoveData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'otfRemove')
    
    # otfAddData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # otfRemoveData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    #===== format data
    
    # calculate mean and confidence interval
    for ((otfThreshold,pkPeriod),perCycleData) in otfAddData.items():
        for cycle in perCycleData.keys():
            (m,confint) = calcMeanConfInt(perCycleData[cycle])
            perCycleData[cycle] = {
                'mean':      m,
                'confint':   confint,
            }
    for ((otfThreshold,pkPeriod),perCycleData) in otfRemoveData.items():
        for cycle in perCycleData.keys():
            (m,confint) = calcMeanConfInt(perCycleData[cycle])
            perCycleData[cycle] = {
                'mean':      -m,
                'confint':   confint,
            }
    
    # otfAddData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: {'mean': 12, 'confint':12},
    #         1: {'mean': 12, 'confint':12},
    #     }
    # }
    # otfRemoveData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: {'mean': 12, 'confint':12},
    #         1: {'mean': 12, 'confint':12},
    #     }
    # }
    
    # arrange to be plotted
    for ((otfThreshold,pkPeriod),perCycleData) in otfAddData.items():
        x     = sorted(perCycleData.keys())
        y     = [perCycleData[i]['mean']    for i in x]
        yerr  = [perCycleData[i]['confint'] for i in x]
        assert len(x)==len(y)==len(yerr)
        
        otfAddData[(otfThreshold,pkPeriod)] = {
            'x':        x,
            'y':        y,
            'yerr':     yerr,
        }
    for ((otfThreshold,pkPeriod),perCycleData) in otfRemoveData.items():
        x     = sorted(perCycleData.keys())
        y     = [perCycleData[i]['mean']    for i in x]
        yerr  = [perCycleData[i]['confint'] for i in x]
        assert len(x)==len(y)==len(yerr)
        
        otfRemoveData[(otfThreshold,pkPeriod)] = {
            'x':        x,
            'y':        y,
            'yerr':     yerr,
        }
    
    # otfAddData = {
    #     (otfThreshold,pkPeriod) = {
    #         'x':      [ 0, 1, 2, 3, 4, 5, 6],
    #         'y':      [12,12,12,12,12,12,12],
    #         'yerr':   [12,12,12,12,12,12,12],
    #     }
    # }
    # otfRemoveData = {
    #     (otfThreshold,pkPeriod) = {
    #         'x':      [ 0, 1, 2, 3, 4, 5, 6],
    #         'y':      [12,12,12,12,12,12,12],
    #         'yerr':   [12,12,12,12,12,12,12],
    #     }
    # }
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    
    def plotForEachThreshold(ax,plotData,period):
        ax.set_xlim(xmin=0,xmax=20)
        #ax.set_ylim(ymin=ymin,ymax=ymax)
        ax.text(2,-15,'packet period {0}s'.format(period))
        plots = []
        for th in [0,4]:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==period:
                    plots += [
                        ax.errorbar(
                            x        = data['x'],
                            y        = data['y'],
                            yerr     = data['yerr'],
                            color    = COLORS_TH[th],
                            ls       = LINESTYLE_TH[th],
                            ecolor   = ECOLORS_TH[th],
                        )
                    ]
        return tuple(plots)
    
    SUBPLOTHEIGHT = 0.28
    
    # pkPeriod=1s
    ax01 = fig.add_axes([0.10, 0.10+2*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax01.get_xaxis().set_visible(False)
    plotForEachThreshold(ax01,otfAddData,1)
    plotForEachThreshold(ax01,otfRemoveData,1)
    
    # pkPeriod=10s
    ax10 = fig.add_axes([0.10, 0.10+1*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    ax10.get_xaxis().set_visible(False)
    plotForEachThreshold(ax10,otfAddData,10)
    plotForEachThreshold(ax10,otfRemoveData,10)
    ax10.set_ylabel('number of add/remove OTF operations per cycle')
    
    # pkPeriod=60s
    ax60 = fig.add_axes([0.10, 0.10+0*SUBPLOTHEIGHT, 0.85, SUBPLOTHEIGHT])
    plotForEachThreshold(ax60,otfAddData,60)
    (th0,th4) = plotForEachThreshold(ax60,otfRemoveData,60)
    ax60.set_xlabel('time (in slotframe cycles)')
    
    fig.legend(
        (th0,th4),
        ('OTF threshold 0 cells', 'OTF threshold 4 cells'),
        'upper right',
        prop={'size':8},
    )
    
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'otfActivity_vs_time.png'))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'otfActivity_vs_time.eps'))
    matplotlib.pyplot.close('all')

def gather_sumOtfActivity_data(dataBins):
    
    prettyp   = False
    
    # gather raw add/remove data
    otfAddData     = {}
    otfRemoveData  = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        otfAddData[   (otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'otfAdd')
        otfRemoveData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'otfRemove')
    
    # otfAddData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # otfRemoveData = {
    #     (otfThreshold,pkPeriod) = {
    #         0: [12,12,12,12,12,12,12,12,12],
    #         1: [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    assert sorted(otfAddData.keys())==sorted(otfRemoveData.keys())
    for otfpk in otfAddData.keys():
        assert sorted(otfAddData[otfpk].keys())==sorted(otfRemoveData[otfpk].keys())
    
    # sum up number of add/remove operations
    
    plotData = {}
    for otfpk in otfAddData.keys():
        plotData[otfpk] = {}
        for cycle in otfAddData[otfpk].keys():
            plotData[otfpk][cycle] = [sum(x) for x in zip(otfAddData[otfpk][cycle],otfRemoveData[otfpk][cycle])]
    
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
    
    return plotData

def plot_otfActivity_vs_threshold(dataBins):
    
    plotData  = gather_sumOtfActivity_data(dataBins)
    
    plot_vs_threshold(
        plotData   = plotData,
        ymin       = 0,
        ymax       = 25,
        ylabel     = 'number of add/remove OTF operations per cycle',
        filename   = 'otfActivity_vs_threshold',
    )

#===== reliability

def plot_reliability_vs_threshold(dataBins):
    
    prettyp = False
    
    #===== gather data
    
    # gather raw add/remove data
    appGeneratedData    = {}
    appReachedData      = {}
    txQueueFillData     = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        appGeneratedData[(otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'appGenerated')
        appReachedData[  (otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'appReachesDagroot')
        txQueueFillData[ (otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'txQueueFill')
    
    # appGeneratedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): [12,12,12,12,12,12,12,12,12],
    #         (0,1): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # appReachedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): [12,12,12,12,12,12,12,12,12],
    #         (0,1): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # txQueueFillData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): [12,12,12,12,12,12,12,12,12],
    #         (0,1): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('gather raw add/remove data'))
            f.write('appGeneratedData={0}'.format(pp.pformat(appGeneratedData)))
            f.write('appReachedData={0}'.format(pp.pformat(appReachedData)))
            f.write('txQueueFillData={0}'.format(pp.pformat(txQueueFillData)))
    
    #===== format data
    
    # sum up appGeneratedData and appReachedData
    for ((otfThreshold,pkPeriod),perRunData) in appGeneratedData.items():
        for runNum in perRunData.keys():
            perRunData[runNum] = sum(perRunData[runNum])
    for ((otfThreshold,pkPeriod),perRunData) in appReachedData.items():
        for runNum in perRunData.keys():
            perRunData[runNum] = sum(perRunData[runNum])
    
    # appGeneratedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): 12,
    #         (0,1): 14,
    #     }
    # }
    # appReachedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): 12,
    #         (0,1): 12,
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('sum up appGeneratedData and appReachedData'))
            f.write('appGeneratedData={0}'.format(pp.pformat(appGeneratedData)))
            f.write('appReachedData={0}'.format(pp.pformat(appReachedData)))
    
    # get last of txQueueFillData
    for ((otfThreshold,pkPeriod),perRunData) in txQueueFillData.items():
        for runNum in perRunData.keys():
            perRunData[runNum] = perRunData[runNum][-1]
    
    # txQueueFillData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): 12,
    #         (0,1): 12,
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('get last of txQueueFillData'))
            f.write('txQueueFillData={0}'.format(pp.pformat(txQueueFillData)))
    
    # calculate the end-to-end reliability for each runNum
    reliabilityData = {}
    for otfpk in appReachedData.keys():
        reliabilityData[otfpk] = {}
        for runNum in appReachedData[otfpk]:
            g = float(appGeneratedData[otfpk][runNum])
            r = float(appReachedData[otfpk][runNum])
            q = float(txQueueFillData[otfpk][runNum])
            assert g>0
            reliability = (r+q)/g
            assert reliability>=0
            assert reliability<=1
            reliabilityData[otfpk][runNum] = reliability
    
    # reliabilityData = {
    #     (otfThreshold,pkPeriod) = {
    #         (0,0): 0.9558,
    #         (0,1): 1.0000,
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('calculate the end-to-end reliability for each cycle'))
            f.write('reliabilityData={0}'.format(pp.pformat(reliabilityData)))
    
    # calculate the end-to-end reliability per (otfThreshold,pkPeriod)
    for otfpk in appReachedData.keys():
        vals = reliabilityData[otfpk].values()
        (m,confint) = calcMeanConfInt(vals)
        reliabilityData[otfpk] = {
            'mean':      m,
            'confint':   confint,
        }
    
    # reliabilityData = {
    #     (otfThreshold,pkPeriod) = {'mean': 12, 'confint':12},
    #     }
    # }
    
    if prettyp:
        with open('poipoi.txt','w') as f:
            f.write('\npoipoipoipoi {0}\n'.format('calculate the end-to-end reliability per (otfThreshold,pkPeriod)'))
            f.write('reliabilityData={0}'.format(pp.pformat(reliabilityData)))
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    matplotlib.pyplot.ylim(ymin=0.94,ymax=1.015)
    matplotlib.pyplot.xlabel('OTF threshold (cells)')
    matplotlib.pyplot.ylabel('end-to-end reliability')
    for period in [1,10,60]:
        
        d = {}
        for ((otfThreshold,pkPeriod),data) in reliabilityData.items():
            if pkPeriod==period:
                d[otfThreshold] = data
        x     = sorted(d.keys())
        y     = [d[k]['mean'] for k in x]
        yerr  = [d[k]['confint'] for k in x]
        
        matplotlib.pyplot.errorbar(
            x        = x,
            y        = y,
            yerr     = yerr,
            color    = COLORS_PERIOD[period],
            ls       = LINESTYLE_PERIOD[period],
            ecolor   = ECOLORS_PERIOD[period],
            label    = 'packet period {0}s'.format(period)
        )
    matplotlib.pyplot.legend(prop={'size':10})
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'reliability_vs_threshold.png'))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'reliability_vs_threshold.eps'))
    matplotlib.pyplot.close('all')
    
#============================ main ============================================

# latency_vs_threshold
# numCells_vs_threshold
# numCells_vs_time
# otfActivity_vs_threshold
# otfActivity_vs_time
# reliability_vs_threshold
# reliability_vs_time


def main():
    
    dataBins = binDataFiles()
    
    # latency
    plot_latency_vs_time(dataBins)
    plot_latency_vs_threshold(dataBins)
    
    # numCells
    plot_numCells_vs_time(dataBins)
    plot_numCells_vs_threshold(dataBins)
    
    # otfActivity
    #plot_otfActivity_vs_time(dataBins)
    plot_otfActivity_vs_threshold(dataBins)
    
    # reliability
    plot_reliability_vs_threshold(dataBins)

if __name__=="__main__":
    main()
