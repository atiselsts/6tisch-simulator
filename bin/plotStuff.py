#!/usr/bin/python
'''
\brief Plots timelines and topology figures from collected simulation data.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
'''

import os
import re
import glob
import pprint

import numpy
import scipy
import scipy.stats

import matplotlib.pyplot

#============================ defines =========================================

DATADIR       = 'simData'
CONFINT       = 0.95

COLORS_TH     = {
    0:        'red',
    1:        'green',
    4:        'blue',
    8:        'magenta',
    10:       'black',
}

LINESTYLE_TH       = {
    0:        '--',
    1:        '--',
    4:        '-.',
    8:        '-.',
    10:       ':',
}

ECOLORS_TH         = {
    0:        'red',
    1:        'green',
    4:        'blue',
    8:        'magenta',
    10:       'black',
}

COLORS_PERIOD      = {
    'NA':     'red',
    1:        'green',
    10:       'blue',
    60:       'black',
}

LINESTYLE_PERIOD   = {
    'NA':     '--',
    1:        '--',
    10:       '-.',
    60:       ':',
}

ECOLORS_PERIOD     = {
    'NA':     'red',
    1:        'green',
    10:       'blue',
    60:       'magenta',
}

pp = pprint.PrettyPrinter(indent=4)

#============================ helpers =========================================

