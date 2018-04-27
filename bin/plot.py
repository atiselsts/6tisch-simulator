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

# third party
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================ main ===========================================

def main(options):

    # init
    data = {}
    yparam, key = options.yparam.split(';')

    # chose lastest results
    subfolder = sorted(os.listdir(options.inputfolder))[-1]

    # read config file
    config_path = os.path.join(options.inputfolder, subfolder, 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    # load data
    for file_path in glob.glob(os.path.join(options.inputfolder, subfolder, '*.dat')):
        first_combination = config["settings"]["combination"].keys()[0]
        with open(file_path, 'r') as f:
            file_settings = json.loads(f.readline())
            curr_combination = file_settings[first_combination]
            data[curr_combination] = []
            for line in f:
                log = json.loads(line)
                if log['type'] == yparam:
                    data[curr_combination].append(log[key])

    plt.boxplot(data.values())
    plt.xticks(range(1, len(data) + 1), data.keys())
    savefig(options.outputfolder, yparam)
    print "Plots are saved in the {0} folder.".format(options.outputfolder)

# =========================== helpers =========================================

def savefig(output_folder, output_name, output_format="png"):
    # check if output folder exists and create it if not
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    # save the figure
    plt.savefig(os.path.join(output_folder, output_name + "." + output_format),
                bbox_inches='tight',
                pad_inches=0,
                format=output_format)

def parse_args():
    # parse options
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputfolder',
                        help='The simulation result folder.',
                        default='simData')
    parser.add_argument('--outputfolder',
                        help='The plots output folder.',
                        default='simPlots')
    parser.add_argument('-x',
                        '--xparam',
                        help='The x-axis parameter',
                        type=str,
                        default='slotframe_iteration')
    parser.add_argument('-y',
                        '--yparam',
                        help='The y-axis parameter',
                        type=str,
                        default='charge_consumed;charge')
    parser.add_argument('--xlabel',
                        help='The x-axis label',
                        type=str,
                        default=None)
    parser.add_argument('--ylabel',
                        help='The y-axis label',
                        type=str,
                        default=None)
    parser.add_argument('--show',
                        help='Show the plots.',
                        action='store_true',
                        default=None)
    return parser.parse_args()

if __name__ == '__main__':

    options = parse_args()

    main(options)
