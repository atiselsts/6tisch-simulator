"""
Plot a stat over another stat.

Example:
    python plot.py --inputfolder simData/numMotes_50/ -x chargeConsumed --y aveLatency
"""

# =========================== imports =========================================

# standard
import sys
import argparse

# third party
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

# project
import datasethelper as dh

# ============================ main ===========================================

def main(options):
    # read dataset
    dataset_list = dh.read_dataset_folder(options.inputfolder)

    # plot each dataset
    for dataset in dataset_list:

        # group dataset by bins
        delta = dataset['stats'][options.xparam].max() - dataset['stats'][options.xparam].min()
        bin_size = 10.0  # size of the bin in %
        df_grouped = dataset['stats'].groupby(
            dataset['stats'][options.xparam].apply(lambda x: (delta/bin_size) * round(x/(delta/bin_size)))
        )

        # calculate mean and std
        mean_index = [name for name, group in df_grouped]
        mean_param = [group[options.yparam].mean() for name, group in df_grouped]
        std_param = [group[options.yparam].std() for name, group in df_grouped]

        # plot errobar
        plt.errorbar(
            x = mean_index,
            y = mean_param,
            yerr = std_param,
            label=dataset['name'],
            capsize=3
        )

    plt.xlabel(options.xlabel if options.xlabel else options.xparam)
    plt.ylabel(options.ylabel if options.ylabel else options.yparam)
    plt.grid(True)
    plt.legend()

    output_file = "_".join([options.yparam, options.xparam])
    dh.savefig(options.outputfolder, output_file)

    if options.show:
        plt.show()

# =========================== plot stuff ======================================

def plot_stuff(options):
    dataset = dh.read_dataset_folder(options.inputfolder)[0]

    plot_allstats_vs_cycle(dataset, options)
    plot_pdr_hist(dataset, options)

    print "Plots are saved in {0} folder.".format(options.outputfolder)

def plot_allstats_vs_cycle(dataset, options):
    # create subplots
    fig, ax = plt.subplots(nrows=len(dataset["stats"].keys()),
                           sharex=True,
                           figsize=(10, 50))

    # plot
    df = dataset["stats"]
    stat_mean = df.groupby(["cycle"]).mean().reset_index()
    for i, stat in enumerate(dataset["stats"]):
        ax[i].plot(stat_mean.cycle, stat_mean[stat])
        ax[i].set_xlabel(stat)
    plt.tight_layout()
    dh.savefig(options.outputfolder, 'allstats_vs_cycle')
    plt.close()

def plot_pdr_hist(dataset, options):
    # filter data
    df = dataset["stats"][dataset["stats"]["appGenerated"] > 0]

    # calculate PDR
    df = df.assign(pdr=pd.Series(df["appReachesDagroot"] / df["appGenerated"]))

    # plot
    plt.hist(df.pdr, bins=[i*0.1 for i in range(0, 11)])
    plt.title("PDR Distribution")
    dh.savefig(options.outputfolder, 'pdr_hist')
    plt.close()

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
                        default='cycle')
    parser.add_argument('-y',
                        '--yparam',
                        help='The y-axis parameter',
                        type=str,
                        default='numDedicatedCells')
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

    if len(sys.argv) > 1:
        main(options)
    else:
        plot_stuff(options)
