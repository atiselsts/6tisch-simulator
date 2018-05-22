"""
Plot a stat over another stat.

Example:
    python plot.py --inputfolder simData/numMotes_50/ -x chargeConsumed --y aveLatency
"""

# =========================== imports =========================================

# standard
import os
import argparse
import json
import glob
from collections import OrderedDict

# third party
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================ defines ========================================

KPIS = [
    'latency_max_s',
    'latency_avg_s',
    'lifetime_AA_years',
    'sync_time_s',
    'join_time_s',
    'upstream_num_lost'
]

# ============================ main ===========================================

def main(options):

    # init
    data = OrderedDict()

    # chose lastest results
    subfolders = list(
        map(lambda x: os.path.join(options.inputfolder, x),
            os.listdir(options.inputfolder)
        )
    )
    subfolder = max(subfolders, key=os.path.getmtime)

    for key in options.kpis:
        # load data
        for file_path in sorted(glob.glob(os.path.join(subfolder, '*.kpi'))):
            curr_combination = os.path.basename(file_path)[:-8] # remove .dat.kpi
            with open(file_path, 'r') as f:

                # read kpi file
                kpis = json.load(f)

                # init data list
                data[curr_combination] = []

                # fill data list
                for run in kpis.itervalues():
                    for mote in run.itervalues():
                        if key in mote:
                            data[curr_combination].append(mote[key])

        # plot
        plt.boxplot(data.values())
        plt.xticks(range(1, len(data) + 1), data.keys())
        plt.ylabel(key)
        savefig(subfolder, key)
        plt.clf()
    print "Plots are saved in the {0} folder.".format(subfolder)

# =========================== helpers =========================================

def savefig(output_folder, output_name, output_format="png"):
    # check if output folder exists and create it if not
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    # save the figure
    plt.savefig(
        os.path.join(output_folder, output_name + "." + output_format),
        bbox_inches     = 'tight',
        pad_inches      = 0,
        format          = output_format,
    )

def parse_args():
    # parse options
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--inputfolder',
        help       = 'The simulation result folder.',
        default    = 'simData',
    )
    parser.add_argument(
        '-k','--kpis',
        help       = 'The kpis to plot',
        type       = list,
        default    = KPIS
    )
    parser.add_argument(
        '--xlabel',
        help       = 'The x-axis label',
        type       = str,
        default    = None,
    )
    parser.add_argument(
        '--ylabel',
        help       = 'The y-axis label',
        type       = str,
        default    = None,
    )
    parser.add_argument(
        '--show',
        help       = 'Show the plots.',
        action     = 'store_true',
        default    = None,
    )
    return parser.parse_args()

if __name__ == '__main__':

    options = parse_args()

    main(options)
