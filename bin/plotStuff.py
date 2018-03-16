#!/usr/bin/python
"""
\brief Plots timelines and topology figures from collected simulation data.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
"""

# standard libraries
import os

# third party libraries
import matplotlib.pyplot as plt
import pandas as pd

# local libraries
import datasetreader

# =========================== defines =========================================

DATADIR       = 'simData'

# =========================== plot scripts ====================================

def plot_allstats_vs_cycle(dataset):
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
    plt.savefig(os.path.join(DATADIR, 'allstats_vs_cycle.png'),
                bbox_inches='tight',
                pad_inches=0)
    plt.close()

def plot_pdr_hist(dataset):
    # filter data
    df = dataset["stats"][dataset["stats"]["appGenerated"] > 0]

    # calculate PDR
    df = df.assign(pdr=pd.Series(df["appReachesDagroot"] / df["appGenerated"]))

    # plot
    plt.hist(df.pdr, bins=[i*0.1 for i in range(0, 11)])
    plt.title("PDR Distribution")
    plt.savefig(os.path.join(DATADIR, 'pdr_hist.png'),
                bbox_inches='tight',
                pad_inches=0)
    plt.close()

#============================ main ============================================

def main():

    dataset = datasetreader.read_dataset_folder(DATADIR)

    plot_allstats_vs_cycle(dataset)

    plot_pdr_hist(dataset)

if __name__ == "__main__":
    main()
