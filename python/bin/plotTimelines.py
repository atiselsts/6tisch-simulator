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
log = logging.getLogger('plotTimelines')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import os
import re
import glob
import sys

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
            'numAccumScheduledCells',
            'numAccumScheduledCollisions',
        ],
        help       = 'Name of the elements to generate timeline figures for.',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__

def genFig(dir,infile,elemName):
    
    outfile   = os.path.join(dir,infile.split('.')[0]+'_{}.png'.format(elemName))
    filepath  = os.path.join(dir,infile)
    
    # print
    print 'Generating {0}...'.format(outfile),
    
    # find colnumelem, colnumcycle, colnumrunNum
    with open(filepath,'r') as f:
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
    with open(filepath,'r') as f:
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
    matplotlib.pyplot.savefig(outfile)
    matplotlib.pyplot.close()
    
    # print
    print 'done.'

def genTopologyFigs(dir,infile):
    
    
    filepath  = os.path.join(dir,infile)
    
    # print
    print 'Generating Topologies...', 
    
    # parse data
    topologies={}
    with open(filepath,'r') as f:
        for line in f:
            if line.startswith('#pos'):
                rawdata=line.strip().split(' ')
                runNum=int(rawdata[1].split('=')[1])
                topologies[runNum]={'motes':{}}
                for node in rawdata[2:]:
                    nodeParam=node.split('@')
                    topologies[runNum]['motes'][int(nodeParam[0])]={'position':eval(nodeParam[1]), 'rank':int(nodeParam[2])}
            elif line.startswith('#links'):
                rawdata=line.strip().split(' ')
                runNum=int(rawdata[1].split('=')[1])
                if topologies.has_key(runNum):
                    topologies[runNum]['links']={}
                    for link in rawdata[2:]:
                        node1, further=link.split('->')
                        node2, further=further.split('@')
                        rssi=further[:-3]
                        topologies[runNum]['links'][(int(node1), int(node2))]=float(rssi)
            else:
                continue
    
    # plot topologies
    for runNum, topology in topologies.iteritems():
        if topology.has_key('links'):
            matplotlib.pyplot.figure()
            xx=[topology['motes'][mote]['position'][0] for mote in sorted(topology['motes'].keys())]
            yy=[topology['motes'][mote]['position'][1] for mote in sorted(topology['motes'].keys())]
            matplotlib.pyplot.scatter(xx,yy,marker='o', c='w', s=50, lw=0.5, zorder=1)
            for mote in sorted(topology['motes'].keys()):
                position=numpy.array(topology['motes'][mote]['position'])
                matplotlib.pyplot.annotate(str(mote), position+numpy.array([0, 0.02]), color='k', size='small', weight='semibold', zorder=3)
                matplotlib.pyplot.annotate(str(topology['motes'][mote]['rank']), position+numpy.array([0, -0.04]), color='r', size='small', zorder=3)
            for link in sorted(topology['links'].keys()):
                matplotlib.pyplot.plot(\
                                        [topology['motes'][link[0]]['position'][0], topology['motes'][link[1]]['position'][0]], \
                                        [topology['motes'][link[0]]['position'][1], topology['motes'][link[1]]['position'][1]], \
                                        color='g', zorder=0
                                        )
#                position=(
#                                (topology['motes'][link[0]]['position'][0] + topology['motes'][link[1]]['position'][0])/2,  \
#                                (topology['motes'][link[0]]['position'][1] + topology['motes'][link[1]]['position'][1])/2
#                                )
#                matplotlib.pyplot.annotate(str(topology['links'][link]), position, color='b', size='small', zorder=3)
            matplotlib.pyplot.savefig(os.path.join(dir,infile.split('.')[0]+'_topology_{}.png'.format(runNum)))
            matplotlib.pyplot.close()
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
        for infile in glob.glob(os.path.join(DATADIR, dir,'*.dat')):
            for elemName in options['elemNames']:
                genFig(
                    dir      = os.path.join(DATADIR, dir),
                    infile   = os.path.basename(infile),
                    elemName = elemName,
                )
                genTopologyFigs(
                    dir      = os.path.join(DATADIR, dir),
                    infile   = os.path.basename(infile),              
                )

if __name__=="__main__":
    main()
