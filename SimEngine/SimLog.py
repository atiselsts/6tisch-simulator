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
LOG_RPL_DIO_TX                   = {'type': 'rpl.dio.tx',                 'keys': ['_mote_id']}
LOG_RPL_DIO_RX                   = {'type': 'rpl.dio.rx',                 'keys': ['_mote_id','source']}
LOG_RPL_DAO_TX                   = {'type': 'rpl.dao.tx',                 'keys': ['_mote_id']}
LOG_RPL_DAO_RX                   = {'type': 'rpl.dao.rx',                 'keys': ['source']}
LOG_RPL_CHURN_RANK               = {'type': 'rpl.churn_rank',             'keys': ['old_rank', 'new_rank']}
LOG_RPL_CHURN_PREF_PARENT        = {'type': 'rpl.churn_pref_parent',      'keys': ['old_parent', 'new_parent']}
LOG_RPL_CHURN_PARENT_SET         = {'type': 'rpl.churn_parent_set'}

# === 6LoWPAN
LOG_SIXLOWPAN_PKT_TX             = {'type': 'sixlowpan.pkt.tx',           'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_FWD            = {'type': 'sixlowpan.pkt.fwd',          'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_RX             = {'type': 'sixlowpan.pkt.rx',           'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_FRAG_GEN           = {'type': 'sixlowpan.frag.gen',         'keys': ['_mote_id','packet']}

# === sixp
LOG_6P_ADD_REQUEST_TX            = {'type': 'sixp.add_request.tx',        'keys': ['_mote_id','packet']}
LOG_6P_ADD_RESPONSE_TX           = {'type': 'sixp.add_response.tx',       'keys': ['_mote_id','packet']}
LOG_6P_ADD_RESPONSE_RX           = {'type': 'sixp.add_response.rx',       'keys': ['_mote_id','packet']}
LOG_6P_DELETE_REQUEST_TX         = {'type': 'sixp.delete_request.tx',     'keys': ['_mote_id','packet']}
LOG_6P_DELETE_RESPONSE_TX        = {'type': 'sixp.delete_response.tx',    'keys': ['_mote_id','packet']}
LOG_6P_DELETE_RESPONSE_RX        = {'type': 'sixp.delete_response.rx',    'keys': ['_mote_id','packet']}

# === tsch
LOG_TSCH_SYNCED                  = {'type': 'tsch.synced',                'keys': ['_mote_id']}
LOG_TSCH_ADD_CELL                = {'type': 'tsch.add_cell'}
LOG_TSCH_REMOVE_CELL             = {'type': 'tsch.remove_cell'}
LOG_TSCH_TX_EB                   = {'type': 'tsch.tx_eb'}
LOG_TSCH_RX_EB                   = {'type': 'tsch.rx_eb'}
LOG_TSCH_TXDONE                  = {'type': 'tsch.txdone',                'keys': ['_mote_id','channel','packet','isACKed']}
LOG_TSCH_RXDONE                  = {'type': 'tsch.rxdone',                'keys': ['_mote_id','packet']}

# === dropping
LOG_PACKET_DROPPED               = {'type': 'packet_dropped', 'keys': ['_mote_id','packet','reason']}
DROPREASON_NO_ROUTE              = 'no_route'
DROPREASON_TXQUEUE_FULL          = 'txqueue_full'
DROPREASON_NO_TX_CELLS           = 'no_tx_cells'
DROPREASON_MAX_RETRIES           = 'max_retries'
DROPREASON_REASSEMBLY_BUFFER_FULL= 'reassembly_buffer_full'
DROPREASON_VRB_TABLE_FULL        = 'vrb_table_full'

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

        # write config to log file; if a file with the same file name exists,
        # append logs to the file. this happens if you multiple runs on the
        # same CPU.
        with open(self.settings.getOutputFile(), 'a') as f:
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
