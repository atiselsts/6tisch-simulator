"""
This module defines the available logs

Usage:
    self.log(
        SimEngine.SimLog.LOG_APP_RX,
        {
            '_mote_id': self.mote.id,
            'source':  srcIp.id,
        }
    )
"""

# ========================== imports =========================================

import json
import traceback

import SimSettings
import SimEngine

# =========================== defines =========================================

# === thread
LOG_THREAD_STATE                 = {'type': 'thread.state', 'keys': ['state', 'name']}

# === mote
LOG_MOTE_STATE                   = {'type': 'mote.state'}

# === app
LOG_APP_TX                       = {'type': 'app.tx',      'keys': ['_mote_id','dest_id','appcounter','packet_type']}
LOG_APP_RX                       = {'type': 'app.rx',      'keys': ['_mote_id','packet']}
LOG_APP_RELAYED                  = {'type': 'app.relayed'}

# === join 
LOG_JOIN_TX                      = {'type': 'join.tx',     'keys': ['_mote_id']}
LOG_JOIN_RX                      = {'type': 'join.rx',     'keys': ['_mote_id']}
LOG_JOINED                       = {'type': 'join.joined', 'keys': ['_mote_id']}

# === rpl
LOG_RPL_DIO_TX                   = {'type': 'rpl.dio.tx',           'keys': ['_mote_id']}
LOG_RPL_DIO_RX                   = {'type': 'rpl.dio.rx',           'keys': ['_mote_id','source']}
LOG_RPL_DAO_TX                   = {'type': 'rpl.dao.tx',           'keys': ['_mote_id']}
LOG_RPL_DAO_RX                   = {'type': 'rpl.dao.rx',           'keys': ['source']}
LOG_RPL_CHURN_RANK               = {'type': 'rpl.churn_rank',       'keys': ['old_rank', 'new_rank']}
LOG_RPL_CHURN_PREF_PARENT        = {'type': 'rpl.churn_pref_parent','keys': ['old_parent', 'new_parent']}
LOG_RPL_CHURN_PARENT_SET         = {'type': 'rpl.churn_parent_set'}
LOG_RPL_DROP_NO_ROUTE            = {'type': 'rpl.drop_no_route',    'keys': ['_mote_id']}

