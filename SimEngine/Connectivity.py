#!/usr/bin/python
"""
Creates a connectivity matrix and provide methods to get the connectivity
between two motes.

The connectivity matrix is indexed by source id, destination id and channel offset.
Each cell of the matrix is a dict with the fields `pdr` and `rssi`

The connectivity matrix can be filled statically at startup or be updated along
time if a connectivity trace is given.

The propagate() method is called at every slot. It loops through the
transmissions occurring during that slot and checks if the transmission fails or
succeeds.
"""

# =========================== imports =========================================

import copy
import sys
import random
import math
from abc import abstractmethod
import gzip
from datetime import datetime
import json

import SimSettings
import SimEngine
from Mote.Mote import Mote
from Mote import MoteDefines as d

# =========================== defines =========================================

CONN_TYPE_TRACE         = "trace"

# =========================== helpers =========================================

# =========================== classes =========================================

class Connectivity(object):
    def __new__(cls):
        settings    = SimEngine.SimSettings.SimSettings()
        class_name  = 'Connectivity{0}'.format(settings.conn_class)
        return getattr(sys.modules[__name__], class_name)()

class ConnectivityBase(object):
    CONNECTIVITY_MATRIX_PERFECT_LINK = {
        'pdr' : 1.00,
        'rssi':  -10
    }
    CONNECTIVITY_MATRIX_NO_LINK = {
        'pdr' :     0,
        'rssi': -1000
    }

    # ===== start singleton
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectivityBase, cls).__new__(cls)
        return cls._instance
    # ===== end singleton

    def __init__(self):

        # ==== start singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        # ==== end singleton

        # store params

        # singletons (quicker access, instead of recreating every time)
        self.settings = SimSettings.SimSettings()
        self.engine   = SimEngine.SimEngine()
        self.log      = SimEngine.SimLog.SimLog().log

        # local variables
        self.connectivity_matrix = {} # described at the top of the file
        self.connectivity_matrix_timestamp = 0

        # at the beginning, connectivity matrix indicates no connectivity at all
        for source in self.engine.motes:
            self.connectivity_matrix[source.id] = {}
            for destination in self.engine.motes:
                self.connectivity_matrix[source.id][destination.id] = {}
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = copy.copy(
                        self.CONNECTIVITY_MATRIX_NO_LINK
                    )

        # introduce some connectivity in the matrix
        self._init_connectivity_matrix()

        # schedule propagation task
        self._schedule_propagate()

    def destroy(self):
        cls           = type(self)
        cls._instance = None
        cls._init     = False

    # ======================== abstract =======================================

    @abstractmethod
    def _init_connectivity_matrix(self):
        raise NotImplementedError() # abstractmethod

    # ======================== public =========================================

    # === getters

    def get_pdr(self, src_id, dst_id, channel):

        assert isinstance(src_id, int)
        assert isinstance(dst_id, int)
        assert isinstance(channel, int)

        return self.connectivity_matrix[src_id][dst_id][channel]["pdr"]

    def get_rssi(self, src_id, dst_id, channel):

        assert isinstance(src_id, int)
        assert isinstance(dst_id, int)
        assert isinstance(channel, int)

        if "rssi" not in self.connectivity_matrix[src_id][dst_id][channel]:
            pass
        return self.connectivity_matrix[src_id][dst_id][channel]["rssi"]

    # === propagation

    def propagate(self):
        """ Simulate the propagation of frames in a slot. """

        # local shorthands
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength

        # repeat propagation for each channel
        for channel in range(self.settings.phy_numChans):

            # === accounting

            # list all transmissions at that frequency
            alltransmissions = []
            for mote in self.engine.motes:
                if mote.radio.onGoingTransmission:
                    assert mote.radio.state == d.RADIO_STATE_TX
                    if mote.radio.onGoingTransmission['channel'] == channel:
                        thisTran = {}

                        # channel
                        thisTran['channel']    = channel

                        # packet
                        thisTran['tx_mote_id'] = mote.id
                        thisTran['packet']     = mote.radio.onGoingTransmission['packet']

                        # time at which the packet starts transmitting
                        thisTran['txTime']     = mote.tsch.clock.get_drift()

                        # number of ACKs received by this packet
                        thisTran['numACKs']    = 0

                        alltransmissions      += [thisTran]

            # === decide which listener gets which packet (rxDone)

            for listener_id in self._get_listener_id_list(channel):

                # random_value will be used for comparison against PDR
                random_value = random.random()

                # list the transmissions that listener can hear
                transmissions = []
                for t in alltransmissions:
                    pdr = self.get_pdr(
                        src_id  = t['tx_mote_id'],
                        dst_id  = listener_id,
                        channel = channel,
                    )

                    # you can interpret the following line as decision for
                    # reception of the preamble of 't'
                    if random_value < pdr:
                        transmissions += [t]

                if transmissions == []:
                    # no transmissions

                    # idle listen
                    sentAnAck = self.engine.motes[listener_id].radio.rxDone(
                        packet = None,
                    )
                    assert sentAnAck == False
                else:
                    # there are transmissions

                    # listener locks onto the earliest transmission
                    lockon_transmission = None
                    for t in transmissions:
                        if lockon_transmission is None or t['txTime']<lockon_transmission['txTime']:
                            lockon_transmission = t

                    # all other transmissions are now intereferers
                    interfering_transmissions = [t for t in transmissions if t!=lockon_transmission]
                    assert len(transmissions) == len(interfering_transmissions)+1

                    # log
                    if interfering_transmissions:
                        self.log(
                            SimEngine.SimLog.LOG_PROP_INTERFERENCE,
                            {
                                '_mote_id':                    listener_id,
                                'channel':                     lockon_transmission['channel'],
                                'lockon_transmission':         lockon_transmission['packet'],
                                'interfering_transmissions':   [t['packet'] for t in interfering_transmissions],
                            }
                        )

                    # calculate the resulting pdr when taking interferers into account
                    pdr = self._compute_pdr_with_interference(
                        listener_id               = listener_id,
                        lockon_transmission       = lockon_transmission,
                        interfering_transmissions = interfering_transmissions,
                    )

                    # decide whether listener receives lockon_transmission or not
                    if random_value < pdr:
                        # listener receives!

                        # lockon_transmission received correctly
                        sentAnAck = self.engine.motes[listener_id].radio.rxDone(
                            packet = lockon_transmission['packet'],
                        )

                        # keep track of the number of ACKs received by that transmission
                        if sentAnAck:
                            lockon_transmission['numACKs'] += 1

                    else:
                        # lockon_transmission NOT received correctly (interference)
                        sentAnAck = self.engine.motes[listener_id].radio.rxDone(
                            packet = None,
                        )
                        self.log(
                            SimEngine.SimLog.LOG_PROP_DROP_LOCKON,
                            {
                                '_mote_id':                    listener_id,
                                'channel':                     lockon_transmission['channel'],
                                'lockon_transmission':         lockon_transmission['packet']
                            }
                        )
                        assert sentAnAck == False

            # verify no more listener on this channel
            assert self._get_listener_id_list(channel) == []

            # === decide whether transmitters get an ACK (txDone)

            for t in alltransmissions:

                # decide whether transmitter received an ACK
                if   t['numACKs'] == 0:
                    isACKed = False
                elif t['numACKs'] == 1:
                    isACKed = True
                else:
                    # we do not expect multiple ACKs (would indicate duplicate MAC addresses)
                    raise SystemError()

                # indicate to source packet was sent
                self.engine.motes[t['tx_mote_id']].radio.txDone(isACKed)

            # verify no more radios active on this channel
            for mote in self.engine.motes:
                assert mote.radio.channel != channel

        # verify all radios off
        for mote in self.engine.motes:
            assert mote.radio.state == d.RADIO_STATE_OFF
            assert mote.radio.channel == None

        # schedule next propagation
        self._schedule_propagate()

    # ======================= private =========================================

    # === schedule

    def _schedule_propagate(self):
        '''
        schedule a propagation task in the middle of the next slot.
        FIXME: only schedule for next active slot.
        '''
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn() + 1,
            cb               = self.propagate,
            uniqueTag        = (None, 'Connectivity.propagate'),
            intraSlotOrder   = d.INTRASLOTORDER_PROPAGATE,
        )

    # === listeners

    def _get_listener_id_list(self, channel):
        returnVal = []
        for mote in self.engine.motes:
            if (mote.radio.state == d.RADIO_STATE_RX) and (mote.radio.channel == channel):
                returnVal.append(mote.id)
        return returnVal

    # === wireless

    def _compute_pdr_with_interference(self, listener_id, lockon_transmission, interfering_transmissions):

        # shorthand
        channel = lockon_transmission['channel']
        for t in interfering_transmissions:
            assert t['channel'] == channel
        lockon_tx_mote_id = lockon_transmission['tx_mote_id']

        # === compute the SINR

        noise_mW   = self._dBm_to_mW(self.engine.motes[listener_id].radio.noisepower)

        # S = RSSI - N

        signal_mW = self._dBm_to_mW(self.get_rssi(lockon_tx_mote_id, listener_id, channel)) - noise_mW
        if signal_mW < 0.0:
            # RSSI has not to be below the noise level.
            # If this happens, return very low SINR (-10.0dB)
            return -10.0

        # I = RSSI - N

        totalInterference_mW = 0.0
        for interfering_tran in interfering_transmissions:
            interfering_tx_mote_id = interfering_tran['tx_mote_id']
            interference_mW = self._dBm_to_mW(self.get_rssi(interfering_tx_mote_id, listener_id, channel)) - noise_mW
            if interference_mW < 0.0:
                # RSSI has not to be below noise level.
                # If this happens, set interference to 0.0
                interference_mW = 0.0
            totalInterference_mW += interference_mW

        sinr_dB = self._mW_to_dBm( signal_mW / (totalInterference_mW + noise_mW) )

        # === compute the interference PDR

        # shorthand
        noise_dBm = self.engine.motes[listener_id].radio.noisepower

        # RSSI of the interfering transmissions
        interference_rssi = self._mW_to_dBm(
            self._dBm_to_mW(sinr_dB + noise_dBm) +
            self._dBm_to_mW(noise_dBm)
        )

        # PDR of the interfering transmissions
        interference_pdr = self._rssi_to_pdr(interference_rssi)

        # === compute the resulting PDR

        lockon_pdr = self.get_pdr(
            src_id  = lockon_tx_mote_id,
            dst_id  = listener_id,
            channel = channel)
        returnVal = lockon_pdr * interference_pdr

        return returnVal

    # === helpers

    def _dBm_to_mW(self,dBm):
        return math.pow(10.0, dBm / 10.0)

    def _mW_to_dBm(self,mW):
        return 10 * math.log10(mW)

    def _rssi_to_pdr(self,rssi):
        """
        rssi and pdr relationship obtained by experiment below
        http://wsn.eecs.berkeley.edu/connectivity/?dataset=dust
        """

        rssi_pdr_table = {
            -97:    0.0000,  # this value is not from experiment
            -96:    0.1494,
            -95:    0.2340,
            -94:    0.4071,
            # <-- 50% PDR is here, at RSSI=-93.6
            -93:    0.6359,
            -92:    0.6866,
            -91:    0.7476,
            -90:    0.8603,
            -89:    0.8702,
            -88:    0.9324,
            -87:    0.9427,
            -86:    0.9562,
            -85:    0.9611,
            -84:    0.9739,
            -83:    0.9745,
            -82:    0.9844,
            -81:    0.9854,
            -80:    0.9903,
            -79:    1.0000,  # this value is not from experiment
        }

        minRssi = min(rssi_pdr_table.keys())
        maxRssi = max(rssi_pdr_table.keys())

        floorRssi = int(math.floor(rssi))
        if  floorRssi < minRssi:
            pdr = 0.0
        elif floorRssi >= maxRssi:
            pdr = 1.0
        else:
            pdrLow  = rssi_pdr_table[floorRssi]
            pdrHigh = rssi_pdr_table[floorRssi+1]
            # linear interpolation
            pdr = (pdrHigh - pdrLow) * (rssi - float(floorRssi)) + pdrLow

        assert 0 <= pdr <= 1.0

        return pdr

