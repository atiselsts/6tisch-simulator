# === admin
NUM_SUFFICIENT_TX                           = 10      # sufficient num. of tx to estimate pdr by ACK
WAITING_FOR_TX                              = 'waiting_for_tx'
WAITING_FOR_RX                              = 'waiting_for_rx'

# === addressing
BROADCAST_ADDRESS                           = 'FF-FF'

# === packet types
PKT_TYPE_DATA                               = 'DATA'
PKT_TYPE_FRAG                               = 'FRAG'
PKT_TYPE_JOIN_REQUEST                       = 'JOIN_REQUEST'
PKT_TYPE_JOIN_RESPONSE                      = 'JOIN_RESPONSE'
PKT_TYPE_DIS                                = 'DIS'
PKT_TYPE_DIO                                = 'DIO'
PKT_TYPE_DAO                                = 'DAO'
PKT_TYPE_EB                                 = 'EB'
PKT_TYPE_SIXP                               = '6P'
PKT_TYPE_KEEP_ALIVE                         = 'KEEP_ALIVE'

# === packet lengths
PKT_LEN_DIS                                 = 8
PKT_LEN_DIO                                 = 76
PKT_LEN_DAO                                 = 20
PKT_LEN_JOIN_REQUEST                        = 20
PKT_LEN_JOIN_RESPONSE                       = 20

# === rpl
RPL_MINHOPRANKINCREASE                      = 256
RPL_PARENT_SWITCH_RANK_THRESHOLD            = 640

RPL_INFINITE_RANK                           = 65535

# === ipv6
IPV6_DEFAULT_HOP_LIMIT                      = 64
IPV6_DEFAULT_PREFIX                         = 'fd00::'
IPV6_ALL_RPL_NODES_ADDRESS                  = 'ff02::1a'

# === sixlowpan
SIXLOWPAN_REASSEMBLY_BUFFER_LIFETIME        = 60 # in seconds
SIXLOWPAN_VRB_TABLE_ENTRY_LIFETIME          = 60 # in seconds

# === sixp
SIXP_MSG_TYPE_REQUEST                       = 'Request'
SIXP_MSG_TYPE_RESPONSE                      = 'Response'
SIXP_MSG_TYPE_CONFIRMATION                  = 'Confirmation'

SIXP_CMD_ADD                                = 'ADD'
SIXP_CMD_DELETE                             = 'DELETE'
SIXP_CMD_RELOCATE                           = 'RELOCATE'
SIXP_CMD_COUNT                              = 'COUNT'
SIXP_CMD_LIST                               = 'LIST'
SIXP_CMD_SIGNAL                             = 'SIGNAL'
SIXP_CMD_CLEAR                              = 'CLEAR'

SIXP_RC_SUCCESS                             = 'RC_SUCCESS'
SIXP_RC_EOL                                 = 'RC_EOL'
SIXP_RC_ERR                                 = 'RC_ERR'
SIXP_RC_RESET                               = 'RC_RESET'
SIXP_RC_ERR_VERSION                         = 'RC_ERR_VERSION'
SIXP_RC_ERR_SFID                            = 'RC_ERR_SFID'
SIXP_RC_ERR_SEQNUM                          = 'RC_ERR_SEQNUM'
SIXP_RC_ERR_CELLLIST                        = 'RC_ERR_CELLLIST'
SIXP_RC_ERR_BUSY                            = 'RC_ERR_BUSY'
SIXP_RC_ERR_LOCKED                          = 'RC_ERR_LOCKED'

SIXP_TRANSACTION_TYPE_2_STEP                = '2-step transaction'
SIXP_TRANSACTION_TYPE_3_STEP                = '3-step transaction'

SIXP_TRANSACTION_TYPE_TWO_STEP              = 'two-step transaction'
SIXP_TRANSACTION_TYPE_THREE_STEP            = 'three-step transaction'

SIXP_CALLBACK_EVENT_PACKET_RECEPTION        = 'packet-reception'
SIXP_CALLBACK_EVENT_MAC_ACK_RECEPTION       = 'mac-ack-reception'
SIXP_CALLBACK_EVENT_TIMEOUT                 = 'timeout'
SIXP_CALLBACK_EVENT_FAILURE                 = 'failure'
SIXP_CALLBACK_EVENT_ABORTED                 = 'aborted'

# === sf
MSF_MAX_NUMCELLS                            = 12
MSF_LIM_NUMCELLSUSED_HIGH                   = 0.75 # in [0-1]
MSF_LIM_NUMCELLSUSED_LOW                    = 0.25 # in [0-1]
MSF_HOUSEKEEPINGCOLLISION_PERIOD            = 60   # in seconds
MSF_RELOCATE_PDRTHRES                       = 0.5  # in [0-1]
MSF_MIN_NUM_TX                              = 100  # min number for PDR to be significant

# === tsch
TSCH_MAXTXRETRIES                           = 5
TSCH_MIN_BACKOFF_EXPONENT                   = 1
TSCH_MAX_BACKOFF_EXPONENT                   = 7
# https://gist.github.com/twatteyne/2e22ee3c1a802b685695#file-4e_tsch_default_ch-py
TSCH_HOPPING_SEQUENCE                       = [16, 17, 23, 18, 26, 15, 25, 22, 19, 11, 12, 13, 24, 14, 20, 21]
TSCH_MAX_EB_DELAY                           = 180
TSCH_NUM_NEIGHBORS_TO_WAIT                  = 2
CELLOPTION_TX                               = 'TX'
CELLOPTION_RX                               = 'RX'
CELLOPTION_SHARED                           = 'SHARED'
LINKTYPE_ADVERTISING                        = 'ADVERTISING'
LINKTYPE_NORMAL                             = 'NORMAL'
INTRASLOTORDER_STARTSLOT                    = 0
INTRASLOTORDER_PROPAGATE                    = 1
INTRASLOTORDER_STACKTASKS                   = 2
INTRASLOTORDER_ADMINTASKS                   = 3

# === radio
RADIO_STATE_TX                              = 'tx'
RADIO_STATE_RX                              = 'rx'
RADIO_STATE_OFF                             = 'off'

# === battery
# Idle: Time slot during which a node listens for data, but receives
# none
CHARGE_IdleListen_uC                        = 6.4
# TxDataRxAck: A timeslot during which the node sends some data frame,
# and expects an acknowledgment (ACK)
CHARGE_TxDataRxAck_uC                       = 54.5
# TxData: Similar to TxDataRxAck, but no ACK is expected. This is
# typically used when the data packet is broadcast
CHARGE_TxData_uC                            = 49.5
# RxDataTxAck: A timeslot during which the node receives some data
# frame, and sends back an ACK to indicate successful reception
CHARGE_RxDataTxAck_uC                       = 32.6
# RxData: Similar to the RxDataTxAck but no ACK is sent (for a
# broadcast packet)
CHARGE_RxData_uC                            = 22.6
