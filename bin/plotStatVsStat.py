"""
Plot a stat over another stat.

Example:
    python plotStatVsStat.py simData/numMotes_50/output.dat --first_stat chargeConsumed --second_stat aveLatency
"""
import argparse
import matplotlib.pyplot as plt
import datasetreader

def main(options):
    # read dataset
    df, stats = datasetreader.read_dataset(options.input_file)

    # plot
    df.plot(x=options.first_stat, y=options.second_stat, style='+', legend=False)
    plt.xlabel(options.first_stat)
    plt.ylabel(options.second_stat)
    plt.grid(True)
    plt.show()

if __name__ == '__main__':
    # parse options
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='The simulation result file.')
    parser.add_argument('--first_stat',
                        help='The first parameter (x axis)',
                        type=str,
                        default='chargeConsumed')
    parser.add_argument('--second_stat',
                        help='The second parameter (y axix)',
                        type=str,
                        default='aveLatency')
    options = parser.parse_args()

    main(options)