class ConnectivityFullyMeshed(ConnectivityBase):
    """
    All nodes can hear all nodes with PDR=100%.
    """

    def _init_connectivity_matrix(self):
        for source in self.engine.motes:
            for destination in self.engine.motes:
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = copy.copy(
                        self.CONNECTIVITY_MATRIX_PERFECT_LINK
                    )

class ConnectivityLinear(ConnectivityBase):
    """
    Perfect linear topology.
           100%     100%     100%       100%
        0 <----> 1 <----> 2 <----> ... <----> num_motes-1
    """

    def _init_connectivity_matrix(self):
        parent = None
        for mote in self.engine.motes:
            if parent is not None:
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[mote.id][parent.id][channel] = copy.copy(
                        self.CONNECTIVITY_MATRIX_PERFECT_LINK
                    )
                    self.connectivity_matrix[parent.id][mote.id][channel] = copy.copy(
                        self.CONNECTIVITY_MATRIX_PERFECT_LINK
                    )
            parent = mote

class ConnectivityK7(ConnectivityBase):
    """
    Replay K7 connectivity trace.
    """

    # ======================= inheritance =====================================

    # definitions of abstract methods

    def _init_connectivity_matrix(self):
        """ Fill the matrix using the connectivity trace"""

        # create the matrix (You take the red pill and stay in Wonderland)
        for source in self.engine.motes:
            self.connectivity_matrix[source.id] = {}
            for dest in self.engine.motes:
                self.connectivity_matrix[source.id][dest.id] = {}
                for chan in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][dest.id][chan] = copy.copy(
                        self.CONNECTIVITY_MATRIX_NO_LINK
                    )

        # load first trace transaction and init
        self.first_date = None
        with gzip.open(self.settings.conn_trace, 'r') as trace:
            trace_header = json.loads(trace.readline())
            csv_header = trace.readline().strip().split(',')

            for line in trace:
                # parse line
                row = self._parse_line(csv_header, line)

                # only read first transaction
                if row['transaction_id'] > 0:
                    break

                # save file position
                self.trace_position = trace.tell()

                # update matrix value
                first_channel = trace_header['channels'][0]
                for channel in row['channels']:
                    channel_offset = channel - first_channel
                    self.connectivity_matrix[row['src']][row['dst']][channel_offset] = {
                        'pdr': float(row['pdr']),
                        'rssi': row['mean_rssi'],
                    }

                # save matrix timestamp
                self.connectivity_matrix_timestamp = row['asn']

    # overloaded methods

    def get_pdr(self, src_id, dst_id, channel):
        # update PDR matrix if we are a new row in our K7 file
        if  self.connectivity_matrix_timestamp < self.engine.asn:
            self.connectivity_matrix_timestamp = self._update_connectivity_matrix_from_trace()

        # then call the parent's method
        return super(ConnectivityK7, self).get_pdr(src_id, dst_id, channel)

    def get_rssi(self, src_id, dst_id, channel):
        # update PDR matrix if we are a new row in our K7 file
        if  self.connectivity_matrix_timestamp < self.engine.asn:
            self.connectivity_matrix_timestamp = self._update_connectivity_matrix_from_trace()

        # then call the parent's method
        print src_id, dst_id, channel
        return super(ConnectivityK7, self).get_rssi(src_id, dst_id, channel)

    # ======================= private =========================================

    def _update_connectivity_matrix_from_trace(self):
        """ Read the connectivity trace and fill the connectivity matrix
        :return: Timestamp when to update the matrix again
        """

        with gzip.open(self.settings.conn_trace, 'r') as trace:
            trace_header = json.loads(trace.readline())
            csv_header = trace.readline().strip().split(',')

            # move to last recorded position
            trace.seek(self.trace_position)

            for line in trace:
                # parse line
                row = self._parse_line(csv_header, line)

                # save file position
                self.trace_position = trace.tell()

                # return next update ASN
                if row['asn'] > self.engine.asn:
                    return row['asn']

                # update matrix value
                first_channel = trace_header['channels'][0]
                for channel in row['channels']:
                    channel_offset = channel - first_channel
                    self.connectivity_matrix[row['src']][row['dst']][channel_offset] = {
                        'pdr': float(row['pdr']),
                        'rssi': row['mean_rssi'],
                    }

        raise Exception("""
                        Reached the end of the trace file without finding a matching row.
                        The simulation duration is longer than the trace duration.
                        """)

    def _parse_line(self, csv_header, line):
        # === read and parse line
        vals = line.strip().split(',')
        row = dict(zip(csv_header, vals))

        # === change row format

        row['src'] = int(row['src'])
        row['dst'] = int(row['dst'])
        row['transaction_id'] = int(row['transaction_id'])
        row['datetime'] = datetime.strptime(row['datetime'], "%Y-%m-%d %H:%M:%S")

        # rssi
        if row['mean_rssi'] == '':
            row['mean_rssi'] = self.CONNECTIVITY_MATRIX_NO_LINK['rssi']
        else:
            row['mean_rssi'] = float(row['mean_rssi'])

        # channel string to list
        row['channels'] = [int(c) for c in row['channels'].strip("[]").split(';')]

        # === add ASN value to row

        # save first row datetime if it does not exits
        if self.first_date is None:
            self.first_date = row['datetime']

        # convert row datetime to ASN
        time_delta = row['datetime'] - self.first_date
        row['asn'] = int(time_delta.total_seconds() / float(self.settings.tsch_slotDuration))

        return row

