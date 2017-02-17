#!/usr/bin/python
'''
\brief Plots statistics of the join process.

\author Malisa Vucinic <malishav@gmail.com>
'''

#============================ imports =========================================
import logging
import glob
import os
import re
import numpy
import scipy
import scipy.stats
import matplotlib.pyplot
#============================ logging =========================================

class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('plotJoinMetrics')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

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

#============================ body ============================================
def binDataFiles():
    '''
    bin the data files according to the withJoin, joinNumExchanges, beaconProbability and slotframeLength.

    Returns a dictionary of format:
    {
        (withJoin,joinNumExchanges, beaconProbability, slotframeLength): [
            filepath,
            filepath,
            filepath,
        ]
    }
    '''
    infilepaths = glob.glob(os.path.join(DATADIR, '**', '*.dat'))

    dataBins = {}
    for infilepath in infilepaths:

        withJoin = None
        joinNumExchanges = None
        beaconProbability = None
        slotframeLength = None

        with open(infilepath, 'r') as f:
            for line in f:
                if not line.startswith('## ') or not line.strip():
                    continue
                # withJoin
                m = re.search('withJoin\s+=\s+([\.0-9]+)', line)
                if m:
                    withJoin = int(m.group(1))
                # joinNumExchanges
                m = re.search('joinNumExchanges\s+=\s+([\.0-9]+)', line)
                if m:
                    joinNumExchanges = int(m.group(1))
                # beaconProbability
                m = re.search('beaconProbability\s+=\s+([\.0-9]+)', line)
                if m:
                    beaconProbability = float(m.group(1))
                # slotframeLength
                m = re.search('slotframeLength\s+=\s+([\.0-9]+)', line)
                if m:
                    slotframeLength = int(m.group(1))
            if withJoin and joinNumExchanges and beaconProbability and slotframeLength:
                if (withJoin, joinNumExchanges, beaconProbability, slotframeLength) not in dataBins:
                    dataBins[(withJoin, joinNumExchanges, beaconProbability, slotframeLength)] = []
                dataBins[(withJoin, joinNumExchanges, beaconProbability, slotframeLength)] += [infilepath]

    return dataBins

def plot_duration(dataBins):
    # duration of the join process is the ASN of the last node to have joined
    dictDurations = {}
    for ((withJoin, joinNumExchanges, beaconPeriod, slotframeLength), filepaths) in dataBins.items():
        for filepath in filepaths:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.startswith('## '):
                        # numMotes
                        m = re.search('numMotes\s+=\s+([0-9]+)', line)
                        if m:
                            numMotes = int(m.group(1))
                    if line.startswith('#join'):
                        duration = float(max(parse_join_asns_per_run(line)) * 10.0 / 1000 / 60 )
                        if (joinNumExchanges, beaconPeriod, slotframeLength, numMotes) not in dictDurations:
                            dictDurations[(joinNumExchanges,beaconPeriod, slotframeLength, numMotes)] = []
                        dictDurations[(joinNumExchanges, beaconPeriod, slotframeLength, numMotes)] += [duration]

    for ((joinNumExchanges,beaconPeriod, slotframeLength, numMotes),perRunData) in dictDurations.items():
        (m,confint) = calcMeanConfInt(perRunData)
        dictDurations[(joinNumExchanges, beaconPeriod, slotframeLength, numMotes)] = {
            'mean':      m,
            'confint':   confint,
        }

    joinNumExchanges = []
    numMotes = []
    beaconPeriods = []
    slotframeLengths = []
    for (joinNumExchange, beaconPeriod, slotframeLength, numMote) in dictDurations.keys():
        joinNumExchanges += [joinNumExchange]
        numMotes += [numMote]
        beaconPeriods += [beaconPeriod]
        slotframeLengths += [slotframeLength]
    joinNumExchanges = sorted(list(set(joinNumExchanges)))
    beaconPeriods = sorted(list(set(beaconPeriods)))
    slotframeLengths = sorted(list(set(slotframeLengths)))
    numMotes = sorted(list(set(numMotes)))

    for je in joinNumExchanges:
        for bp in beaconPeriods:
            for sl in slotframeLengths:
                for nm in numMotes:
                    if (je, bp, sl, nm) not in dictDurations:
                        dictDurations[(je, bp, sl, nm)] = {
                            'mean': numpy.nan,
                            'confint': 0,
                        }

    # ===== plot

    # duration vs number of motes
    fig = matplotlib.pyplot.figure()

    for slotframeLength in slotframeLengths:
        for beaconPeriod in beaconPeriods:
            for joinNumExchange in joinNumExchanges:
                x = numMotes
                y = [dictDurations[joinNumExchange, beaconPeriod, slotframeLength, k]['mean'] for k in x]
                yerr = [dictDurations[joinNumExchange, beaconPeriod, slotframeLength, k]['confint'] for k in x]
                matplotlib.pyplot.errorbar(
                    x=x,
                    y=y,
                    yerr=yerr,
                    label='Number of exchanges = {0}'.format(joinNumExchange)
                )
                matplotlib.pyplot.ylim(ymin=0, ymax=max(y) + 2)
                matplotlib.pyplot.xlim(xmin=0, xmax=max(x) + 2)
                matplotlib.pyplot.legend(loc='best', prop={'size': 10})
            matplotlib.pyplot.xlabel('Number of motes')
            matplotlib.pyplot.ylabel('Duration of the join process (min)')
            matplotlib.pyplot.savefig(os.path.join(DATADIR, 'duration_vs_numMotes_beaconPeriod_{0}_slotframeLength_{1}.eps'.format(beaconPeriod, slotframeLength)))
            matplotlib.pyplot.close('all')

    # duration vs beaconPeriod
    fig = matplotlib.pyplot.figure()

    for slotframeLength in slotframeLengths:
        for joinNumExchange in joinNumExchanges:
            for nm in numMotes:
                x = beaconPeriods
                y = [dictDurations[joinNumExchange, k, slotframeLength, nm]['mean'] for k in x]
                yerr = [dictDurations[joinNumExchange, k, slotframeLength, nm]['confint'] for k in x]
                matplotlib.pyplot.errorbar(
                    x=x,
                    y=y,
                    yerr=yerr,
                    label='Number of motes = {0}'.format(nm)
                )
                matplotlib.pyplot.ylim(ymin=0, ymax=max(y) + 2)
                matplotlib.pyplot.xlim(xmin=0, xmax=max(x) + 2)
                matplotlib.pyplot.legend(loc='best', prop={'size': 10})
            matplotlib.pyplot.xlabel('Beacon Period (s)')
            matplotlib.pyplot.ylabel('Duration of the join process (min)')
            matplotlib.pyplot.savefig(os.path.join(DATADIR, 'duration_vs_beaconPeriod_numExchanges_{0}_slotframeLength_{1}.eps'.format(joinNumExchange,slotframeLength)))
            matplotlib.pyplot.close('all')

