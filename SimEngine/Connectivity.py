#!/usr/bin/python
"""
Connectivity Module.

Creates a 3D connectivity matrix and provide methods to get the connectivity
between two motes.

The connectivity matrix is index by source id, destination id and channel.
Each cell of the matrix is a dict with the fields `pdr` and `rssi`

The connectivity matrix can be filled statically at startup or be updated along
time if a connectivity trace is given.

The propagate() method is called at every slot. It loops through the
transmissions occurring during that slot and checks if the transmission fails or
succeeds.
"""

# =========================== imports =========================================

import random
import math

import SimSettings
import SimEngine
from Mote.Mote import Mote
from Mote import MoteDefines as d

# =========================== defines =========================================

PISTER_HACK_LOWER_SHIFT = 40   # dB
TWO_DOT_FOUR_GHZ = 2400000000  # Hz
SPEED_OF_LIGHT = 299792458     # m/s

CONN_TYPE_TRACE         = "trace"
CONN_TYPE_FULLY_MESHED  = "fully_meshed"
CONN_TYPE_LINEAR        = "linear"
CONN_TYPE_TWO_BRANCHES  = "two_branches"
CONN_TYPE_PISTER_HACK   = "pister_hack"

# =========================== helpers =========================================

def _dBm_to_mW(dBm):
    """ translate dBm to mW """
    return math.pow(10.0, dBm / 10.0)

def _mW_to_dBm(mW):
    """ translate dBm to mW """
    return 10 * math.log10(mW)

