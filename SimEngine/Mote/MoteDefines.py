
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
PKT_TYPE_SIXP_ADD_REQUEST                   = 'SIXP_ADD_REQUEST'
PKT_TYPE_SIXP_ADD_RESPONSE                  = 'SIXP_ADD_RESPONSE'
PKT_TYPE_SIXP_DELETE_REQUEST                = 'SIXP_DELETE_REQUEST'
PKT_TYPE_SIXP_DELETE_RESPONSE               = 'SIXP_DELETE_RESPONSE'
PKT_TYPE_SIXP_CLEAR_REQUEST                 = 'SIXP_CLEAR_REQUEST'
PKT_TYPE_SIXP_CLEAR_RESPONSE                = 'SIXP_CLEAR_RESPONSE'
PKT_TYPE_SIXP_RELOCATE_REQUEST              = 'SIXP_RELOCATE_REQUEST'
PKT_TYPE_SIXP_RELOCATE_RESPONSE             = 'SIXP_RELOCATE_RESPONSE'

# === packet lengths
PKT_LEN_DAO                                 = 20
PKT_LEN_JOIN_REQUEST                        = 20
PKT_LEN_JOIN_RESPONSE                       = 20

# === rpl
RPL_MINHOPRANKINCREASE                      = 256
RPL_PARENT_SWITCH_THRESHOLD                 = 640

# === sixlowpan
SIXLOWPAN_REASSEMBLY_BUFFER_LIFETIME        = 60 # in seconds
SIXLOWPAN_VRB_TABLE_ENTRY_LIFETIME          = 60 # in seconds

# === sixp
SIXP_RC_SUCCESS                             = 'success'
SIXP_RC_ERR                                 = 'error'
SIXP_RC_ERR_CELLLIST                        = 'error_celllist'
SIXP_RC_ERR_SEQNUM                          = 'error_seqnum'

# === sf
MSF_MAX_NUMCELLS                            = 12
MSF_LIM_NUMCELLSUSED_HIGH                   = 0.75 # in percent [0-1]
MSF_LIM_NUMCELLSUSED_LOW                    = 0.25 # in percent [0-1]
MSF_HOUSEKEEPINGCOLLISION_PERIOD            = 60   # in seconds
MSF_RELOCATE_PDRTHRES                       = 0.5  # in percent [0-1]
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
RADIO_MAXDRIFT                              = 30 # in ppm
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
