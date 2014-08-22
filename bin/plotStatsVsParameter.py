#!/usr/bin/python
'''
\brief Plots statistics with a selected parameter.

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
log = logging.getLogger('plotStatsVsParameter')
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
        type       = str,
        default    = 'numMotes',
        help       = 'Name of the elements to be used as x axis.',
    )
    
    options        = parser.parse_args()
    
    return options.__dict__

def calce2ePDR(dir,infilename,elemName):
    
    infilepath     = os.path.join(dir,infilename)
        
    # find xAxis, numCyclesPerRun    
    with open(infilepath,'r') as f:
        for line in f:
            
            if line.startswith('##'):
                
                # elem
                m = re.search(elemName+'\s+=\s+([\.0-9]+)',line)
                if m:
                    elem               = float(m.group(1))
                
                # numCyclesPerRun
                m = re.search('numCyclesPerRun\s+=\s+([\.0-9]+)',line)
                if m:
                    numCyclesPerRun    = int(m.group(1))
    
    # find appGenerated, appReachesDagroot, txQueueFill, colnumcycle
    with open(infilepath,'r') as f:
        for line in f:
            if line.startswith('# '):
                elems                   = re.sub(' +',' ',line[2:]).split()
                numcols                 = len(elems)
                colnumappGenerated      = elems.index('appGenerated')
                colnumappReachesDagroot = elems.index('appReachesDagroot')
                colnumtxQueueFill       = elems.index('txQueueFill')
                colnumcycle             = elems.index('cycle')
                break
    
    assert colnumappGenerated
    assert colnumappReachesDagroot
    assert colnumtxQueueFill
    assert colnumcycle
    
    # parse data
    e2ePDR = []
    totalGenerated = 0
    totalReaches   = 0
    with open(infilepath,'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            m = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
            appGenerated        = int(m.group(colnumappGenerated+1))
            appReachesDagroot   = int(m.group(colnumappReachesDagroot+1))
            txQueueFill         = int(m.group(colnumtxQueueFill+1))      
            cycle               = int(m.group(colnumcycle+1))
            
            totalGenerated     += appGenerated
            totalReaches       += appReachesDagroot
            
            if cycle == numCyclesPerRun-1:
                e2ePDR         += [float(totalReaches)/float(totalGenerated-txQueueFill)]
                totalGenerated  = 0
                totalReaches    = 0
    
    return elem, e2ePDR
            
def calcBatteryLife(dir,infilename,elemName):

    CAPACITY = 2200 # in mAh
    
    infilepath     = os.path.join(dir,infilename)

    with open(infilepath,'r') as f:
        for line in f:
            
            if line.startswith('##'):
                # elem
                m = re.search(elemName+'\s+=\s+([\.0-9]+)',line)
                if m:
                    elem               = float(m.group(1))

                # slotDuration
                m = re.search('slotDuration\s+=\s+([\.0-9]+)',line)
                if m:
                    slotDuration       = float(m.group(1))

                # slotframeLength
                m = re.search('slotframeLength\s+=\s+([\.0-9]+)',line)
                if m:
                    slotframeLength    = int(m.group(1))
        
    minBatteryLives = []
    with open(infilepath,'r') as f:
        for line in f:
            
            if line.startswith('#aveChargePerCycle'):
                
                # runNum
                m      = re.search('runNum=([0-9]+)',line)
                runNum = int(m.group(1))
                                
                # maximum average charge
                m           = re.findall('([0-9]+)@([\.0-9]+)',line)
                lm          = [list(t) for t in m if int(list(t)[0]) != 0] # excluding DAG root
                maxIdCharge = max(lm, key=lambda x: float(x[1]))
                maxCurrent  = float(maxIdCharge[1])*10**(-3)/(slotDuration*slotframeLength) # convert from uC/cycle to mA
                
                # battery life
                minBatteryLives += [CAPACITY/maxCurrent/24] # mAh/mA/(h/day), in day
                
    return elem, minBatteryLives    

def calcLatency(dir,infilename,elemName):

    infilepath     = os.path.join(dir,infilename)

    with open(infilepath,'r') as f:
        for line in f:
            
            if line.startswith('##'):

                # elem
                m = re.search(elemName+'\s+=\s+([\.0-9]+)',line)
                if m:
                    elem               = float(m.group(1))
                
                # numCyclesPerRun
                m = re.search('numCyclesPerRun\s+=\s+([\.0-9]+)',line)
                if m:
                    numCyclesPerRun    = int(m.group(1))


    # find appReachesDagroot, aveLatency
    with open(infilepath,'r') as f:
        for line in f:
            if line.startswith('# '):
                elems                   = re.sub(' +',' ',line[2:]).split()
                numcols                 = len(elems)
                colnumappReachesDagroot = elems.index('appReachesDagroot')
                colnumaveLatency        = elems.index('aveLatency')
                colnumcycle             = elems.index('cycle')
                break
    
    assert colnumappReachesDagroot
    assert colnumaveLatency
    assert colnumcycle
    
    # parse data
    latencies              = []
    sumaveLatency          = 0
    sumappReachesDagroot   = 0
    with open(infilepath,'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            m                          = re.search('\s+'.join(['([\.0-9]+)']*numcols),line.strip())
            appReachesDagroot          = int(m.group(colnumappReachesDagroot+1))
            aveLatency                 = float(m.group(colnumaveLatency+1))      
            cycle                      = int(m.group(colnumcycle+1))
            
            sumappReachesDagroot      += appReachesDagroot
            sumaveLatency             += aveLatency*appReachesDagroot
            
            if cycle == numCyclesPerRun-1:
                latencies             += [sumaveLatency/sumappReachesDagroot]
                sumaveLatency          = 0
                sumappReachesDagroot   = 0

    return elem, latencies
    
def genMotesPlots(vals, dir, outfilename):

    outfilepath    = os.path.join(dir,outfilename)

    # print
    print 'Generating {0}...'.format(outfilename),
    
    # calculate mean and confidence interval
    meanPerNumMotes    = {}
    confintPerNumMotes = {}
    for (k,v) in vals.items():
        a          = 1.0*numpy.array(v)
        n          = len(a)
        se         = scipy.stats.sem(a)
        m          = numpy.mean(a)
        confint    = se * scipy.stats.t._ppf((1+CONFINT)/2., n-1)
        meanPerNumMotes[k]      = m
        confintPerNumMotes[k]   = confint
    
    # plot
    x         = sorted(meanPerNumMotes.keys())
    y         = [meanPerNumMotes[k] for k in x]
    yerr      = [confintPerNumMotes[k] for k in x]
    matplotlib.pyplot.figure()
    matplotlib.pyplot.errorbar(x,y,yerr=yerr)
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
    
    # parse CLI option
    options      = parseCliOptions()
    elemName     = options['elemNames']
    e2ePdrs      = {}
    batteryLives = {}
    latencies    = {}

    # assumed that each data file uses same parameters other than elemName 
     
    for dir in os.listdir(DATADIR):
        for infilename in glob.glob(os.path.join(DATADIR, dir,'*.dat')):

            elem, e2ePdrEachRun = calce2ePDR(
                dir                = os.path.join(DATADIR, dir),
                infilename         = os.path.basename(infilename),
                elemName           = elemName
            )
            
            e2ePdrs[elem] = e2ePdrEachRun
            
            elem, batteryLifeEachRun = calcBatteryLife(
                dir                = os.path.join(DATADIR, dir),
                infilename         = os.path.basename(infilename),
                elemName           = elemName
            )
            
            batteryLives[elem] = batteryLifeEachRun

            elem, latencyEachRun = calcLatency(
                dir                = os.path.join(DATADIR, dir),
                infilename         = os.path.basename(infilename),
                elemName           = elemName
            )
            
            latencies[elem] = latencyEachRun


    outfilename    = 'output_e2ePDR_{}.png'.format(elemName)
    
    # plot figure for e2ePDR    
    genMotesPlots(
        e2ePdrs,
        dir            = DATADIR,
        outfilename    = outfilename
    )

    outfilename    = 'output_battery_{}.png'.format(elemName)

    # plot figure for battery life    
    genMotesPlots(
        batteryLives,
        dir            = DATADIR,
        outfilename    = outfilename
    )
    
    outfilename    = 'output_latency_{}.png'.format(elemName)

    # plot figure for latency    
    genMotesPlots(
        latencies,
        dir            = DATADIR,
        outfilename    = outfilename
    )
    
    
if __name__=="__main__":
    main()