def _rssi_to_pdr(rssi):
    """
    rssi and pdr relationship obtained by experiment below
    http://wsn.eecs.berkeley.edu/connectivity/?dataset=dust

    :param float rssi:
    :return:
    :rtype: float
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

    if  rssi < minRssi:
        pdr = 0.0
    elif rssi > maxRssi:
        pdr = 1.0
    else:
        floorRssi = int(math.floor(rssi))
        pdrLow    = rssi_pdr_table[floorRssi]
        pdrHigh   = rssi_pdr_table[floorRssi+1]
        # linear interpolation
        pdr       = (pdrHigh - pdrLow) * (rssi - float(floorRssi)) + pdrLow

    assert 0 <= pdr <= 1.0

    return pdr

def _compute_rssi_pisterhack(mote, neighbor):
    """
    computes RSSI between any two nodes (not only neighbors)
    according to the Pister-hack model.
    """

    # distance in m
    distance = _get_distance(mote, neighbor)

    # sqrt and inverse of the free space path loss
    fspl = SPEED_OF_LIGHT / (4 * math.pi * distance * TWO_DOT_FOUR_GHZ)

    # simple friis equation in Pr=Pt+Gt+Gr+20log10(c/4piR)
    pr = (mote.txPower + mote.antennaGain + neighbor.antennaGain +
          (20 * math.log10(fspl)))

    # according to the receiver power (RSSI) we can apply the Pister hack
    # model.
    rssi = pr - random.uniform(0, PISTER_HACK_LOWER_SHIFT)

    return rssi

def _get_distance(mote, neighbor):
    """
    mote.x and mote.y are in km. This function returns the distance in m.
    """

    return 1000*math.sqrt((mote.x - neighbor.x)**2 +
                          (mote.y - neighbor.y)**2)

# =========================== classes =========================================

class Connectivity(object):

    # ===== start singleton
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Connectivity, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    # ===== end singleton

    def __init__(self):

        # ==== start singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        # ==== end singleton

        # get singletons
        self.settings = SimSettings.SimSettings()
        self.engine   = SimEngine.SimEngine()
        self.log      = SimEngine.SimLog.SimLog().log

        # local variables
        self.connectivity_matrix = {} # described at the top of the file
        self.connectivity_matrix_timestamp = 0

        # init connectivity matrix
        self._init_connectivity_matrix()

        # schedule propagation task
        self._schedule_propagate()

    def destroy(self):
        cls = type(self)
        cls._instance = None
        cls._init = False

    # ======================== public =========================================

    def propagate(self):
        """ Simulate the propagation of frames in a slot. """

        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        for channel in range(self.settings.phy_numChans):
            arrivalTime = {} # dict of frame reception time
            transmissions = [] # list of transmission in the current slot

            # transmissions
            for mote in self.engine.motes:
                if mote.radio.onGoingTransmission:
                    if mote.radio.onGoingTransmission['channel'] == channel:
                        transmissions.append(mote.radio.onGoingTransmission)

            # store arrival times of transmitted packets
            for transmission in transmissions:
                sender = transmission['smac']
                arrivalTime[transmission['smac']] = sender.tsch.getOffsetToDagRoot()

            for transmission in transmissions:
                isACKed = False
                isNACKed = False
                senders = self._get_senders(channel)  # list of motes in tx state
                receivers = self._get_receivers(channel)  # list of motes in rx state

                for receiver in receivers:
                    # get interferers
                    # i.e motes that:
                    #     - send at same time and channel
                    #     - send with sufficient signal that the mote can receive
                    #     except the current transmission sender
                    interferers = []
                    for sender in senders:
                        if (
                            self.settings.phy_minRssi < self.get_rssi(receiver, sender)
                            and sender.id != transmission['smac'].id
                        ):
                            interferers.append(sender)

                    # log
                    if len(interferers) > 0:
                        self.log(
                            SimEngine.SimLog.LOG_PROP_PROBABLE_COLLISION,
                            {
                                 "source_id": transmission['smac'].id,
                                 "channel": transmission['channel']
                             }
                        )

                    # lock on the first transmission
                    sender_locked_on = transmission['smac']
                    for itfr in senders:
                        if (
                            arrivalTime[itfr] < arrivalTime[sender_locked_on]
                            and self.settings.phy_minRssi < self.get_rssi(receiver, itfr)
                        ):
                            # lock on interference
                            sender_locked_on = itfr

                    if sender_locked_on == transmission['smac']:
                        # mote locked in the current signal

                        # calculate pdr, including interference
                        pdr = self.compute_pdr(transmission['smac'],
                                               receiver,
                                               interferers=interferers,
                                               channel=transmission['channel'])

                        # try to send
                        if random.random() < pdr:
                            # packet is received correctly
                            isACKed, isNACKed = receiver.radio.rxDone(**transmission)

                        else:
                            # packet is NOT received correctly
                            receiver.radio.rxDone()
                    else:
                        # mote locked on an interfering signal

                        # receive the interference as if it was the right frame
                        pseudo_interferers = senders + [transmission['smac']]

                        # calculate PDR
                        pdr = self.compute_pdr(sender_locked_on,
                                               receiver,
                                               interferers=pseudo_interferers,
                                               channel=transmission['channel'])

                        # try to send
                        if random.random() < pdr and receiver.radio_isSync():
                            # success to receive the interference and realize collision
                            receiver.schedule[ts]['rx_wrong_frame'] = True

                        # frame is not received
                        receiver.radio.rxDone()

                # indicate to source packet was sent
                transmission['smac'].radio.txDone(isACKed, isNACKed)

            # get remaining senders and receivers
            senders = self._get_senders(channel)  # list of motes in tx state
            receivers = self._get_receivers(channel)  # list of motes in rx state

            # remaining receivers that did not receive a packet
            for receiver in receivers:
                # ignore mote that are not in rx state
                if receiver.radio.state != d.RADIO_STATE_RX:
                    continue

                # get interferers
                # i.e motes that:
                #     - send at same time and channel
                #     - send with sufficient signal that the mote can receive
                interferers = []
                for sender in senders:
                    if (
                            self.settings.phy_minRssi < self.get_rssi(receiver, sender)
                    ):
                        interferers.append(sender)

                # lock on the first arrived transmission
                sender_locked_on = None
                for itfr in interferers:
                    if not sender_locked_on:
                        sender_locked_on = itfr
                    else:
                        if arrivalTime[itfr] < arrivalTime[sender_locked_on]:
                            sender_locked_on = itfr

                # if locked, try to receive the frame
                if sender_locked_on:
                    # pdr calculation
                    pdr = self.compute_pdr(sender_locked_on,
                                           receiver,
                                           interferers=senders,
                                           channel=receiver.radio.channel)

                    # pick a random number
                    if random.random() < pdr and receiver.radio_isSync():
                        # success to receive the interference and realize collision
                        receiver.schedule[ts]['rx_wrong_frame'] = True

                # packet is not received
                receiver.radio.rxDone()

        # schedule next propagation
        self._schedule_propagate()

    def compute_pdr(self, source, destination, interferers, channel=None):
        """
        Returns the PDR of a link at a given time.
        The returned PDR is computed from the connectivity matrix and from
        internal interferences.
        :param Mote source:
        :param Mote destination:
        :param list interferers:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """

        matrix_pdr = self.get_pdr(source, destination, channel)

        sinr = self._compute_sinr(source, destination, interferers)
        interference_pdr = self._compute_pdr_from_sinr(sinr, destination)

        return interference_pdr * matrix_pdr

    def get_pdr(self, source, destination, channel=None):
        """
        Returns the PDR of a link.
        The value is taken form the connectivity matrix.
        :param Mote source:
        :param Mote destination:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """
        if (
            self.settings.conn_type == CONN_TYPE_TRACE
            and self.connectivity_matrix_timestamp < self.engine.asn
        ):
            self._update_connectivity_matrix_from_trace()

        return self.connectivity_matrix[source.id][destination.id][channel]["pdr"]

    def get_rssi(self, source, destination, channel=0): # TODO which default channel to use ?
        """
        Returns the RSSI of a link.
        The value is taken form the connectivity matrix.
        :param Mote source:
        :param Mote destination:
        :param int channel:
        :return: The link mean RSSI
        :rtype: float
        """
        if (
                self.settings.conn_type == CONN_TYPE_TRACE
                and self.connectivity_matrix_timestamp < self.engine.asn
        ):
            self._update_connectivity_matrix_from_trace()

        return self.connectivity_matrix[source.id][destination.id][channel]["rssi"]

    # ======================= private =========================================

    def _init_connectivity_matrix(self):
        """ Creates a 3D matrix (source, destination, channel) """

        # init the matrix with None values
        self.connectivity_matrix = {}
        for source in self.engine.motes:
            self.connectivity_matrix[source.id] = {}
            for destination in self.engine.motes:
                self.connectivity_matrix[source.id][destination.id] = {}
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr": None,
                        "rssi": None,
                    }

        # call a method to fill connectivity matrix with values depending on the
        # connectivity type defined in the settings
        getattr(self, "_fill_connectivity_matrix_{0}".format(self.settings.conn_type))()

    # === fill

    def _fill_connectivity_matrix_fully_meshed(self):
        """ Fill the matrix with PDR = 100 and RSSI = -10 """
        for source in self.engine.motes:
            for destination in self.engine.motes:
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr": 100,
                        "rssi": -10}

    def _fill_connectivity_matrix_linear(self):
        """ creates a static connectivity linear path
            0 <-- 1 <-- 2 <-- ... <-- num_motes
        """
        parent = None
        for mote in self.engine.motes:
            if parent is not None:
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[mote.id][parent.id][channel] = {
                        "pdr": 100,
                        "rssi": -10}
                    self.connectivity_matrix[parent.id][mote.id][channel] = {
                        "pdr": 100,
                        "rssi": -10}
            parent = mote

    def _fill_connectivity_matrix_two_branches(self):
        raise NotImplementedError

    def _fill_connectivity_matrix_pisterhack(self):
        """ Fill the matrix using the Pister Hack model
            This requires that the motes have positions
        """
        for source in self.engine.motes:
            for destination in self.engine.motes:
                for channel in range(self.settings.phy_numChans):
                    rssi = _compute_rssi_pisterhack(source, destination)
                    pdr = _rssi_to_pdr(rssi)
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr": pdr,
                        "rssi": rssi,
                    }

    def _fill_connectivity_matrix_trace(self):
        """ Fill the matrix using the connectivity trace"""
        raise NotImplementedError

    # === update

    def _update_connectivity_matrix_from_trace(self):
        """
        :return: Timestamp when to update the matrix again
        """

        first_line = None
        with open(self.settings.conn_trace, 'r') as trace:
            trace.readline()  # ignore header
            self.csv_header = trace.readline().split(',')
            for line in trace:
                # read and parse line
                vals = line.split(',')
                row = dict(zip(self.csv_header, vals))

                if first_line is None:
                    first_line = line
                else:
                    if line == first_line:
                        return row['datetime']

                # update matrix value
                self.connectivity_matrix[row['src']][row['dst']][row['channel']] = row['pdr']

    # === schedule

    def _schedule_propagate(self):
        self.engine.scheduleAtAsn(
            asn         = self.engine.getAsn() + 1, # so propagation happens in next slot
            cb          = self.propagate,
            uniqueTag   = (None, 'propagation'),
            priority    = 1,
        )

    # === sinr and pdr

    def _compute_sinr(self, source, destination, interferers):
        """ Compute the signal to interference plus noise ratio (SINR)

        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param list interferers:
        :return: The SINR
        :rtype: int
        """

        noise = _dBm_to_mW(destination.radio.noisepower)
        # S = RSSI - N
        signal = _dBm_to_mW(self.get_rssi(source, destination)) - noise
        if signal < 0.0:
            # RSSI has not to be below noise level.
            # If this happens, return very low SINR (-10.0dB)
            return -10.0

        totalInterference = 0.0
        for interferer in interferers:
            # I = RSSI - N
            interference = _dBm_to_mW(self.get_rssi(interferer, destination)) - noise
            if interference < 0.0:
                # RSSI has not to be below noise level.
                # If this happens, set interference to 0.0
                interference = 0.0
            totalInterference += interference

        sinr = signal / (totalInterference + noise)

        return _mW_to_dBm(sinr)

    @staticmethod
    def _compute_pdr_from_sinr(sinr, destination):
        """ Compute the packet delivery ration (PDR) from
            signal to interference plus noise ratio (SINR)

        :param int sinr:
        :param Mote.Mote destination:
        :return:
        :rtype: float
        """

        equivalentRSSI = _mW_to_dBm(
            _dBm_to_mW(sinr + destination.radio.noisepower) +
            _dBm_to_mW(destination.radio.noisepower)
        )

        pdr = _rssi_to_pdr(equivalentRSSI)

        return pdr

    # === senders and receivers

    def _get_senders(self, channel):
        """Returns a list of motes transmitting on a given channel in the current ASN"""
        senders = []  # list of motes in tx state
        for mote in self.engine.motes:
            if (mote.radio.state == d.RADIO_STATE_TX) and (mote.radio.channel == channel):
                senders.append(mote)

        return senders

    def _get_receivers(self, channel):
        """Returns a list of motes listening on a given channel in the current ASN"""
        receivers = []  # list of motes in rx state
        for mote in self.engine.motes:
            if (mote.radio.state == d.RADIO_STATE_RX) and (mote.radio.channel == channel):
                receivers.append(mote)

        return receivers