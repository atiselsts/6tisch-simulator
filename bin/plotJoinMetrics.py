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
    bin the data files according to the withJoin and joinNumExchanges.

    Returns a dictionary of format:
    {
        (withJoin,joinNumExchanges): [
            filepath,
            filepath,
            filepath,
        ]
    }
    '''
    infilepaths = glob.glob(os.path.join(DATADIR, '**', '*.dat'))

    dataBins = {}
    for infilepath in infilepaths:
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
                else:
                    joinNumExchanges = 'NA'
            if withJoin: # add to the dictionary only if withJoin is 1
                if (withJoin, joinNumExchanges) not in dataBins:
                    dataBins[(withJoin, joinNumExchanges)] = []
                dataBins[(withJoin, joinNumExchanges)] += [infilepath]

    return dataBins

def plot_duration_vs_numMotes(dataBins):
    # duration of the join process is the ASN of the last node to have joined
    dictDurations = {}
    for ((withJoin, joinNumExchanges), filepaths) in dataBins.items():
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
                        if (joinNumExchanges, numMotes) not in dictDurations:
                            dictDurations[(joinNumExchanges,numMotes)] = []
                        dictDurations[(joinNumExchanges, numMotes)] += [duration]

    for ((joinNumExchanges,numMotes),perRunData) in dictDurations.items():
        (m,confint) = calcMeanConfInt(perRunData)
        dictDurations[(joinNumExchanges,numMotes)] = {
            'mean':      m,
            'confint':   confint,
        }


    joinNumExchanges = []
    numMotes = []
    for (joinNumExchange, numMote) in dictDurations.keys():
        joinNumExchanges += [joinNumExchange]
        numMotes += [numMote]
    joinNumExchanges = sorted(list(set(joinNumExchanges)))
    numMotes = sorted(list(set(numMotes)))

    # ===== plot

    fig = matplotlib.pyplot.figure()
    matplotlib.pyplot.xlabel('Number of motes')
    matplotlib.pyplot.ylabel('Duration of the join process (min)')

    for joinNumExchange in joinNumExchanges:
        x = numMotes
        y = [dictDurations[joinNumExchange, k]['mean'] for k in x]
        yerr = [dictDurations[joinNumExchange, k]['confint'] for k in x]
        matplotlib.pyplot.errorbar(
            x=x,
            y=y,
            yerr=yerr,
            label='Number of exchanges = {0}'.format(joinNumExchange)
        )
        matplotlib.pyplot.ylim(ymin=0, ymax=max(y) + 2)
        matplotlib.pyplot.xlim(xmin=0, xmax=max(x) + 2)
        matplotlib.pyplot.legend(loc='best', prop={'size': 10})
    matplotlib.pyplot.savefig(os.path.join(DATADIR, 'duration_vs_numMotes.png'))
    matplotlib.pyplot.savefig(os.path.join(DATADIR, 'duration_vs_numMotes.eps'))
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

    # plot join duration vs num motes
    plot_duration_vs_numMotes(dataBins)




if __name__ == "__main__":
    main()