class ConnectivityRandom(ConnectivityBase):
    """Random (topology) connectivity using the Pister-Hack model

    Note that it doesn't guarantee every motes has always at least as
    many neighbors as 'conn_random_init_min_neighbors', who have good
    PDR values with the mote.

    Computed PDR and RSSI are computed on the fly; they could vary at
    every transmission.
    """

    def __init__(self):
        # the singleton has already been initialized
        cls = type(self)
        if cls._init:
            return

        # attributes specific to ConnectivityRandom
        self.coordinates = {}  # (x, y) indexed by mote_id
        self.pister_hack = PisterHackModel()

        # initialize the singleton
        super(ConnectivityRandom, self).__init__()


    def _init_connectivity_matrix(self):

        # ConnectivityRandom doesn't need the connectivity matrix. Instead, it
        # initializes coordinates of the motes. Its algorithm is:
        #
        # step.1 if moteid is 0
        #   step.1-1 set (0, 0) to its coordinate
        # step.2 otherwise
        #   step.2-1 set its (tentative) coordinate randomly
        #   step.2-2 count the number of neighbors with sufficient PDR (N)
        #   step.2-3 if the number of deployed motes are smaller than
        #          STABLE_NEIGHBORS
        #     step.2-3-1 if N is equal to the number of deployed motes, fix the
        #                coordinate of the mote
        #     step.2-3-2 otherwise, go back to step.2-1
        #   step.2-4 otherwise,
        #     step.2-4 if N is equal to or larger than STABLE_NEIGHBORS, fix
        #                the coordinate of the mote
        #     step.2-5 otherwise, go back to step.2-1

        # for quick access
        square_side        = self.settings.conn_random_square_side
        init_min_pdr       = self.settings.conn_random_init_min_pdr
        init_min_neighbors = self.settings.conn_random_init_min_neighbors

        assert init_min_neighbors <= self.settings.exec_numMotes

        # determine coordinates of the motes
        for target_mote in self.engine.motes:
            mote_is_deployed = False
            while mote_is_deployed is False:

                # select a tentative coordinate
                if target_mote.id == 0:
                    self.coordinates[target_mote.id] = (0, 0)
                    mote_is_deployed = True
                    continue

                coordinate = (
                    square_side * random.random(),
                    square_side * random.random()
                )

                # count deployed motes who have enough PDR values to this
                # mote
                good_pdr_count = 0
                for deployed_mote_id in self.coordinates.keys():
                    rssi = self.pister_hack.compute_rssi(
                        {
                            'mote'      : target_mote,
                            'coordinate': coordinate
                        },
                        {
                            'mote'      : self._get_mote(deployed_mote_id),
                            'coordinate': self.coordinates[deployed_mote_id]
                        }
                    )
                    pdr = self.pister_hack.convert_rssi_to_pdr(rssi)
                    # memorize the rssi and pdr values at channel 0
                    self._set_rssi(target_mote.id, deployed_mote_id, 0, rssi)
                    self._set_pdr(target_mote.id, deployed_mote_id, 0, pdr)

                    if init_min_pdr <= pdr:
                        good_pdr_count += 1

                # determine whether we deploy this mote or not
                if (
                        (
                            (len(self.coordinates) <= init_min_neighbors)
                            and
                            (len(self.coordinates) == good_pdr_count)
                        )
                        or
                        (
                            (init_min_neighbors < len(self.coordinates))
                            and
                            (init_min_neighbors <= good_pdr_count)
                        )
                    ):
                    # fix the coordinate of the mote
                    self.coordinates[target_mote.id] = coordinate
                    # copy the rssi and pdr values to other channels
                    for deployed_mote_id in self.coordinates.keys():
                        rssi = self.get_rssi(target_mote.id, deployed_mote_id, channel=0)
                        pdr  = self.get_pdr(target_mote.id, deployed_mote_id, channel=0)
                        for channel in range(1, self.settings.phy_numChans):
                            self._set_rssi(target_mote.id, deployed_mote_id, channel, rssi)
                            self._set_pdr(target_mote.id, deployed_mote_id, channel, pdr)
                    mote_is_deployed = True
                else:
                    # remove memorized values at channel 0
                    for deployed_mote_id in self.coordinates.keys():
                        self._clear_rssi(target_mote.id, deployed_mote_id, channel=0)
                        self._clear_pdr(target_mote.id, deployed_mote_id, channel=0)
                    # try another random coordinate
                    continue

    def _get_mote(self, mote_id):
        # there must be a mote having mote_id. otherwise, the following line
        # raises an exception.
        return [mote for mote in self.engine.motes if mote.id == mote_id][0]

    def _set_rssi(self, mote_id_1, mote_id_2, channel, rssi):
        # set the same RSSI to the both directions
        self.connectivity_matrix[mote_id_1][mote_id_2][channel]['rssi'] = rssi
        self.connectivity_matrix[mote_id_2][mote_id_1][channel]['rssi'] = rssi

    def _clear_rssi(self, mote_id_1, mote_id_2, channel):
        INVALID_RSSI = self.CONNECTIVITY_MATRIX_NO_LINK['rssi']
        self._set_rssi(mote_id_1, mote_id_2, channel, rssi=INVALID_RSSI)

    def _set_pdr(self, mote_id_1, mote_id_2, channel, pdr):
        # set the same RSSI to the both directions
        self.connectivity_matrix[mote_id_1][mote_id_2][channel]['pdr'] = pdr
        self.connectivity_matrix[mote_id_2][mote_id_1][channel]['pdr'] = pdr

    def _clear_pdr(self, mote_id_1, mote_id_2, channel):
        self._set_pdr(mote_id_1, mote_id_2, channel, pdr=0)


