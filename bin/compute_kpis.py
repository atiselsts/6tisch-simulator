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
import SimEngine.Mote.MoteDefines as d

# =========================== defines =========================================

DAGROOT_ID = 0  # we assume first mote is DAGRoot
DAGROOT_IP = 0  # we assume DAGRoot IP is 0

# =========================== decorators ======================================

def openfile(func):
    def inner(inputfile):
        with open(inputfile, 'r') as f:
            return func(f)
    return inner

# =========================== helpers =========================================

@openfile
def kpis_all(inputfile):

    allstats = {} # indexed by run_id, srcIp

    file_settings = json.loads(inputfile.readline())  # first line contains settings

    # === gather raw stats

    for line in inputfile:
        logline = json.loads(line)

        # shorthands
        run_id = logline['_run_id']

        # populate
        if run_id not in allstats:
            allstats[run_id] = {}

        if   logline['_type'] == SimLog.LOG_TSCH_SYNCED['type']:
            # sync'ed

            # shorthands
            mote_id    = logline['_mote_id']
            asn        = logline['_asn']

            # only log non-dagRoot sync times
            if mote_id == DAGROOT_ID:
                continue

            # populate
            if mote_id not in allstats[run_id]:
                allstats[run_id][mote_id] = {}

            allstats[run_id][mote_id]['sync_asn']  = asn
            allstats[run_id][mote_id]['sync_time_s'] = asn*file_settings['tsch_slotDuration']

        elif logline['_type'] == SimLog.LOG_SECJOIN_JOINED['type']:
            # joined

            # shorthands
            mote_id    = logline['_mote_id']
            asn        = logline['_asn']

            # only log non-dagRoot join times
            if mote_id == DAGROOT_ID:
                continue

            # populate
            assert mote_id in allstats[run_id]

            allstats[run_id][mote_id]['join_asn']  = asn
            allstats[run_id][mote_id]['join_time_s'] = asn*file_settings['tsch_slotDuration']
            allstats[run_id][mote_id]['upstream_pkts'] = {}

        elif logline['_type'] == SimLog.LOG_APP_TX['type']:
            # packet transmission

            # shorthands
            srcIp      = logline['packet']['net']['srcIp']
            dstIp      = logline['packet']['net']['dstIp']
            appcounter = logline['packet']['app']['appcounter']
            tx_asn     = logline['_asn']

            # only log upstream packets
            if dstIp != DAGROOT_IP:
                continue

            # populate
            assert srcIp in allstats[run_id]
            if appcounter not in allstats[run_id][srcIp]['upstream_pkts']:
                allstats[run_id][srcIp]['upstream_pkts'][appcounter] = {
                    'hops': 0,
                }

            allstats[run_id][srcIp]['upstream_pkts'][appcounter]['tx_asn'] = tx_asn

        elif logline['_type'] == SimLog.LOG_APP_RX['type']:
            # packet reception

            # shorthands
            srcIp      = logline['packet']['net']['srcIp']
            dstIp      = logline['packet']['net']['dstIp']
            hop_limit  = logline['packet']['net']['hop_limit']
            appcounter = logline['packet']['app']['appcounter']
            rx_asn     = logline['_asn']

            # only log upstream packets
            if dstIp != DAGROOT_IP:
                continue

            allstats[run_id][srcIp]['upstream_pkts'][appcounter]['hops']   = (
                d.IPV6_DEFAULT_HOP_LIMIT - hop_limit + 1
            )
            allstats[run_id][srcIp]['upstream_pkts'][appcounter]['rx_asn'] = rx_asn

        elif logline['_type'] == SimLog.LOG_PACKET_DROPPED['type']:
            # packet dropped

            # shorthands
            mote_id    = logline['_mote_id']
            reason     = logline['reason']

            # populate
            if mote_id not in allstats[run_id]:
                allstats[run_id][mote_id] = {}
            if 'packet_drops' not in allstats[run_id][mote_id]:
                allstats[run_id][mote_id]['packet_drops'] = {}
            if reason not in allstats[run_id][mote_id]['packet_drops']:
                allstats[run_id][mote_id]['packet_drops'][reason] = 0

            allstats[run_id][mote_id]['packet_drops'][reason] += 1

        elif logline['_type'] == SimLog.LOG_BATT_CHARGE['type']:
            # battery charge

            # shorthands
            mote_id    = logline['_mote_id']
            asn        = logline['_asn']
            charge     = logline['charge']

            # only log non-dagRoot charge
            if mote_id == DAGROOT_ID:
                continue

            # populate
            if mote_id not in allstats[run_id]:
                allstats[run_id][mote_id] = {}
            if 'charge' in allstats[run_id][mote_id]:
                assert charge >= allstats[run_id][mote_id]['charge']

            allstats[run_id][mote_id]['charge_asn'] = asn
            allstats[run_id][mote_id]['charge']     = charge

    # === compute advanced motestats

    for (run_id, per_mote_stats) in allstats.items():
        for (srcIp, motestats) in per_mote_stats.items():
            if srcIp != 0:

                if   'sync_asn' not in motestats:
                    motestats['WARNING'] = "mote didn't sync"
                elif 'charge_asn' not in motestats:
                    motestats['WARNING'] = "log doesn't have battery info"
                else:
                    # avg_current, lifetime_AA
                    motestats['avg_current_uA'] = motestats['charge']/float((motestats['charge_asn']-motestats['sync_asn']) * file_settings['tsch_slotDuration'])
                    if motestats['avg_current_uA'] > 0:
                        motestats['lifetime_AA_years'] = (2200*1000/float(motestats['avg_current_uA']))/(24.0*365)
                    else:
                        motestats['lifetime_AA_years'] = 'N/A'
                if 'join_asn' in motestats:
                    # latencies, upstream_num_tx, upstream_num_rx, upstream_num_lost
                    motestats['latencies']         = []
                    motestats['hops']              = []
                    motestats['upstream_num_tx']   = 0
                    motestats['upstream_num_rx']   = 0
                    motestats['upstream_num_lost'] = 0
                    for (appcounter, pktstats) in allstats[run_id][srcIp]['upstream_pkts'].items():
                        motestats['upstream_num_tx']      += 1
                        if 'rx_asn' in pktstats:
                            motestats['upstream_num_rx']  += 1
                            thislatency = (pktstats['rx_asn']-pktstats['tx_asn'])*file_settings['tsch_slotDuration']
                            motestats['latencies']  += [thislatency]
                            motestats['hops']       += [pktstats['hops']]
                        else:
                            motestats['upstream_num_lost'] += 1
                    if (motestats['upstream_num_rx'] > 0) and (motestats['upstream_num_tx'] > 0):
                        motestats['latency_min_s'] = min(motestats['latencies'])
                        motestats['latency_avg_s'] = sum(motestats['latencies'])/float(len(motestats['latencies']))
                        motestats['latency_max_s'] = max(motestats['latencies'])
                        motestats['upstream_reliability'] = motestats['upstream_num_rx']/float(motestats['upstream_num_tx'])
                        motestats['avg_hops'] = sum(motestats['hops'])/float(len(motestats['hops']))
                    else:
                        motestats['WARNING'] = "mote didn't send or receive pkts"
                else:
                    motestats['WARNING'] = "mote didn't join"

    # === remove unnecessary stats

    for (run_id, per_mote_stats) in allstats.items():
        for (srcIp, motestats) in per_mote_stats.items():
            if 'sync_asn' in motestats:
                del motestats['sync_asn']
            if 'charge_asn' in motestats:
                del motestats['charge_asn']
                del motestats['charge']
            if 'join_asn' in motestats:
                del motestats['upstream_pkts']
                del motestats['hops']
                del motestats['latencies']
                del motestats['join_asn']

    return allstats

# =========================== main ============================================

def main():

    # FIXME: This logic could be a helper method for other scripts
    # Identify simData having the latest results. That directory should have
    # the latest "mtime".
    subfolders = list(
        map(
            lambda x: os.path.join('simData', x),
            os.listdir('simData')
        )
    )
    subfolder = max(subfolders, key=os.path.getmtime)
    for infile in glob.glob(os.path.join(subfolder, '*.dat')):
        print 'generating KPIs for {0}'.format(infile)

        # gather the kpis
        kpis = kpis_all(infile)

        # print on the terminal
        print json.dumps(kpis, indent=4)

        # add to the data folder
        outfile = '{0}.kpi'.format(infile)
        with open(outfile, 'w') as f:
            f.write(json.dumps(kpis, indent=4))
        print 'KPIs saved in {0}'.format(outfile)

if __name__ == '__main__':
    main()
