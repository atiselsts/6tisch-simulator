
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

# === packet lengths
PKT_LEN_DAO                                 = 20
PKT_LEN_JOIN_REQUEST                        = 20
PKT_LEN_JOIN_RESPONSE                       = 20

# === rpl
RPL_PARENT_SWITCH_THRESHOLD                 = 768 # corresponds to 1.5 hops. RFC8180 uses 384 for 2*ETX.
RPL_MIN_HOP_RANK_INCREASE                   = 256
RPL_MAX_ETX                                 = 4
RPL_MAX_RANK_INCREASE                       = RPL_MAX_ETX*RPL_MIN_HOP_RANK_INCREASE*2 # 4 transmissions allowed for rank increase for parents
RPL_MAX_TOTAL_RANK                          = 256*RPL_MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
RPL_PARENT_SET_SIZE                         = 3

# === sixlowpan
SIXLOWPAN_REASSEMBLY_BUFFER_LIFETIME        = 60 # in seconds
SIXLOWPAN_VRB_TABLE_ENTRY_LIFETIME          = 60 # in seconds

# === sixp
SIXP_RC_SUCCESS                             = 'success'

# === tsch
TSCH_QUEUE_SIZE                             = 10
TSCH_MAXTXRETRIES                           = 5
TSCH_MIN_BACKOFF_EXPONENT                   = 3
TSCH_MAX_BACKOFF_EXPONENT                   = 5
CELLOPTION_TX                               = 'TX'
CELLOPTION_RX                               = 'RX'
CELLOPTION_SHARED                           = 'SHARED'

# === radio
RADIO_MAXDRIFT                              = 30 # in ppm
RADIO_STATE_IDLE                            = 'idle'
RADIO_STATE_TX                              = 'tx'
RADIO_STATE_RX                              = 'rx'

# === battery
CHARGE_Idle_uC                              = 6.4
CHARGE_TxDataRxAck_uC                       = 54.5
CHARGE_TxData_uC                            = 49.5
CHARGE_TxDataRxAckNone_uC                   = 54.5
CHARGE_RxDataTxAck_uC                       = 32.6
CHARGE_RxData_uC                            = 22.6
