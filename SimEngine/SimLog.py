"""
This module defines the available logs

Usage: log(LOG_APP_REACHES_DAGROOT, {"mote": self.id})
"""

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
LOG_6TOP_ADD_CELL = {"type": "6top_add_cell"}
LOG_6TOP_TX_ADD_REQ = {"type": "6top_tx_add_req"}
LOG_6TOP_TX_DEL_REQ = {"type": "6top_tx_del_req"}
LOG_6TOP_TX_ADD_RESP = {"type": "6top_tx_add_resp"}
LOG_6TOP_TX_DEL_RESP = {"type": "6top_tx_del_resp"}
LOG_6TOP_RX_ADD_REQ = {"type": "6top_rx_add_req"}
LOG_6TOP_RX_DEL_REQ = {"type": "6top_rx_del_req"}
LOG_6TOP_RX_RESP = {"type": "6top_rx_resp", "keys": ["mote_id", "rc", "type", "neighbor_id"]}
LOG_6TOP_RX_ACK = {"type": "6top_rx_ack"}
LOG_6TOP_LATENCY = {"type": "6top_latency"}

# === 6LoWPAN
LOG_SIXLOWPAN_FRAGMENT_RELAYED = {"type": "fragment_relayed"}

# === RPL
LOG_RPL_TX_DIO = {"type": "rpl_tx_dio"}
LOG_RPL_RX_DIO = {"type": "rpl_rx_dio"}
LOG_RPL_TX_DAO = {"type": "rpl_tx_dao"}
LOG_RPL_RX_DAO = {"type": "rpl_rx_dao"}
LOG_RPL_CHURN_RANK = {"type": "rpl_churn_rank"}
LOG_RPL_CHURN_PREF_PARENT = {"type": "rpl_churn_pref_parent"}
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
LOG_JOIN_RX = {"type": "join_rx"}
LOG_JOINED = {"type": "joined"}

# === MOTE

LOG_MOTE_STAT = {"type": "mote_stat"}

# ============================ methods ========================================

def check_log_format(simlog, content):
    """
    Check if the log format is valid
    :param dict simlog:
    :param dict content:
    :return:
    """
    if "keys" in simlog and sorted(simlog["keys"]) != sorted(content.keys()):
        print simlog["keys"], content.keys()
        raise Exception("Missing keys in log_type {0}".format(simlog))
