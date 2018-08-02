
# === admin
NUM_SUFFICIENT_TX                           = 10      # sufficient num. of tx to estimate pdr by ACK
WAITING_FOR_TX                              = 'waiting_for_tx'
WAITING_FOR_RX                              = 'waiting_for_rx'

# === addressing
BROADCAST_ADDRESS                           = 0xffff

# === packet types
PKT_TYPE_DATA                               = 'DATA'
PKT_TYPE_FRAG                               = 'FRAG'
PKT_TYPE_JOIN_REQUEST                       = 'JOIN_REQUEST'
PKT_TYPE_JOIN_RESPONSE                      = 'JOIN_RESPONSE'
PKT_TYPE_DIO                                = 'DIO'
PKT_TYPE_DAO                                = 'DAO'
PKT_TYPE_EB                                 = 'EB'
PKT_TYPE_SIXP                               = '6P'
PKT_TYPE_KEEP_ALIVE                         = 'KEEP_ALIVE'

# === packet lengths
PKT_LEN_DIO                                 = 76
PKT_LEN_DAO                                 = 20
PKT_LEN_JOIN_REQUEST                        = 20
PKT_LEN_JOIN_RESPONSE                       = 20

# === rpl
RPL_MINHOPRANKINCREASE                      = 256
RPL_PARENT_SWITCH_THRESHOLD                 = 640

# === ipv6
IPV6_DEFAULT_HOP_LIMIT                      = 64

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

# === sf
MSF_MAX_NUMCELLS                            = 12
MSF_LIM_NUMCELLSUSED_HIGH                   = 0.75 # in [0-1]
MSF_LIM_NUMCELLSUSED_LOW                    = 0.25 # in [0-1]
MSF_HOUSEKEEPINGCOLLISION_PERIOD            = 60   # in seconds
MSF_RELOCATE_PDRTHRES                       = 0.5  # in [0-1]
MSF_MIN_NUM_TX                              = 100  # min number for PDR to be significant

# === tsch
TSCH_QUEUE_SIZE                             = 10
TSCH_MAXTXRETRIES                           = 5
TSCH_MIN_BACKOFF_EXPONENT                   = 1
TSCH_MAX_BACKOFF_EXPONENT                   = 7
CELLOPTION_TX                               = 'TX'
CELLOPTION_RX                               = 'RX'
CELLOPTION_SHARED                           = 'SHARED'
INTRASLOTORDER_STARTSLOT                    = 0
INTRASLOTORDER_PROPAGATE                    = 1
INTRASLOTORDER_STACKTASKS                   = 2
INTRASLOTORDER_ADMINTASKS                   = 3

# === radio
RADIO_STATE_TX                              = 'tx'
RADIO_STATE_RX                              = 'rx'
RADIO_STATE_OFF                             = 'off'

# === battery
CHARGE_Idle_uC                              = 6.4
CHARGE_TxDataRxAck_uC                       = 54.5
CHARGE_TxData_uC                            = 49.5
CHARGE_TxDataRxAckNone_uC                   = 54.5
CHARGE_RxDataTxAck_uC                       = 32.6
CHARGE_RxData_uC                            = 22.6