def plot_duration_cdf(dataBins):
    dictDurations = {}
    for ((withJoin, joinNumExchanges, beaconPeriod, slotframeLength), filepaths) in dataBins.items():
        for filepath in filepaths:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.startswith('## '):
                        # numMotes
                        m = re.search('numMotes\s+=\s+([0-9]+)', line)
                        if m:
                            numMotes = int(m.group(1))
                    if line.startswith('#join'):
                        duration = [i * 10.0 / 1000 / 60 for i in parse_join_asns_per_run(line) if i != 0]
                        if (joinNumExchanges, beaconPeriod, slotframeLength, numMotes) not in dictDurations:
                            dictDurations[(joinNumExchanges, beaconPeriod, slotframeLength, numMotes)] = []
                        dictDurations[(joinNumExchanges, beaconPeriod, slotframeLength, numMotes)] += duration

    joinNumExchanges = []
    numMotes = []
    beaconPeriods = []
    slotframeLengths = []
    for (joinNumExchange, beaconPeriod, slotframeLength, numMote) in dictDurations.keys():
        joinNumExchanges += [joinNumExchange]
        numMotes += [numMote]
        beaconPeriods += [beaconPeriod]
        slotframeLengths += [slotframeLength]
    joinNumExchanges = sorted(list(set(joinNumExchanges)))
    beaconPeriods = sorted(list(set(beaconPeriods)))
    slotframeLengths = sorted(list(set(slotframeLengths)))
    numMotes = sorted(list(set(numMotes)))

    fig = matplotlib.pyplot.figure()

    for slotframeLength in slotframeLengths:
        for beaconPeriod in beaconPeriods:
            for joinNumExchange in joinNumExchanges:
                for numMote in numMotes:
                    if (joinNumExchange, beaconPeriod, slotframeLength, numMote) in dictDurations:
                        sortedAsns = numpy.sort(dictDurations[(joinNumExchange, beaconPeriod, slotframeLength, numMote)])
                        yvals = numpy.arange(len(sortedAsns))/float(len(sortedAsns) - 1)
                        matplotlib.pyplot.plot(sortedAsns, yvals, label='Number of motes = {0}'.format(numMote))
                matplotlib.pyplot.xlabel('Duration of the join process (min)')
                matplotlib.pyplot.ylabel('CDF')
                matplotlib.pyplot.legend(loc='best', prop={'size': 10})
                matplotlib.pyplot.ylim(ymin=0, ymax=1)
                matplotlib.pyplot.savefig(os.path.join(DATADIR, 'cdf_{0}_exchanges_beaconPeriod_{1}_slotframeLength_{2}.eps'.format(joinNumExchange, beaconPeriod, slotframeLength)))
                matplotlib.pyplot.close('all')


def calcMeanConfInt(vals):
    assert type(vals) == list
    for val in vals:
        assert type(val) in [int, float]

    a = 1.0 * numpy.array(vals)
    se = scipy.stats.sem(a)
    m = numpy.mean(a)
    confint = se * scipy.stats.t._ppf((1 + CONFINT) / 2., len(a) - 1)

    return (m, confint)

def parse_join_asns_per_run(line):
    '''
    Returns a list of join ASNs
    '''
    assert line.startswith('#join')
    joinAsns = []
    for word in line.split():
        if '@' in word:
            joinAsns += [int(word.split('@')[1])]

    return joinAsns
# ============================ main ============================================
def main():
    dataBins = binDataFiles()

    # plot join duration vs num motes and vs beaconPeriod
    plot_duration(dataBins)

    # plot cdfs for each joinNumExchange run
    plot_duration_cdf(dataBins)



if __name__ == "__main__":
    main()