# === 6LoWPAN
LOG_SIXLOWPAN_PKT_TX             = {'type': 'sixlowpan.pkt.tx',           'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_FWD            = {'type': 'sixlowpan.pkt.fwd',          'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_RX             = {'type': 'sixlowpan.pkt.rx',           'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_FRAG_GEN           = {'type': 'sixlowpan.frag.gen',         'keys': ['_mote_id','packet']}

# === 6top
LOG_6TOP_ADD_CELL                = {'type': '6top.add_cell',     'keys': ['ts', 'channel', 'direction', 'neighbor_id']}
LOG_6TOP_TX_ADD_REQ              = {'type': '6top.tx_add_req'}
LOG_6TOP_TX_DEL_REQ              = {'type': '6top.tx_del_req'}
LOG_6TOP_TX_ADD_RESP             = {'type': '6top.tx_add_resp'}
LOG_6TOP_TX_DEL_RESP             = {'type': '6top.tx_del_resp'}
LOG_6TOP_RX_ADD_REQ              = {'type': '6top.rx_add_req'}
LOG_6TOP_RX_DEL_REQ              = {'type': '6top.rx_del_req'}
LOG_6TOP_RX_RESP                 = {'type': '6top.rx_resp',      'keys': ['_mote_id', 'rc', 'type', 'neighbor_id']}
LOG_6TOP_RX_ACK                  = {'type': '6top.rx_ack'}
LOG_6TOP_TIMEOUT                 = {'type': '6top.timeout',      'keys': ['cell_pdr']}
LOG_6TOP_CELL_USED               = {'type': '6top.cell_used',    'keys': ['neighbor', 'direction', 'cell_type', 'prefered_parent']}
LOG_6TOP_CELL_ELAPSED            = {'type': '6top.cell_elapsed', 'keys': ['cell_pdr']}
LOG_6TOP_ERROR                   = {'type': '6top.error'}
LOG_6TOP_INFO                    = {'type': '6top.info'}
LOG_6TOP_LATENCY                 = {'type': '6top.latency'}
LOG_6TOP_QUEUE_DEL               = {'type': '6top.queue_del', 'keys': ['pkt_type','neighbor']}

# === tsch
LOG_TSCH_SYNCED                  = {'type': 'tsch.synced',                  'keys': ['_mote_id']}
LOG_TSCH_ADD_CELL                = {'type': 'tsch.add_cell'}
LOG_TSCH_REMOVE_CELL             = {'type': 'tsch.remove_cell'}
LOG_TSCH_TX_EB                   = {'type': 'tsch.tx_eb'}
LOG_TSCH_RX_EB                   = {'type': 'tsch.rx_eb'}
LOG_TSCH_TXDONE                  = {'type': 'tsch.txdone',                  'keys': ['_mote_id','channel','packet','isACKed']}
LOG_TSCH_RXDONE                  = {'type': 'tsch.rxdone',                  'keys': ['_mote_id','packet']}
LOG_TSCH_DROP_QUEUE_FULL         = {'type': 'tsch.drop_queue_full',         'keys': ['_mote_id']}
LOG_TSCH_DROP_NO_TX_CELLS        = {'type': 'tsch.drop_no_tx_cells',        'keys': ['_mote_id']}
LOG_TSCH_DROP_FAIL_ENQUEUE       = {'type': 'tsch.drop_fail_enqueue',       'keys': ['_mote_id']}
LOG_TSCH_DROP_DATA_FAIL_ENQUEUE  = {'type': 'tsch.drop_data_fail_enqueue',  'keys': ['_mote_id']}
LOG_TSCH_DROP_ACK_FAIL_ENQUEUE   = {'type': 'tsch.drop_ack_fail_enqueue',   'keys': ['_mote_id']}
LOG_TSCH_DROP_MAX_RETRIES        = {'type': 'tsch.drop_max_retries',        'keys': ['_mote_id']}
LOG_TSCH_DROP_DATA_MAX_RETRIES   = {'type': 'tsch.drop_data_max_retries',   'keys': ['_mote_id']}
LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE  = {'type': 'tsch.drop_frag_fail_enqueue',  'keys': ['_mote_id']}
LOG_TSCH_DROP_RELAY_FAIL_ENQUEUE = {'type': 'tsch.drop_relay_fail_enqueue', 'keys': ['_mote_id']}

# === radio
LOG_PACKET_DROPPED               = {'type': 'packet_dropped', 'keys': ['_mote_id','packet','reason']}

# === queue
LOG_QUEUE_DELAY                  = {'type': 'queue.delay'}

# === propagation
LOG_PROP_TRANSMISSION            = {'type': 'prop.transmission', 'keys': ['channel','packet','destinations']}
LOG_PROP_INTERFERENCE            = {'type': 'prop.interference', 'keys': ['source_id','channel','interferers']}

# ============================ SimLog =========================================

class SimLog(object):

    # ==== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimLog, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    # ==== end singleton

    def __init__(self, failIfNotInit=False):

        if failIfNotInit and not self._init:
            raise EnvironmentError('SimLog singleton not initialized.')

        # ==== start singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        # ==== end singleton

        # get singletons
        self.settings   = SimSettings.SimSettings()
        self.engine     = None # will be defined by set_simengine

        # local variables
        self.log_filters = []

        # write config to log file
        with open(self.settings.getOutputFile(), 'w') as f:
            json.dump(self.settings.__dict__, f)
            f.write('\n')

    def log(self, simlog, content):
        """
        :param dict simlog:
        :param dict content:
        """

        # ignore types that are not listed in the simulation config
        if (self.log_filters != 'all') and (simlog['type'] not in self.log_filters):
            return

        # if a key is passed but is not listed in the log definition, raise error
        if ("keys" in simlog) and (sorted(simlog["keys"]) != sorted(content.keys())):
            raise Exception(
                "Wrong keys passed to log() function for type {0}!\n    - expected {1}\n    - got      {2}".format(
                    simlog['type'],
                    sorted(simlog["keys"]),
                    sorted(content.keys()),
                )
            )

        # update the log content
        content.update(
            {
                "_asn":       self.engine.asn,
                "_type":      simlog["type"],
                "_run_id":    self.engine.run_id
            }
        )

        # write line
        with open(self.settings.getOutputFile(), 'a') as f:
            try:
                json.dump(content, f, sort_keys=True)
            except Exception as err:
                output  = []
                output += ['----------------------']
                output += ['']
                output += ['log() FAILED for content']
                output += [str(content)]
                output += ['']
                output += [str(err)]
                output += ['']
                output += [traceback.format_exc(err)]
                output += ['']
                output += ['----------------------']
                output  = '\n'.join(output)
                print output
                raise
            f.write('\n')

    def set_simengine(self, engine):
        self.engine = engine

    def set_log_filters(self, log_filters):
        self.log_filters = log_filters

    def destroy(self):
        cls = type(self)
        cls._instance       = None
        cls._init           = False

    # ============================== private ==================================
