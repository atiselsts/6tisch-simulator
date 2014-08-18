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

#============================ defines =========================================

DATADIR = 'simData'
CONFINT = 0.95

#============================ body ============================================

def parseCliOptions():
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument( '--elemNames',
        dest       = 'elemNames',
        nargs      = '+',
        type       = str,
        default    = [
            'numTxCells',
        ],
        help       = 'Name of the elements to generate timeline figures for.',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__

def genTimelinePlots(dir,infilemame,elemName):
    
    infilepath     = os.path.join(dir,infilemame)
    outfilename    = infilemame.split('.')[0]+'_{}.png'.format(elemName)
    outfilepath    = os.path.join(dir,outfilename)
    
    # print
    print 'Parsing    {0}...'.format(infilemame),
    
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
    valuesPerCycle = {}
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
    
    # print
    print 'Generating {0}...'.format(outfilename),
    
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
    
    # plot
    x         = sorted(meanPerCycle.keys())
    y         = [meanPerCycle[k] for k in x]
    yerr      = [confintPerCycle[k] for k in x]
    matplotlib.pyplot.figure()
    matplotlib.pyplot.errorbar(x,y,yerr=yerr)
    matplotlib.pyplot.savefig(outfilepath)
    matplotlib.pyplot.close('all')
    
    # print
    print 'done.'

def genTopologyPlots(dir,infilemame):
    
    infilepath     = os.path.join(dir,infilemame)
    
    # print
    print 'Parsing    {0}...'.format(infilemame),
    
    # parse data
    xcoord         = {}
    ycoord         = {}
    motes          = {}
    links          = {}
    with open(infilepath,'r') as f:
        for line in f:
            
            if line.startswith('##'):
                # squareSide
                m = re.search('squareSide\s+=\s+([\.0-9]+)',line)
                if m:
                    squareSide = float(m.group(1))
            
            if line.startswith('#pos'):
                
                # runNum
                m = re.search('runNum=([0-9]+)',line)
                runNum = int(m.group(1))
                
                # initialize variables
                motes[runNum]     = []
                xcoord[runNum]    = {}
                ycoord[runNum]    = {}
                
                # motes
                m = re.findall('([0-9]+)\@\(([\.0-9]+),([\.0-9]+)\)\@([0-9]+)',line)
                for (id,x,y,rank) in m:
                    id       = int(id)
                    x        = float(x)
                    y        = float(y)
                    rank     = int(rank)
                    motes[runNum] += [{
                        'id':     id,
                        'x':      x,
                        'y':      y,
                        'rank':   rank,
                    }]
                    xcoord[runNum][id] = x
                    ycoord[runNum][id] = y
            
            if line.startswith('#links'):
                
                # runNum
                m = re.search('runNum=([0-9]+)',line)
                runNum = int(m.group(1))
                
                # create entry for this run
                links[runNum] = []
                
                # links
                m = re.findall('([0-9]+)-([0-9]+)@([\-0-9]+)dBm',line)
                for (moteA,moteB,rssi) in m:
                    links[runNum] += [{
                        'moteA':  int(moteA),
                        'moteB':  int(moteB),
                        'rssi':   int(rssi),
                    }]
    
    # verify integrity
    assert squareSide
    assert sorted(motes.keys())==sorted(links.keys())
    
    # print
    print 'done.'
    
    def plotMotes(thisax):
        # motes
        thisax.scatter(
            [mote['x'] for mote in motes[runNum] if mote['id']!=0],
            [mote['y'] for mote in motes[runNum] if mote['id']!=0],
            marker      = 'o',
            c           = 'white',
            s           = 10,
            lw          = 0.5,
            zorder      = 4,
        )
        thisax.scatter(
            [mote['x'] for mote in motes[runNum] if mote['id']==0],
            [mote['y'] for mote in motes[runNum] if mote['id']==0],
            marker      = 'o',
            c           = 'red',
            s           = 10,
            lw          = 0.5,
            zorder      = 4,
        )
    
    # plot topologies
    for runNum in sorted(motes.keys()):
        
        outfilename = infilemame.split('.')[0]+'_topology_runNumber_{}.png'.format(runNum)
        outfilepath = os.path.join(dir,outfilename)
        
        # print
        print 'Generating {0}...'.format(outfilename),
        
        #=== start new plot
        
        fig = matplotlib.pyplot.figure(figsize=(8,12), dpi=80)
        
        #=== plot 1: motes and IDs
        
        ax1 = fig.add_subplot(3,2,1,aspect='equal')
        ax1.set_xlim(xmin=0,xmax=squareSide)
        ax1.set_ylim(ymin=0,ymax=squareSide)
        
        # motes
        plotMotes(ax1)
        
        # id
        for mote in motes[runNum]:
            ax1.annotate(
                mote['id'],
                xy      = (mote['x']+0.01,mote['y']+0.01),
                color   = 'blue',
                size    = '6',
                zorder  = 3,
            )
        
        #=== plot 2: motes, rank and contour
        
        ax2 = fig.add_subplot(3,2,2,aspect='equal')
        ax2.set_xlim(xmin=0,xmax=squareSide)
        ax2.set_ylim(ymin=0,ymax=squareSide)
        
        # motes
        #plotMotes(ax2)
        
        # rank
        '''
        for mote in motes[runNum]:
            ax2.annotate(
                mote['rank'],
                xy      = (mote['x']+0.01,mote['y']-0.02),
                color   = 'black',
                size    = '6',
                zorder  = 2,
            )
        '''
        
        # contour
        x     = [mote['x']    for mote in motes[runNum]]
        y     = [mote['y']    for mote in motes[runNum]]
        z     = [mote['rank'] for mote in motes[runNum]]
        
        xi    = numpy.linspace(0,squareSide,100)
        yi    = numpy.linspace(0,squareSide,100)
        zi    = matplotlib.mlab.griddata(x,y,z,xi,yi)
        
        ax2.contour(xi,yi,zi,lw=0.1)
        
        #=== plot 3: links
        
        ax3 = fig.add_subplot(3,2,3,aspect='equal')
        ax3.set_xlim(xmin=0,xmax=squareSide)
        ax3.set_ylim(ymin=0,ymax=squareSide)
        
        # motes
        plotMotes(ax3)
        
        # links
        cmap       = matplotlib.pyplot.get_cmap('jet')
        cNorm      = matplotlib.colors.Normalize(
            vmin   = min([link['rssi'] for link in links[runNum]]),
            vmax   = max([link['rssi'] for link in links[runNum]]),
        )
        scalarMap  = matplotlib.cm.ScalarMappable(norm=cNorm, cmap=cmap)
        
        for link in links[runNum]:
            colorVal = scalarMap.to_rgba(link['rssi'])
            ax3.plot(
                [xcoord[runNum][link['moteA']],xcoord[runNum][link['moteB']]],
                [ycoord[runNum][link['moteA']],ycoord[runNum][link['moteB']]],
                color   = colorVal,
                zorder  = 1,
                lw      = 0.1,
            )
        
        #=== plot 4: TODO
        
        ax4 = fig.add_subplot(3,2,4,aspect='equal')
        ax4.set_xlim(xmin=0,xmax=squareSide)
        ax4.set_ylim(ymin=0,ymax=squareSide)
        
        # motes
        plotMotes(ax4)
        
        #=== plot 5: rssi vs. distance
        
        ax5 = fig.add_subplot(3,2,5)
        ax5.set_xlim(xmin=0,xmax=1000*squareSide)
        
        data_x = []
        data_y = []
        
        for numRun in links.keys():
            pos = {}
            for mote in motes[numRun]:
                pos[mote['id']] = (mote['x'],mote['y'])
            
            for l in links[numRun]:
                distance = 1000*math.sqrt(
                    (pos[l['moteA']][0] - pos[l['moteB']][0])**2 +
                    (pos[l['moteA']][1] - pos[l['moteB']][1])**2
                )
                rssi     = l['rssi']
                
                data_x += [distance]
                data_y += [rssi]
        
        ax5.scatter(
            data_x,
            data_y,
            marker      = '+',
            c           = 'blue',
            s           = 3,
            zorder      = 1,
        )
        ax5.plot(
            [0,1000*squareSide],
            [-101,-101],
            color       = 'red',
            zorder      = 2,
            lw          = 0.5,
        )
        
        #=== plot 6: waterfall (pdr vs rssi)
        
        ax6 = fig.add_subplot(3,2,6,aspect='equal')
        ax6.set_xlim(xmin=0,xmax=squareSide)
        ax6.set_ylim(ymin=0,ymax=squareSide)
        
        # motes
        plotMotes(ax6)
        
        #=== save and close plot
        
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
    for dir in os.listdir(DATADIR):
        for infilemame in glob.glob(os.path.join(DATADIR, dir,'*.dat')):
            
            # plot timelines
            for elemName in options['elemNames']:
                genTimelinePlots(
                    dir           = os.path.join(DATADIR, dir),
                    infilemame    = os.path.basename(infilemame),
                    elemName      = elemName,
                )
            
            # plot topologies
            genTopologyPlots(
                dir               = os.path.join(DATADIR, dir),
                infilemame        = os.path.basename(infilemame),
            )

if __name__=="__main__":
    main()
