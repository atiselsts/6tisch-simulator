"""
This module defines the available logs

Usage: log(LOG_APP_REACHES_DAGROOT, {"mote": self.id})
"""

# ========================== imports =========================================

import json

import SimSettings
import SimEngine

# =========================== defines =========================================

# === PROPAGATION
LOG_PROP_PROBABLE_COLLISION = {"type": "radio_probable_collision"}

# === TSCH
LOG_TSCH_ADD_CELL = {"type": "tsch_add_cell"}
LOG_TSCH_REMOVE_CELL = {"type": "tsch_remove_cell"}
LOG_TSCH_TX_EB = {"type": "tsch_tx_eb"}
LOG_TSCH_RX_EB = {"type": "tsch_rx_eb"}
LOG_TSCH_DROP_QUEUE_FULL = {"type": "tsch_drop_queue_full", "keys": ["mote_id"]}
LOG_TSCH_DROP_NO_TX_CELLS = {"type": "tsch_drop_no_tx_cells", "keys": ["mote_id"]}
LOG_TSCH_DROP_FAIL_ENQUEUE = {"type": "tsch_drop_fail_enqueue", "keys": ["mote_id"]}
LOG_TSCH_DROP_DATA_FAIL_ENQUEUE = {"type": "tsch_drop_data_fail_enqueue", "keys": ["mote_id"]}
LOG_TSCH_DROP_ACK_FAIL_ENQUEUE = {"type": "tsch_drop_ack_fail_enqueue", "keys": ["mote_id"]}
LOG_TSCH_DROP_MAX_RETRIES = {"type": "tsch_drop_max_retries", "keys": ["mote_id"]}
LOG_TSCH_DROP_DATA_MAX_RETRIES = {"type": "tsch_drop_data_max_retries", "keys": ["mote_id"]}
LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE = {"type": "tsch_drop_frag_fail_enqueue", "keys": ["mote_id"]}
LOG_TSCH_DROP_RELAY_FAIL_ENQUEUE = {"type": "tsch_drop_relay_fail_enqueue", "keys": ["mote_id"]}

# === 6TOP
LOG_6TOP_ADD_CELL = {"type": "6top_add_cell",
                     'keys': ['ts', 'channel', 'direction', 'neighbor_id']}
LOG_6TOP_TX_ADD_REQ = {"type": "6top_tx_add_req"}
LOG_6TOP_TX_DEL_REQ = {"type": "6top_tx_del_req"}
LOG_6TOP_TX_ADD_RESP = {"type": "6top_tx_add_resp"}
LOG_6TOP_TX_DEL_RESP = {"type": "6top_tx_del_resp"}
LOG_6TOP_RX_ADD_REQ = {"type": "6top_rx_add_req"}
LOG_6TOP_RX_DEL_REQ = {"type": "6top_rx_del_req"}
LOG_6TOP_RX_RESP = {"type": "6top_rx_resp", "keys": ["mote_id", "rc", "type", "neighbor_id"]}
LOG_6TOP_RX_ACK = {"type": "6top_rx_ack"}
LOG_6TOP_TIMEOUT = {"type": "6top_timeout", 'keys': ['cell_pdr']}
LOG_6TOP_CELL_USED = {"type": "6top_cell_used",
                      'keys': ['neighbor', 'direction', 'cell_type', 'prefered_parent']}
LOG_6TOP_CELL_ELAPSED = {"type": "6top_cell_elapsed", 'keys': ['cell_pdr']}
LOG_6TOP_ERROR = {"type": "6top_error"}
LOG_6TOP_INFO = {"type": "6top_info"}
LOG_6TOP_LATENCY = {"type": "6top_latency"}

# === 6LoWPAN
LOG_SIXLOWPAN_FRAGMENT_RELAYED = {"type": "fragment_relayed"}

# === RPL
LOG_RPL_TX_DIO = {"type": "rpl_tx_dio"}
LOG_RPL_RX_DIO = {"type": "rpl_rx_dio", "keys": ['source']}
LOG_RPL_TX_DAO = {"type": "rpl_tx_dao"}
LOG_RPL_RX_DAO = {"type": "rpl_rx_dao", "keys": ['source']}
LOG_RPL_CHURN_RANK = {"type": "rpl_churn_rank", "keys": ['old_rank', 'new_rank']}
LOG_RPL_CHURN_PREF_PARENT = {"type": "rpl_churn_pref_parent",
                             "keys": ['old_parent', 'new_parent']}
LOG_RPL_CHURN_PARENT_SET = {"type": "rpl_churn_parent_set"}
LOG_RPL_DROP_NO_ROUTE = {"type": "rpl_drop_no_route", "keys": ["mote_id"]}

# === APP
LOG_APP_REACHES_DAGROOT = {"type": "app_reaches_dagroot", "keys": ["mote_id"]}
LOG_APP_GENERATED = {"type": "app_generated", "keys": ["mote_id"]}
LOG_APP_RELAYED = {"type": "app_relayed"}
LOG_APP_VRB_TABLE_FULL = {"type": "app_vrb_table_full"}

# === CHARGE
LOG_CHARGE_CONSUMED = {"type": "charge_consumed", "keys": ["mote_id", "charge"]}

# === QUEUE
LOG_QUEUE_DELAY = {"type": "queue_delay"}

# === JOIN
LOG_JOIN_TX = {"type": "join_tx"}
LOG_JOIN_RX = {"type": "join_rx", "keys": ['source', 'token']}
LOG_JOINED = {"type": "joined"}

# === MOTE
LOG_MOTE_STATS = {"type": "mote_stats"}
LOG_MOTE_STATE = {"type": "mote_state"}

# ===
LOG_THREAD_STATE = {"type": "thread_state", "keys": ['state', 'name']}

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
        if self.log_filters != 'all' and simlog['type'] not in self.log_filters:
            return

        # if a key is passed but is not listed in the log definition, raise error
        if "keys" in simlog and sorted(simlog["keys"]) != sorted(content.keys()):
            print simlog["keys"], content.keys()
            raise Exception("Missing keys in log_type {0}".format(simlog))

        # update the log content
        content.update(
            {
                "asn": self.engine.asn,
                "type": simlog["type"],
                "run_id": self.engine.run_id
            }
        )

        # write line
        with open(self.settings.getOutputFile(), 'a') as f:
            json.dump(content, f)
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

    def _collectSumMoteStats(self):
        returnVal = {}

        for mote in self.engine.motes:
            mote_stats = mote.getMoteStats()
            mote_stats["mote_id"] = mote.id

            # log
            self.log(
                LOG_MOTE_STATS,
                mote_stats
            )

        return returnVal

    def _action_collect_stats(self):
        """Called at each end of cycle."""

        self._collectSumMoteStats()

        # schedule next statistics collection
        self.engine.scheduleAtAsn(
            asn         = self.engine.asn + self.settings.tsch_slotframeLength,
            cb          = self._action_collect_stats,
            uniqueTag   = (None, '_action_collect_stats'),
            priority    = 10,
        )