class PisterHackModel(object):

    PISTER_HACK_LOWER_SHIFT  =         40 # dB
    TWO_DOT_FOUR_GHZ         = 2400000000 # Hz
    SPEED_OF_LIGHT           =  299792458 # m/s

    # RSSI and PDR relationship obtained by experiment; dataset was available
    # at the link shown below:
    # http://wsn.eecs.berkeley.edu/connectivity/?dataset=dust
    RSSI_PDR_TABLE = {
        -97:    0.0000,  # this value is not from experiment
        -96:    0.1494,
        -95:    0.2340,
        -94:    0.4071,
        # <-- 50% PDR is here, at RSSI=-93.6
        -93:    0.6359,
        -92:    0.6866,
        -91:    0.7476,
        -90:    0.8603,
        -89:    0.8702,
        -88:    0.9324,
        -87:    0.9427,
        -86:    0.9562,
        -85:    0.9611,
        -84:    0.9739,
        -83:    0.9745,
        -82:    0.9844,
        -81:    0.9854,
        -80:    0.9903,
        -79:    1.0000,  # this value is not from experiment
    }

    def __init__(self):

        # singleton
        self.engine   = SimEngine.SimEngine()

        # remember what RSSI value is computed for a mote at an ASN; the same
        # RSSI value will be returned for the same motes and the ASN.
        self.rssi_cache = {} # indexed by (src_mote.id, dst_mote.id)

    def compute_mean_rssi(self, src, dst):
        # distance in meters
        distance = self._get_distance_in_meters(
            src['coordinate'],
            dst['coordinate']
        )

        # sqrt and inverse of the free space path loss (fspl)
        free_space_path_loss = (
            self.SPEED_OF_LIGHT / (4 * math.pi * distance * self.TWO_DOT_FOUR_GHZ)
        )

        # simple friis equation in Pr = Pt + Gt + Gr + 20log10(fspl)
        pr = (
            src['mote'].radio.txPower     +
            src['mote'].radio.antennaGain +
            dst['mote'].radio.antennaGain +
            (20 * math.log10(free_space_path_loss))
        )

        # according to the receiver power (RSSI) we can apply the Pister hack
        # model.
        return pr - self.PISTER_HACK_LOWER_SHIFT / 2    # choosing the "mean" value

    def compute_rssi(self, src, dst):
        """Compute RSSI between the points of a and b using Pister Hack"""

        assert sorted(src.keys()) == sorted(['mote', 'coordinate'])
        assert sorted(dst.keys()) == sorted(['mote', 'coordinate'])

        # compute the mean RSSI (== friis - 20)
        mu = self.compute_mean_rssi(src, dst)

        # the receiver will receive the packet with an rssi uniformly
        # distributed between friis and (friis - 40)
        rssi = (
            mu +
            random.uniform(
                -self.PISTER_HACK_LOWER_SHIFT/2,
                +self.PISTER_HACK_LOWER_SHIFT/2
            )
        )

        return rssi

    def convert_rssi_to_pdr(self, rssi):
        minRssi = min(self.RSSI_PDR_TABLE.keys())
        maxRssi = max(self.RSSI_PDR_TABLE.keys())

        if rssi < minRssi:
            pdr = 0.0
        elif rssi > maxRssi:
            pdr = 1.0
        else:
            floor_rssi = int(math.floor(rssi))
            pdr_low    = self.RSSI_PDR_TABLE[floor_rssi]
            pdr_high   = self.RSSI_PDR_TABLE[floor_rssi + 1]
            # linear interpolation
            pdr = (pdr_high - pdr_low) * (rssi - float(floor_rssi)) + pdr_low

        assert pdr >= 0.0
        assert pdr <= 1.0
        return pdr

    @staticmethod
    def _get_distance_in_meters(a, b):
        """Compute distance in meters between two points of a and b

        a and b are tuples which are 2D coordinates expressed in
        kilometers.
        """
        return 1000 * math.sqrt(
            pow((b[0] - a[0]), 2) +
            pow((b[1] - a[1]), 2)
        )
