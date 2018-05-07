# =========================== adjust path =====================================

import os
import sys

if __name__ == '__main__':
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..'))

# ========================== imports ==========================================

import json
import glob

from SimEngine import SimLog

# =========================== defines =========================================

DAGROOT_ID = 0 # we assume first mote is DAGRoot
DAGROOT_IP = 0  # we assume DAGRoot IP is 0

# =========================== decorators ======================================

def openfile(func):
    def inner(inputfile):
        with open(inputfile, 'r') as f:
            return func(f)
    return inner

# =========================== helpers =========================================

@openfile
def kpi_formation(inputfile):
    joins  = {} # indexed by run_id

    # read file settings
    file_settings = json.loads(inputfile.readline())

    for line in inputfile:
        log = json.loads(line)

        if log['_type'] == SimLog.LOG_JOINED['type']:
            run_id = log['_run_id']
            mote_id = log['_mote_id']

            # convert and save time to join
            if mote_id != DAGROOT_ID: # do not log DAGRoot join
                joins.setdefault(run_id, {})[mote_id] = \
                    log['_asn'] * file_settings['tsch_slotDuration']

    # make sure all motes joined
    for run_id in joins.iterkeys():
        assert len(joins[run_id]) == (file_settings['exec_numMotes'] -1)

    # calculate average max join time
    max_join_time_list = []
    for run_id in joins.iterkeys():
        max_join_time_list.append(max([t for t in joins[run_id].itervalues()]))
    avg_max_join_time = sum(max_join_time_list) / float(len(max_join_time_list))

    returnVal = {
        'result': avg_max_join_time,
        # per node?
    }
    return returnVal

@openfile
def kpi_reliability(inputfile):
    rx_packets_at_dagroot = {} # indexed by run_id
    tx_packets_to_dagroot = {} # indexed by run_id

    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_APP_RX['type'] and log['_mote_id'] == DAGROOT_ID:
            rx_packets_at_dagroot.setdefault(log['_run_id'], []).append(log['packet'])
        elif log['_type'] == SimLog.LOG_APP_TX['type']:
            if log['packet']['net']['dstIp'] == DAGROOT_IP:
                tx_packets_to_dagroot.setdefault(log['_run_id'], []).append(log['packet'])

    # === calculate average e2e reliability
    avg_reliabilities = []
    for run_id in tx_packets_to_dagroot.iterkeys():
        avg_reliabilities.append(
            len(rx_packets_at_dagroot[run_id]) /
            float(len(tx_packets_to_dagroot[run_id]))
        )
    avg_reliability = sum(avg_reliabilities) / float(len(avg_reliabilities))
    # === end calculate average e2e reliability

    returnVal = {
        'result': avg_reliability,
        # per node?
    }
    return returnVal

@openfile
def kpi_latency(inputfile):
    rx_packets_at_dagroot = {} # indexed by run_id
    tx_packets_to_dagroot = {} # indexed by run_id

    # get logs
    file_settings = json.loads(inputfile.readline())  # first line contains settings
    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_APP_RX['type'] and log['_mote_id'] == DAGROOT_ID:
            rx_packets_at_dagroot.setdefault(log['_run_id'], []).append(log)
        elif log['_type'] == SimLog.LOG_APP_TX['type']:
            if log['packet']['net']['dstIp'] == DAGROOT_IP:
                tx_packets_to_dagroot.setdefault(log['_run_id'], []).append(log)

    # === calculate average e2e latency
    avg_latencies = []
    for run_id in tx_packets_to_dagroot.iterkeys():
        packets = {} # index by srcIp then appcounter
        time_deltas = []

        # loop through tx
        for log in tx_packets_to_dagroot[run_id]:
            src_id = log['packet']['net']['srcIp']
            pkt_id = log['packet']['app']['appcounter']

            # create dict
            if not src_id in packets:
                packets[src_id] = {}

            # save asn
            packets[src_id][pkt_id] = log['_asn']

        # loop through rx
        for log in rx_packets_at_dagroot[run_id]:
            src_id = log['packet']['net']['srcIp']
            pkt_id = log['packet']['app']['appcounter']

            # calculate time delta
            if src_id in packets and pkt_id in packets[src_id]:
                asn_delta = log['_asn'] - packets[src_id][pkt_id]
                time_deltas.append(asn_delta * file_settings['tsch_slotDuration'])

        avg_latencies.append(sum(time_deltas) / float(len(time_deltas)))
    avg_latency = sum(avg_latencies) / float(len(avg_latencies))
    # === end calculate latency

    returnVal = {
        'result': avg_latency,
        # per node?
        # min/avg/max?
        # std
    }
    return returnVal

@openfile
def kpi_consumption(inputfile):
    batt_logs = {} # indexed by run_id

    # get logs
    for line in inputfile:
        log = json.loads(line)
        if log['_type'] == SimLog.LOG_BATT_CHARGE['type']:
            batt_logs.setdefault(log['_run_id'], {})\
                     .setdefault(log['_mote_id'], []).append(log)

    # find average max consumption
    max_consumptions = []
    for run in batt_logs.itervalues():
        max_consumption = 0
        for mote in run.itervalues():
            max_consumption = max(
                sum([l['charge'] for l in mote]),
                max_consumption
            )
        max_consumptions.append(max_consumption)
    avg_max_consumptions = sum(max_consumptions) / float(len(max_consumptions))

    returnVal = {
        'result': avg_max_consumptions / 3600, # uC to uA
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

if __name__ == '__main__':
    main()
