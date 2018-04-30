
# sufficient num. of tx to estimate pdr by ACK
NUM_SUFFICIENT_TX                           = 10

# === TSCH cell option bits
DIR_TX                                      = 'TX'
DIR_RX                                      = 'RX'
DIR_TXRX_SHARED                             = 'SHARED'

# === log message levels
DEBUG                                       = 'DEBUG'
INFO                                        = 'INFO'
WARNING                                     = 'WARNING'
ERROR                                       = 'ERROR'

# === frame types
APP_TYPE_DATA                               = 'DATA'
APP_TYPE_ACK                                = 'DATA_ACK'  # end to end ACK
APP_TYPE_JOIN                               = 'JOIN' # join traffic
NET_TYPE_FRAG                               = 'FRAG'
RPL_TYPE_DIO                                = 'DIO'
RPL_TYPE_DAO                                = 'DAO'
TSCH_TYPE_EB                                = 'EB'
IANA_6TOP_ADD_REQUEST                       = '6P_ADD_REQUEST'
IANA_6TOP_DELETE_REQUEST                    = '6P_DELETE_REQUEST'

# === 6top message types
IANA_6TOP_TYPE_REQUEST                      = '6TOP_REQUEST'
IANA_6TOP_TYPE_RESPONSE                     = '6TOP_RESPONSE'

# === rpl
RPL_PARENT_SWITCH_THRESHOLD                 = 768 # corresponds to 1.5 hops. 6tisch minimal draft use 384 for 2*ETX.
RPL_MIN_HOP_RANK_INCREASE                   = 256
RPL_MAX_ETX                                 = 4
RPL_MAX_RANK_INCREASE                       = RPL_MAX_ETX*RPL_MIN_HOP_RANK_INCREASE*2 # 4 transmissions allowed for rank increase for parents
RPL_MAX_TOTAL_RANK                          = 256*RPL_MIN_HOP_RANK_INCREASE*2 # 256 transmissions allowed for total path cost for parents
RPL_PARENT_SET_SIZE                         = 3

# === 6top states
SIX_STATE_IDLE                              = 0x00
# sending
SIX_STATE_SENDING_REQUEST                   = 0x01
# waiting for SendDone confirmation
SIX_STATE_WAIT_ADDREQUEST_SENDDONE          = 0x02
SIX_STATE_WAIT_DELETEREQUEST_SENDDONE       = 0x03
SIX_STATE_WAIT_RELOCATEREQUEST_SENDDONE     = 0x04
SIX_STATE_WAIT_COUNTREQUEST_SENDDONE        = 0x05
SIX_STATE_WAIT_LISTREQUEST_SENDDONE         = 0x06
SIX_STATE_WAIT_CLEARREQUEST_SENDDONE        = 0x07
# waiting for response from the neighbor
SIX_STATE_WAIT_ADDRESPONSE                  = 0x08
SIX_STATE_WAIT_DELETERESPONSE               = 0x09
SIX_STATE_WAIT_RELOCATERESPONSE             = 0x0a
SIX_STATE_WAIT_COUNTRESPONSE                = 0x0b
SIX_STATE_WAIT_LISTRESPONSE                 = 0x0c
SIX_STATE_WAIT_CLEARRESPONSE                = 0x0d
#response
SIX_STATE_REQUEST_ADD_RECEIVED              = 0x0e
SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE        = 0x0f
SIX_STATE_REQUEST_DELETE_RECEIVED           = 0x10
SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE     = 0x11

# === 6top commands
IANA_6TOP_CMD_ADD                           = 0x01 # add one or more cells
IANA_6TOP_CMD_DELETE                        = 0x02 # delete one or more cells
IANA_6TOP_CMD_RELOCATE                      = 0x03 # relocate one or more cells
IANA_6TOP_CMD_COUNT                         = 0x04 # count scheduled cells
IANA_6TOP_CMD_LIST                          = 0x05 # list the scheduled cells
IANA_6TOP_CMD_CLEAR                         = 0x06 # clear all cells

# === 6P return code
IANA_6TOP_RC_SUCCESS                        = 0x00 # operation succeeded
IANA_6TOP_RC_ERROR                          = 0x01 # generic error
IANA_6TOP_RC_EOL                            = 0x02 # end of list
IANA_6TOP_RC_RESET                          = 0x03 # critical error, reset
IANA_6TOP_RC_VER_ERR                        = 0x04 # unsupported 6P version
IANA_6TOP_RC_SFID_ERR                       = 0x05 # unsupported SFID
IANA_6TOP_RC_GEN_ERR                        = 0x06 # wrong schedule generation
IANA_6TOP_RC_BUSY                           = 0x07 # busy
IANA_6TOP_RC_NORES                          = 0x08 # not enough resources
IANA_6TOP_RC_CELLLIST_ERR                   = 0x09 # cellList error

# === sixlowpan
SIXLOWPAN_REASSEMBLY_BUFFER_LIFETIME        = 60 # in seconds
SIXLOWPAN_VRB_TABLE_ENTRY_LIFETIME          = 60 # in seconds

# === tsch
TSCH_QUEUE_SIZE                             = 10
TSCH_MAXTXRETRIES                           = 5
TSCH_MIN_BACKOFF_EXPONENT                   = 2
TSCH_MAX_BACKOFF_EXPONENT                   = 4

# === radio
RADIO_MAXDRIFT                              = 30 # in ppm
RADIO_STATE_IDLE                            = 'idle'
RADIO_STATE_TX                              = 'tx'
RADIO_STATE_RX                              = 'rx'

# === battery
# see A Realistic Energy Consumption Model for TSCH Networks.
# Xavier Vilajosana, Qin Wang, Fabien Chraim, Thomas Watteyne, Tengfei
# Chang, Kris Pister. IEEE Sensors, Vol. 14, No. 2, February 2014.
CHARGE_Idle_uC                              = 6.4
CHARGE_TxDataRxAck_uC                       = 54.5
CHARGE_TxData_uC                            = 49.5
CHARGE_TxDataRxAckNone_uC                   = 54.5
CHARGE_RxDataTxAck_uC                       = 32.6
CHARGE_RxData_uC                            = 22.6

BROADCAST_ADDRESS                           = 0xffff