def binDataFiles():
    '''
    bin the data files according to the otfThreshold and pkPeriod.
    
    Returns a dictionary of format:
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
                else:
                    pkPeriod     = 'NA'
            if (otfThreshold,pkPeriod) not in dataBins:
                dataBins[(otfThreshold,pkPeriod)] = []
            dataBins[(otfThreshold,pkPeriod)] += [infilepath]
    
    output  = []
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        output         += ['otfThreshold={0} pkPeriod={1}'.format(otfThreshold,pkPeriod)]
        for f in filepaths:
            output     += ['   {0}'.format(f)]
    output  = '\n'.join(output)
    
    return dataBins

def gatherPerRunData(infilepaths,elemName):
    
    valuesPerRun = {}
    for infilepath in infilepaths:
        
        # print
        print 'Parsing {0} for {1}...'.format(infilepath,elemName),
        
        # find col_elemName, col_runNum, cpuID
        col_elemName    = None
        col_runNum      = None
        cpuID           = None
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('# '):
                    # col_elemName, col_runNum
                    elems        = re.sub(' +',' ',line[2:]).split()
                    numcols      = len(elems)
                    col_elemName = elems.index(elemName)
                    col_runNum   = elems.index('runNum')
                    break
                
                if line.startswith('## '):
                    # cpuID
                    m = re.search('cpuID\s+=\s+([0-9]+)',line)
                    if m:
                        cpuID = int(m.group(1))
        
        assert col_elemName!=None
        assert col_runNum!=None
        # see SimSettings.getOutputFile() for the data file naming pattern.
        assert cpuID==None or re.match('output_cpu[0-9]+.dat', os.path.basename(infilepath))!=None
        
        # parse data
        with open(infilepath,'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                m       = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
                runNum  = int(m.group(col_runNum+1))
                try:
                    elem         = float(m.group(col_elemName+1))
                except:
                    try:
                        elem     =   int(m.group(col_elemName+1))
                    except:
                        elem     =       m.group(col_elemName+1)
                
                if (cpuID,runNum) not in valuesPerRun:
                    valuesPerRun[cpuID,runNum] = []
                valuesPerRun[cpuID,runNum] += [elem]
        
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

def plot_vs_time(plotData,ymin=None,ymax=None,ylabel=None,filename=None,doPlot=True):
    
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
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('arrange to be plotted'))
            f.write(pp.pformat(plotData))
    
    if not doPlot:
        return plotData
    
    #===== plot
    
    pkPeriods           = []
    otfThresholds       = []
    for (otfThreshold,pkPeriod) in plotData.keys():
        pkPeriods      += [pkPeriod]
        otfThresholds  += [otfThreshold]
    pkPeriods           = sorted(list(set(pkPeriods)))
    otfThresholds       = sorted(list(set(otfThresholds)), reverse=True)
    
    fig = matplotlib.pyplot.figure()
    
    def plotForEachPkPeriod(ax,plotData,pkPeriod_p):
        ax.set_xlim(xmin=0,xmax=100)
        ax.set_ylim(ymin=ymin,ymax=ymax)
        if pkPeriod_p!='NA':
            ax.text(2,0.9*ymax,'packet period {0}s'.format(pkPeriod_p))
        plots = []
        for th in otfThresholds:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==pkPeriod_p:
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
    
    # plot axis
    allaxes = []
    if 'NA' not in pkPeriods:
        subplotHeight = 0.85/len(pkPeriods)
        for (plotIdx,pkPeriod) in enumerate(pkPeriods):
            ax = fig.add_axes([0.10, 0.10+plotIdx*subplotHeight, 0.85, subplotHeight])
            legendPlots = plotForEachPkPeriod(ax,plotData,pkPeriod)
            allaxes += [ax]
    else:
        ax = fig.add_axes([0.10, 0.10, 0.85, 0.85])
        ax.set_xlim(xmin=0,xmax=100)
        ax.set_ylim(ymin=ymin,ymax=ymax)
        plots = []
        for th in otfThresholds:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th:
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
        legendPlots = tuple(plots)
        allaxes += [ax]
    
    # add x label
    for ax in allaxes[1:]:
        ax.get_xaxis().set_visible(False)
    allaxes[0].set_xlabel('time (slotframe cycles)')
    
    # add y label
    allaxes[int(len(allaxes)/2)].set_ylabel(ylabel)
    
    # add legend
    legendText = tuple(['OTF threshold {0} cells'.format(t) for t in otfThresholds])
    fig.legend(
        legendPlots,
        legendText,
        'upper right',
        prop={'size':8},
    )
    
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.png'.format(filename)))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'{0}.eps'.format(filename)))
    matplotlib.pyplot.close('all')

def plot_vs_threshold(plotData,ymin,ymax,ylabel,filename):
    
    prettyp   = False
    
    #===== format data
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         cycle0: [run0,run1, ...],
    #         cycle1: [run0,run1, ...],
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('initial data'))
            f.write(pp.pformat(plotData))
    
    # collapse all cycles
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        temp = []
        for (k,v) in perCycleData.items():
            temp += v
        plotData[(otfThreshold,pkPeriod)] = temp
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = [
    #         cycle0_run0,
    #         cycle0_run1,
    #         ...,
    #         cycle1_run0,
    #         cycle1_run1,
    #         ...,
    #     ]
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('collapse all cycles'))
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
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('calculate mean and confidence interval'))
            f.write(pp.pformat(plotData))
    
    pkPeriods           = []
    otfThresholds       = []
    for (otfThreshold,pkPeriod) in plotData.keys():
        pkPeriods      += [pkPeriod]
        otfThresholds  += [otfThreshold]
    pkPeriods           = sorted(list(set(pkPeriods)))
    otfThresholds       = sorted(list(set(otfThresholds)), reverse=True)
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    matplotlib.pyplot.ylim(ymin=ymin,ymax=ymax)
    matplotlib.pyplot.xlabel('OTF threshold (cells)')
    matplotlib.pyplot.ylabel(ylabel)
    for period in pkPeriods:
        
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
    #         cycle0: [run0,run1, ...],
    #         cycle1: [run0,run1, ...],
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('gather raw data'))
            f.write(pp.pformat(plotData))
    
    # convert slots to seconds
    slotDuration = getSlotDuration(dataBins)
    for ((otfThreshold,pkPeriod),perCycleData) in plotData.items():
        for cycle in perCycleData.keys():
            perCycleData[cycle] = [d*slotDuration for d in perCycleData[cycle]]
    
    # plotData = {
    #     (otfThreshold,pkPeriod) = {
    #         cycle0: [run0,run1, ...],
    #         cycle1: [run0,run1, ...],
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('convert slots to seconds'))
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
    #         cycle0: [run0,run1, ...],
    #         cycle1: [run0,run1, ...],
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('filter out 0 values'))
            f.write(pp.pformat(plotData))
    
    return plotData

def plot_latency_vs_time(dataBins):
    
    plotData  = gather_latency_data(dataBins)
    
    plot_vs_time(
        plotData = plotData,
        ymin     = 0,
        ymax     = 8,
        ylabel   = 'end-to-end latency (s)',
        filename = 'latency_vs_time',
    )

def plot_latency_vs_threshold(dataBins):
    
    plotData  = gather_latency_data(dataBins)
    
    plot_vs_threshold(
        plotData   = plotData,
        ymin       = 0,
        ymax       = 3,
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
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('gather raw data'))
            f.write(pp.pformat(plotData))
    
    return plotData

def plot_numCells_vs_time(dataBins):
    
    plotData  = gather_numCells_data(dataBins)
    
    plot_vs_time(
        plotData = plotData,
        ymin     = 0,
        ymax     = 200,
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

def plot_numCells_otfActivity_vs_time(dataBins):
    
    plotData  = gather_numCells_data(dataBins)
    
    plotDataNumCells = plot_vs_time(
        plotData   = plotData,
        doPlot     = False,
    )
    
    (otfAddData,otfRemoveData) = plot_otfActivity_vs_time(
        dataBins   = dataBins,
        doPlot     = False,
    )
    
    #===== plot
    
    allaxes = []
    pkPeriods           = []
    otfThresholds       = []
    for (otfThreshold,pkPeriod) in plotDataNumCells.keys():
        pkPeriods      += [pkPeriod]
        otfThresholds  += [otfThreshold]
    pkPeriods           = sorted(list(set(pkPeriods)))
    otfThresholds       = sorted(list(set(otfThresholds)), reverse=True)
    
    fig = matplotlib.pyplot.figure(figsize=(8, 4))
    
    #=== otfActivity
    
    def plotForEachPkPeriodOtfActivity(ax,plotData,pkPeriod_p):
        plots = []
        for th in otfThresholds:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==pkPeriod_p:
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
    
    def maxY(plotData):
        returnVal = []
        for ((otfThreshold,pkPeriod),data) in plotData.items():
            returnVal += data['y']
        return max(returnVal)
    
    # plot axis
    ax = fig.add_axes([0.12, 0.54, 0.85, 0.40])
    ax.set_xlim(xmin= 0,xmax=100)
    ax.set_ylim(ymin=-4,ymax=8)
    ax.annotate(
        'max. value {0:.0f}'.format(maxY(otfAddData)),
        xy=(10, 7.9),
        xycoords='data',
        xytext=(22, 4),
        textcoords='data',
        arrowprops=dict(arrowstyle="->",facecolor='black'),
        horizontalalignment='right',
        verticalalignment='top',
    )
    ax.annotate(
        'add cells',
        xytext=(50,0.2),
        xy    =(50,3.8),
        xycoords='data',
        textcoords='data',
        arrowprops=dict(arrowstyle="->",facecolor='black'),
        horizontalalignment='center',
        verticalalignment='bottom',
    )
    ax.annotate(
        'remove cells',
        xytext=(50,-0.2),
        xy    =(50,-3.8),
        xycoords='data',
        textcoords='data',
        arrowprops=dict(arrowstyle="->",facecolor='black'),
        horizontalalignment='center',
        verticalalignment='top',
    )
    plotForEachPkPeriodOtfActivity(ax,otfAddData,pkPeriod)
    plotForEachPkPeriodOtfActivity(ax,otfRemoveData,pkPeriod)
    allaxes += [ax]    
    
    # add x/y labels
    ax.set_xticks([])
    ax.set_ylabel('num. add/remove OTF\noperations per cycle')
    
    #=== numCells
    
    # plot axis
    ax = fig.add_axes([0.12, 0.14, 0.85, 0.40])
    ax.set_xlim(xmin=0,xmax=100)
    ax.set_ylim(ymin=0,ymax=199)
    plots = []
    for th in otfThresholds:
        for ((otfThreshold,pkPeriod),data) in plotDataNumCells.items():
            if otfThreshold==th:
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
    legendPlots = tuple(plots)
    
    # add x/y labels
    ax.set_xlabel('time (slotframe cycles)')
    ax.set_ylabel('number of\nscheduled cells')
    ax.annotate(
        'first burst\n(5 packets per node)',
        xy=(20, 120),
        xycoords='data',
        xytext=(20, 35),
        textcoords='data',
        arrowprops=dict(arrowstyle="->",facecolor='black'),
        horizontalalignment='center',
        verticalalignment='center',
    )
    ax.annotate(
        'second burst\n(5 packets per node)',
        xy=(60, 120),
        xycoords='data',
        xytext=(60, 35),
        textcoords='data',
        arrowprops=dict(arrowstyle="->",facecolor='black'),
        horizontalalignment='center',
        verticalalignment='center',
    )
    
    #=== legend
    
    legendText = tuple(['OTF threshold {0} cells'.format(t) for t in otfThresholds])
    fig.legend(
        legendPlots,
        legendText,
        'upper right',
        prop={'size':11},
    )
    
    allaxes += [ax]
    
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'numCells_otfActivity_vs_time.png'))
    matplotlib.pyplot.savefig(os.path.join(DATADIR,'numCells_otfActivity_vs_time.eps'))
    matplotlib.pyplot.close('all')
    
#===== otfActivity

def plot_otfActivity_vs_time(dataBins,doPlot=True):
    
    prettyp   = False
    
    # gather raw add/remove data
    otfAddData     = {}
    otfRemoveData  = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        otfAddData[   (otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'6topTxAddReq')
        otfRemoveData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'6topTxDelReq')
    
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
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('gather raw add/remove data'))
            f.write(pp.pformat(otfAddData))
            f.write(pp.pformat(otfRemoveData))
    
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
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('calculate mean and confidence interval'))
            f.write(pp.pformat(otfAddData))
            f.write(pp.pformat(otfRemoveData))
    
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
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('arrange to be plotted'))
            f.write(pp.pformat(otfAddData))
            f.write(pp.pformat(otfRemoveData))
    
    if not doPlot:
        return (otfAddData,otfRemoveData)
    
    pkPeriods           = []
    otfThresholds       = []
    for (otfThreshold,pkPeriod) in otfAddData.keys():
        pkPeriods      += [pkPeriod]
        otfThresholds  += [otfThreshold]
    pkPeriods           = sorted(list(set(pkPeriods)))
    otfThresholds       = sorted(list(set(otfThresholds)), reverse=True)
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    
    def plotForEachPkPeriod(ax,plotData,pkPeriod_p):
        #ax.set_xlim(xmin=poi,xmax=poi)
        #ax.set_ylim(ymin=0,ymax=50)
        if pkPeriod_p!='NA':
            ax.text(1,70,'packet period {0}s'.format(pkPeriod_p))
        plots = []
        for th in otfThresholds:
            for ((otfThreshold,pkPeriod),data) in plotData.items():
                if otfThreshold==th and pkPeriod==pkPeriod_p:
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
    
    # plot axis
    allaxes = []
    subplotHeight = 0.85/len(pkPeriods)
    for (plotIdx,pkPeriod) in enumerate(pkPeriods):
        ax = fig.add_axes([0.12, 0.10+plotIdx*subplotHeight, 0.85, subplotHeight])
        legendPlots = plotForEachPkPeriod(ax,otfAddData,pkPeriod)
        legendPlots = plotForEachPkPeriod(ax,otfRemoveData,pkPeriod)
        allaxes += [ax]
    
    # add x label
    for ax in allaxes[1:]:
        ax.get_xaxis().set_visible(False)
    allaxes[0].set_xlabel('time (slotframe cycles)')
    
    # add y label
    allaxes[int(len(allaxes)/2)].set_ylabel('number of add/remove OTF\noperations per cycle')
    
    # add legend
    legendText = tuple(['OTF threshold {0} cells'.format(t) for t in otfThresholds])
    fig.legend(
        legendPlots,
        legendText,
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
        otfAddData[   (otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'6topTxAddReq')
        otfRemoveData[(otfThreshold,pkPeriod)] = gatherPerCycleData(filepaths,'6topTxDelReq')
    
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
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('gather raw data'))
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
    
    prettyp = True
    
    #===== gather data
    
    # gather raw add/remove data
    appGeneratedData    = {}
    appReachedData      = {}
    dataQueueFillData     = {}
    for ((otfThreshold,pkPeriod),filepaths) in dataBins.items():
        appGeneratedData[(otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'appGenerated')
        appReachedData[  (otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'appReachesDagroot')
        dataQueueFillData[ (otfThreshold,pkPeriod)]=gatherPerRunData(filepaths,'dataQueueFill')
    
    # appGeneratedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): [12,12,12,12,12,12,12,12,12],
    #         (cpuID,runNum): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # appReachedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): [12,12,12,12,12,12,12,12,12],
    #         (cpuID,runNum): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    # dataQueueFillData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): [12,12,12,12,12,12,12,12,12],
    #         (cpuID,runNum): [12,12,12,12,12,0,0,0,0],
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','w') as f:
            f.write('\n============ {0}\n'.format('gather raw add/remove data'))
            f.write('appGeneratedData={0}'.format(pp.pformat(appGeneratedData)))
            f.write('appReachedData={0}'.format(pp.pformat(appReachedData)))
            f.write('dataQueueFillData={0}'.format(pp.pformat(dataQueueFillData)))
    
    #===== format data
    
    # sum up appGeneratedData
    for ((otfThreshold,pkPeriod),perRunData) in appGeneratedData.items():
        for cpuID_runNum in perRunData.keys():
            perRunData[cpuID_runNum] = sum(perRunData[cpuID_runNum])
    # sum up appReachedData
    for ((otfThreshold,pkPeriod),perRunData) in appReachedData.items():
        for cpuID_runNum in perRunData.keys():
            perRunData[cpuID_runNum] = sum(perRunData[cpuID_runNum])
    # get last of dataQueueFillData
    for ((otfThreshold,pkPeriod),perRunData) in dataQueueFillData.items():
        for cpuID_runNum in perRunData.keys():
            perRunData[cpuID_runNum] = perRunData[cpuID_runNum][-1]
    
    # appGeneratedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): sum_over_all_cycles,
    #         (cpuID,runNum): sum_over_all_cycles,
    #     }
    # }
    # appReachedData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): sum_over_all_cycles,
    #         (cpuID,runNum): sum_over_all_cycles,
    #     }
    # }
    # dataQueueFillData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): value_last_cycles,
    #         (cpuID,runNum): value_last_cycles,
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('format data'))
            f.write('\nappGeneratedData={0}'.format(pp.pformat(appGeneratedData)))
            f.write('\nappReachedData={0}'.format(pp.pformat(appReachedData)))
            f.write('\ndataQueueFillData={0}'.format(pp.pformat(dataQueueFillData)))
    
    #===== calculate the end-to-end reliability for each runNum
    
    reliabilityData = {}
    for otfThreshold_pkPeriod in appReachedData.keys():
        reliabilityData[otfThreshold_pkPeriod] = {}
        for cpuID_runNum in appReachedData[otfThreshold_pkPeriod]:
            g = float(appGeneratedData[otfThreshold_pkPeriod][cpuID_runNum])
            r = float(appReachedData[otfThreshold_pkPeriod][cpuID_runNum])
            q = float(dataQueueFillData[otfThreshold_pkPeriod][cpuID_runNum])
            assert g>0
            reliability = r/(g-q)
            assert reliability>=0
            assert reliability<=1
            reliabilityData[otfThreshold_pkPeriod][cpuID_runNum] = reliability
    
    # reliabilityData = {
    #     (otfThreshold,pkPeriod) = {
    #         (cpuID,runNum): 0.9558,
    #         (cpuID,runNum): 1.0000,
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('calculate the end-to-end reliability for each cycle'))
            f.write('reliabilityData={0}'.format(pp.pformat(reliabilityData)))
    
    # calculate the end-to-end reliability per (otfThreshold,pkPeriod)
    for otfThreshold_pkPeriod in reliabilityData.keys():
        vals = reliabilityData[otfThreshold_pkPeriod].values()
        (m,confint) = calcMeanConfInt(vals)
        reliabilityData[otfThreshold_pkPeriod] = {
            'mean':      m,
            'confint':   confint,
        }
    
    # reliabilityData = {
    #     (otfThreshold,pkPeriod) = {
    #         'mean': 12,
    #         'confint':12,
    #     }
    # }
    
    if prettyp:
        with open('templog.txt','a') as f:
            f.write('\n============ {0}\n'.format('calculate the end-to-end reliability per (otfThreshold,pkPeriod)'))
            f.write('reliabilityData={0}'.format(pp.pformat(reliabilityData)))
    
    pkPeriods           = []
    otfThresholds       = []
    for (otfThreshold,pkPeriod) in reliabilityData.keys():
        pkPeriods      += [pkPeriod]
        otfThresholds  += [otfThreshold]
    pkPeriods           = sorted(list(set(pkPeriods)))
    otfThresholds       = sorted(list(set(otfThresholds)), reverse=True)
    
    #===== plot
    
    fig = matplotlib.pyplot.figure()
    matplotlib.pyplot.ylim(ymin=0.94,ymax=1.015)
    matplotlib.pyplot.xlabel('OTF threshold (cells)')
    matplotlib.pyplot.ylabel('end-to-end reliability')
    for period in pkPeriods:
        
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

def main():
    
    dataBins = binDataFiles()
    
    # latency
    plot_latency_vs_time(dataBins)
    plot_latency_vs_threshold(dataBins)
    
    # numCells
    plot_numCells_vs_time(dataBins)
    plot_numCells_vs_threshold(dataBins)
    plot_numCells_otfActivity_vs_time(dataBins)
    
    # otfActivity
    plot_otfActivity_vs_time(dataBins)
    plot_otfActivity_vs_threshold(dataBins)
    
    # reliability
    plot_reliability_vs_threshold(dataBins)

if __name__=="__main__":
    main()
