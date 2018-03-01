import pandas as pd
import re

def read_dataset(file_name):
    """
    Read the dataset and returs the simulation data and parameters
    :param string file_name:
    :return: A Pandas dataframe containing the data and a dict containings the simulation parameters
    :rtype: pandas.Dataframe & dict
    """

    column_names = None
    parameters = {}

    # read column names
    with open(file_name, 'r') as f:
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
        raise Exception("Could not read column names from file {0}".format(file_name))

    # read data (ignoring comment lines)
    data = pd.read_csv(file_name, sep='[ ^]+', comment='#', names=column_names, engine='python')

    return data, parameters

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
