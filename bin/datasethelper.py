import re
import glob
import os

import pandas as pd
import matplotlib.pyplot as plt

def read_dataset_folder(folder_path):
    """
    Read the dataset folder and returns a list of datasets.
    Each dataset is a dict of the following format:
      {
        'stats': a pandas Dataframe containing the simulations statistics,
        'params': a dict containing the simulation parameters
      }
    :param string folder_path:
    :return: the list of datasets
    :rtype: list
    """

    # init results
    dataset_list = []

    for subfolder in os.listdir(folder_path):
        file_path_list = glob.glob(os.path.join(folder_path, subfolder, '*.dat'))
        merged_params = None
        dataframe_list = []

        # read files and concatenate results
        for file_path in file_path_list:
            # read dataset file
            stats, params = read_dataset_file(file_path)

            # add cpuId column
            stats['cpuId'] = params['cpuID']

            # concatenate stats
            dataframe_list.append(stats)

            # merge simulation parameters
            del params['cpuID']
            if merged_params is None:
                merged_params = params
            else:
                assert merged_params == params

        merged_stats = pd.concat(dataframe_list)
        merged_stats.sort_values(["cycle"], inplace=True)
        dataset_list.append({
            "stats": merged_stats,
            "params": merged_params,
            "name": subfolder
        })
    return dataset_list

def read_dataset_file(file_path):
    """
    Read the dataset and returns the simulation stats and parameters
    :param string file_path:
    :return: A Pandas Dataframe containing the stats and a dict containing the parameters
    :rtype: pandas.Dataframe & dict
    """

    column_names = None
    parameters = {}

    # read column names
    with open(file_path, 'r') as f:
        for line in f:
            # get stats
            if line.startswith('## '):
                key, val = get_parameter_from_line(line)
                if key is not None:
                    parameters.update({key: val})

            # get columns header
            if line.startswith('# '):
                column_names = line.strip().split(" ")[1:]
                break

    if column_names is None:
        raise Exception("Could not read column names from file {0}".format(file_path))

    # read stats (ignoring comment lines)
    stats = pd.read_csv(file_path, sep='[ ^]+', comment='#', names=column_names,
                        engine='python')

    return stats, parameters

def get_parameter_from_line(line):
    """Split line and return the parameter key and value"""
    stat_name = None
    stat_value = None

    # extract key and value from line
    m = re.findall(r'\w+\s+=\s+.+', line)
    if len(m) > 0:
        m = m[0].replace(" ", "").split("=")
        if len(m) == 2:
            stat_name = m[0]
            stat_value = m[1]

    # try to convert the parameter value
    if stat_value.isdigit():
        stat_value = int(stat_value)
    elif isfloat(stat_value):
        stat_value = float(stat_value)
    elif islist(stat_value):
        stat_value = stat_value[1:-1].replace("'", "").split(",")

    return stat_name, stat_value

def isfloat(str):
    """check if the string can be converted to a float"""
    try:
        float(str)
        return True
    except ValueError:
        return False

def islist(str):
    """check if the string can be converted to a list"""
    if str[0] == '[' and str[-1] == ']':
        return True
    else:
        return False

def savefig(output_folder, output_name, output_format="png"):
    # check if output folder exists and create it if not
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    # save the figure
    plt.savefig(os.path.join(output_folder, output_name + "." + output_format),
                bbox_inches='tight',
                pad_inches=0,
                format=output_format)
