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

import copy
import json
import traceback

import SimSettings
import SimEngine

# =========================== defines =========================================

# === simulator
LOG_SIMULATOR_STATE               = {'type': 'simulator.state',           'keys': ['state', 'name']}

# === packet drops
LOG_PACKET_DROPPED                = {'type': 'packet_dropped',            'keys': ['_mote_id','packet','reason']}
DROPREASON_NO_ROUTE               = 'no_route'
DROPREASON_TXQUEUE_FULL           = 'txqueue_full'
DROPREASON_NO_TX_CELLS            = 'no_tx_cells'
DROPREASON_MAX_RETRIES            = 'max_retries'
DROPREASON_REASSEMBLY_BUFFER_FULL = 'reassembly_buffer_full'
DROPREASON_VRB_TABLE_FULL         = 'vrb_table_full'

# === app
LOG_APP_TX                        = {'type': 'app.tx',                    'keys': ['_mote_id','packet']}
LOG_APP_RX                        = {'type': 'app.rx',                    'keys': ['_mote_id','packet']}

# === secjoin 
LOG_SECJOIN_TX                    = {'type': 'secjoin.tx',                'keys': ['_mote_id']}
LOG_SECJOIN_RX                    = {'type': 'secjoin.rx',                'keys': ['_mote_id']}
LOG_JOINED                        = {'type': 'secjoin.joined',            'keys': ['_mote_id']}

# === rpl
LOG_RPL_DIO_TX                    = {'type': 'rpl.dio.tx',                'keys': ['_mote_id','packet']}
LOG_RPL_DIO_RX                    = {'type': 'rpl.dio.rx',                'keys': ['_mote_id','packet']}
LOG_RPL_DAO_TX                    = {'type': 'rpl.dao.tx',                'keys': ['_mote_id','packet']}
LOG_RPL_DAO_RX                    = {'type': 'rpl.dao.rx',                'keys': ['_mote_id','packet']}
LOG_RPL_CHURN                     = {'type': 'rpl.churn',                 'keys': ['_mote_id','rank','preferredParent']}

# === 6LoWPAN
LOG_SIXLOWPAN_PKT_TX              = {'type': 'sixlowpan.pkt.tx',          'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_FWD             = {'type': 'sixlowpan.pkt.fwd',         'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_PKT_RX              = {'type': 'sixlowpan.pkt.rx',          'keys': ['_mote_id','packet']}
LOG_SIXLOWPAN_FRAG_GEN            = {'type': 'sixlowpan.frag.gen',        'keys': ['_mote_id','packet']}

# === sixp
LOG_SIXP_ADD_REQUEST_TX           = {'type': 'sixp.add_request.tx',       'keys': ['_mote_id','packet']}
LOG_SIXP_ADD_REQUEST_RX           = {'type': 'sixp.add_request.rx',       'keys': ['_mote_id','packet']}
LOG_SIXP_ADD_RESPONSE_TX          = {'type': 'sixp.add_response.tx',      'keys': ['_mote_id','packet']}
LOG_SIXP_ADD_RESPONSE_RX          = {'type': 'sixp.add_response.rx',      'keys': ['_mote_id','packet']}
LOG_SIXP_DELETE_REQUEST_TX        = {'type': 'sixp.delete_request.tx',    'keys': ['_mote_id','packet']}
LOG_SIXP_DELETE_REQUEST_RX        = {'type': 'sixp.delete_request.rx',    'keys': ['_mote_id','packet']}
LOG_SIXP_DELETE_RESPONSE_TX       = {'type': 'sixp.delete_response.tx',   'keys': ['_mote_id','packet']}
LOG_SIXP_DELETE_RESPONSE_RX       = {'type': 'sixp.delete_response.rx',   'keys': ['_mote_id','packet']}

# === tsch
LOG_TSCH_SYNCED                   = {'type': 'tsch.synced',               'keys': ['_mote_id']}
LOG_TSCH_EB_TX                    = {'type': 'tsch.eb.tx',                'keys': ['_mote_id','packet']}
LOG_TSCH_EB_RX                    = {'type': 'tsch.eb.rx',                'keys': ['_mote_id','packet']}
LOG_TSCH_ADD_CELL                 = {'type': 'tsch.add_cell',             'keys': ['_mote_id','slotOffset','channelOffset','neighbor','cellOptions']}
LOG_TSCH_DELETE_CELL              = {'type': 'tsch.delete_cell',          'keys': ['_mote_id','slotOffset','channelOffset','neighbor','cellOptions']}
LOG_TSCH_TXDONE                   = {'type': 'tsch.txdone',               'keys': ['_mote_id','channel','packet','isACKed']}
LOG_TSCH_RXDONE                   = {'type': 'tsch.rxdone',               'keys': ['_mote_id','packet']}
LOG_TSCH_BACKOFFCHANGED           = {'type': 'tsch.backoff.changed',      'keys': ['_mote_id','cell']}

# === batt
LOG_BATT_CHARGE                   = {'type': 'batt.charge',               'keys': ['_mote_id','charge']}

# === propagation
LOG_PROP_TRANSMISSION             = {'type': 'prop.transmission',         'keys': ['channel','packet']}
LOG_PROP_INTERFERENCE             = {'type': 'prop.interference',         'keys': ['_mote_id','channel','lockon_transmission','interfering_transmissions']}

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

        # open log file
        self.log_output_file = open(self.settings.getOutputFile(), 'a')

        # write config to log file; if a file with the same file name exists,
        # append logs to the file. this happens if you multiple runs on the
        # same CPU. And amend config line; config line in log file should have
        # '_type' field. And 'run_id' type should be '_run_id'
        config_line = copy.deepcopy(self.settings.__dict__)
        config_line['_type']   = 'config'
        config_line['_run_id'] = config_line['run_id']
        del config_line['run_id']
        json_string = json.dumps(config_line)
        self.log_output_file.write(json_string + '\n')

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
        try:
            json_string = json.dumps(content, sort_keys=True)
            self.log_output_file.write(json_string + '\n')
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

    def flush(self):
        # flush the internal buffer, write data to the file
        assert not self.log_output_file.closed
        self.log_output_file.flush()

    def set_simengine(self, engine):
        self.engine = engine

    def set_log_filters(self, log_filters):
        self.log_filters = log_filters

    def destroy(self):
        # close log file
        if not self.log_output_file.closed:
            self.log_output_file.close()

        cls = type(self)
        cls._instance       = None
        cls._init           = False

    # ============================== private ==================================
