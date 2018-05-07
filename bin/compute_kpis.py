# =========================== adjust path =====================================

import os
import sys

if __name__ == '__main__':
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..'))

# ========================== imports =========================================

import json
import glob

from SimEngine import SimLog

# =========================== decorators ======================================

def openfile(func):
    def inner(inputfile):
        with open(inputfile, 'r') as f:
            return func(f)
    return inner

# =========================== helpers =========================================

@openfile
def kpi_formation(inputfile):
    join_times = []

    file_settings = json.loads(inputfile.readline()) # first line contains settings
    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_JOINED['type']:
            join_times.append(log['_asn'] * file_settings['tsch_slotDuration'])

    returnVal = {
        'result': max(join_times),
        # per node?
    }
    return returnVal

@openfile
def kpi_reliability(inputfile):
    rx_packets_at_dagroot = []
    tx_packets_to_dagroot = []
    DAGROOT_ID = 0 # we assume first mote is DAGRoot
    DAGROOT_IP = 0 # we assume DAGRoot IP is 0

    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_APP_RX['type'] and log['_mote_id'] == DAGROOT_ID:
            rx_packets_at_dagroot.append(log['packet'])
        elif log['_type'] == SimLog.LOG_APP_TX['type']:
            if log['packet']['net']['dstIp'] == DAGROOT_IP:
                tx_packets_to_dagroot.append(log['packet'])

    returnVal = {
        'result': len(rx_packets_at_dagroot)/ float(len(tx_packets_to_dagroot)),
        # per node?
    }
    return returnVal

@openfile
def kpi_latency(inputfile):
    rx_packets_at_dagroot = []
    tx_packets_to_dagroot = []
    DAGROOT_ID = 0  # we assume first mote is DAGRoot
    DAGROOT_IP = 0  # we assume DAGRoot IP is 0

    # get logs
    file_settings = json.loads(inputfile.readline())  # first line contains settings
    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_APP_RX['type'] and log['_mote_id'] == DAGROOT_ID:
            rx_packets_at_dagroot.append(log)
        elif log['_type'] == SimLog.LOG_APP_TX['type']:
            if log['packet']['net']['dstIp'] == DAGROOT_IP:
                tx_packets_to_dagroot.append(log)

    # === calculate latency
    packets = {} # index by srcIp then appcounter
    time_deltas = []

    # loop through tx
    for log in tx_packets_to_dagroot:
        src_id = log['packet']['net']['srcIp']
        pkt_id = log['packet']['app']['appcounter']

        # create dict
        if not src_id in packets:
            packets[src_id] = {}

        # save asn
        packets[src_id][pkt_id] = log['_asn']

    # loop through rx
    for log in rx_packets_at_dagroot:
        src_id = log['packet']['net']['srcIp']
        pkt_id = log['packet']['app']['appcounter']

        # calculate time delta
        if src_id in packets and pkt_id in packets[src_id]:
            asn_delta = log['_asn'] - packets[src_id][pkt_id]
            time_deltas.append(asn_delta * file_settings['tsch_slotDuration'])
    # === end calculate latency

    returnVal = {
        'result': sum(time_deltas) / float(len(time_deltas)),
        # per node?
        # min/avg/max?
        # std
    }
    return returnVal

@openfile
def kpi_consumption(inputfile):
    for line in inputfile:
        pass

    returnVal = {
        'result': 'TODO',
        # per node?
        # per hop?
        # first death?
        # last death?
        # lifetime for different batteries?
    }
    return returnVal

# =========================== main ============================================

def kpis_all(inputfile):
    kpis = {
        'formation':    kpi_formation(inputfile),
        'reliability':  kpi_reliability(inputfile),
        'latency':      kpi_latency(inputfile),
        'consumption':  kpi_consumption(inputfile),
    }
    return kpis

def main():
    subfolder = sorted(os.listdir('simData'))[-1] # chose latest results
    for file_path in glob.glob(os.path.join('simData', subfolder, '*.dat')):
        print file_path

        # gather the kpis
        kpis = kpis_all(file_path)

        # print on the terminal
        print json.dumps(kpis, indent=4)

        # add to the data folder
        with open('{0}_kpis.json'.format(file_path), 'w') as f:
            f.write(json.dumps(kpis, indent=4))

if __name__=='__main__':
    main()

