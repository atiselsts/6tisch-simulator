#!/usr/bin/python
"""
Creates a connectivity matrix and provide methods to get the connectivity
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

import sys
import random
import math
from abc import abstractmethod

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

    # ===== start singleton
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectivityBase, cls).__new__(cls, *args, **kwargs)
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
        
        # connectivity matrix indicates no connectivity at all
        for source in self.engine.motes:
            self.connectivity_matrix[source.id] = {}
            for destination in self.engine.motes:
                self.connectivity_matrix[source.id][destination.id] = {}
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr":      0,
                        "rssi": -1000,
                    }
        
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
        raise NotImplementedError()
    
    # ======================== public =========================================
    
    # === getters
    
    def get_pdr(self, source, destination, channel):
        
        assert type(source)==int
        assert type(destination)==int
        assert type(channel)==int
        
        return self.connectivity_matrix[source][destination][channel]["pdr"]

    def get_rssi(self, source, destination, channel):
        
        assert type(source)==int
        assert type(destination)==int
        assert type(channel)==int
        
        return self.connectivity_matrix[source][destination][channel]["rssi"]
    
    # === propagation
    
    def propagate(self):
        """ Simulate the propagation of frames in a slot. """
        
        # local shorthands
        asn        = self.engine.getAsn()
        slotOffset = asn % self.settings.tsch_slotframeLength

        for channel in range(self.settings.phy_numChans):
            arrivalTime   = {} # dict of frame reception time
            transmissions = [] # list of transmission in the current slot

            # transmissions
            for mote in self.engine.motes:
                if mote.radio.onGoingTransmission:
                    if mote.radio.onGoingTransmission['channel'] == channel:
                        transmissions.append(mote.radio.onGoingTransmission)

            # store arrival times of transmitted packets
            for transmission in transmissions:
                sender_id   = transmission['packet']['mac']['srcMac']
                sender_mote = self.engine.motes[sender_id]
                arrivalTime[sender_id] = sender_mote.tsch.computeTimeOffsetToDagRoot()

            for transmission in transmissions:
                
                senders   = self._get_senders(channel)    # list of motes in TX state on that channel
                receivers = self._get_receivers(channel)  # list of motes in rx state on that channel
                
                # log
                self.log(
                    SimEngine.SimLog.LOG_PROP_TRANSMISSION,
                    {
                        'channel':          transmission['channel'],
                        'packet':           transmission['packet'],
                        'destinations':     None,
                    }
                )
                
                # keep track of the number of ACKs
                numACKs = 0
                
                for receiver in receivers:
                    
                    # get interferers
                    # i.e motes that:
                    #     - send at same time and channel
                    #     - send with sufficient signal that the mote can receive
                    #     except the current transmission sender
                    interferers = []
                    for sender in senders:
                        if  (
                                self.settings.phy_minRssi < self.get_rssi(receiver, sender, channel=0) #FIXME: channel
                                and
                                sender != transmission['packet']['mac']['srcMac']
                            ):
                            interferers.append(sender)

                    # log
                    if interferers:
                        self.log(
                            SimEngine.SimLog.LOG_PROP_INTERFERENCE,
                            {
                                'source_id':     transmission['packet']['mac']['srcMac'],
                                'channel':       transmission['channel'],
                                'interferers':   interferers,
                            }
                        )

                    # lock on the first transmission
                    sender_locked_on = transmission['packet']['mac']['srcMac']
                    for itfr in senders:
                        if  (
                                arrivalTime[itfr] < arrivalTime[sender_locked_on]
                                and
                                self.settings.phy_minRssi < self.get_rssi(receiver, itfr, channel=0) # FIXME: channel
                            ):
                            # lock on interference
                            sender_locked_on = itfr

                    if sender_locked_on == transmission['packet']['mac']['srcMac']:
                        # mote locked in the current signal

                        # calculate pdr, including interference
                        pdr = self._compute_pdr_with_interference(
                            src_id          = transmission['packet']['mac']['srcMac'],
                            dst_id          = receiver,
                            interferers     = interferers,
                            channel         = transmission['channel'],
                        )

                        # try to send
                        if random.random() < pdr:
                            # deliver frame to this receiver; sentAnAck indicates whether that receiver sent an ACK
                            sentAnAck = self.engine.motes[receiver].radio.rxDone(
                                packet = transmission['packet'],
                            )
                            
                            # keep track of the number of ACKs received
                            if sentAnAck:
                                numACKs += 1

                        else:
                            # packet is NOT received correctly
                            self.engine.motes[receiver].radio.rxDone(
                                packet = None,
                            )
                    else:
                        # mote locked on an interfering signal

                        # receive the interference as if it was the right frame
                        pseudo_interferers = senders + [transmission['packet']['mac']['srcMac']]

                        # calculate PDR
                        pdr = self._compute_pdr_with_interference(
                            src_id          = sender_locked_on,
                            dst_id          = receiver,
                            interferers     = pseudo_interferers,
                            channel         = transmission['channel'],
                        )

                        # try to send
                        if random.random() < pdr and receiver.radio_isSync():
                            # success to receive the interference and realize collision
                            receiver.schedule[slotOffset]['rx_wrong_frame'] = True

                        # frame is not received
                        self.engine.motes[receiver].radio.rxDone(
                            packet = None,
                        )
                        
                # decide whether transmitter received an ACK
                assert numACKs in [0,1] # we do not expect multiple ACKs (would indicate duplicate MAC addresses)
                if numACKs==1:
                    isACKed = True
                else:
                    isACKed = False

                # indicate to source packet was sent
                self.engine.motes[transmission['packet']['mac']['srcMac']].radio.txDone(isACKed)

            # get remaining senders and receivers
            senders   = self._get_senders(channel)    # list of motes in tx state
            receivers = self._get_receivers(channel)  # list of motes in rx state

            # remaining receivers that did not receive a packet
            for receiver in receivers:
                
                # ignore mote that are not in rx state
                if self.engine.motes[receiver].radio.state != d.RADIO_STATE_RX:
                    continue

                # get interferers
                # i.e motes that:
                #     - send at same time and channel
                #     - send with sufficient signal that the mote can receive
                interferers = []
                for sender in senders:
                    if self.settings.phy_minRssi < self.get_rssi(receiver, sender, channel=0): # FIXME: channel
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
                    pdr = self._compute_pdr_with_interference(
                        src_id         = sender_locked_on,
                        dst_id         = receiver,
                        interferers    = senders,
                        channel        = self.engine.motes[receiver].radio.channel,
                    )

                    # pick a random number
                    if random.random() < pdr and receiver.radio_isSync():
                        # success to receive the interference and realize collision
                        receiver.schedule[slotOffset]['rx_wrong_frame'] = True

                # packet is not received
                self.engine.motes[receiver].radio.rxDone(
                    packet = None,
                )

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

    # === senders and receivers

    def _get_senders(self, channel):
        returnVal = []  
        for mote in self.engine.motes:
            if (mote.radio.state == d.RADIO_STATE_TX) and (mote.radio.channel == channel):
                returnVal.append(mote.id)
        return returnVal

    def _get_receivers(self, channel):
        returnVal = []
        for mote in self.engine.motes:
            if (mote.radio.state == d.RADIO_STATE_RX) and (mote.radio.channel == channel):
                returnVal.append(mote.id)
        return returnVal
    
    # === wireless
    
    def _compute_pdr_with_interference(self, src_id, dst_id, interferers, channel):
        """
        Returns the PDR of a link at a given time.
        The returned PDR is computed from the connectivity matrix and from
        internal interferences.
        :param Mote src_id:
        :param Mote destination:
        :param list interferers:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """
        
        assert type(src_id) == int
        assert type(dst_id) == int
        for interferer in interferers:
            assert type(interferer) == int
        
        matrix_pdr = self.get_pdr(src_id, dst_id, channel)

        sinr       = self._compute_sinr(src_id, dst_id, interferers)
        interference_pdr = self._compute_pdr_from_sinr(sinr, dst_id)

        return interference_pdr * matrix_pdr
    
    def _compute_sinr(self, source, destination, interferers):
        """ Compute the signal to interference plus noise ratio (SINR)

        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param list interferers:
        :return: The SINR
        :rtype: int
        """
        
        noise = self._dBm_to_mW(self.engine.motes[destination].radio.noisepower)
        # S = RSSI - N
        signal = self._dBm_to_mW(self.get_rssi(source, destination,channel=0)) - noise # FIXME: channel
        if signal < 0.0:
            # RSSI has not to be below noise level.
            # If this happens, return very low SINR (-10.0dB)
            return -10.0

        totalInterference = 0.0
        for interferer in interferers:
            # I = RSSI - N
            interference = self._dBm_to_mW(self.get_rssi(interferer, destination, channel=0)) - noise # FIXME: channel
            if interference < 0.0:
                # RSSI has not to be below noise level.
                # If this happens, set interference to 0.0
                interference = 0.0
            totalInterference += interference

        sinr = signal / (totalInterference + noise)

        return self._mW_to_dBm(sinr)

    def _compute_pdr_from_sinr(self, sinr, destination):
        """ Compute the packet delivery ration (PDR) from
            signal to interference plus noise ratio (SINR)

        :param int sinr:
        :param Mote.Mote destination:
        :return:
        :rtype: float
        """
        
        noisepower = self.engine.motes[destination].radio.noisepower
        
        equivalentRSSI = self._mW_to_dBm(
            self._dBm_to_mW(sinr + noisepower) +
            self._dBm_to_mW(noisepower)
        )

        pdr = self._rssi_to_pdr(equivalentRSSI)

        return pdr
    
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

class ConnectivityFullyMeshed(ConnectivityBase):
    """
    All nodes can hear all nodes with PDR=100%.
    """
    
    def _init_connectivity_matrix(self):
        for source in self.engine.motes:
            for destination in self.engine.motes:
                for channel in range(self.settings.phy_numChans):
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr":    1.00,
                        "rssi":    -10,
                    }

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
                    self.connectivity_matrix[mote.id][parent.id][channel] = {
                        "pdr": 1.00,
                        "rssi": -10,
                    }
                    self.connectivity_matrix[parent.id][mote.id][channel] = {
                        "pdr": 1.00,
                        "rssi": -10,
                    }
            parent = mote

class ConnectivityK7(ConnectivityBase):
    """
    Replay K7 connectivity trace.
    """
    
    # ======================= inheritance =====================================
    
    # definitions of abstract methods
    
    def _init_connectivity_matrix(self):
        """ Fill the matrix using the connectivity trace"""
        raise NotImplementedError()
    
    # overloaded methods
    
    def get_pdr(self, source, destination, channel):
        
        # update PDR matrix if we are a new row in our K7 file
        if  self.connectivity_matrix_timestamp < self.engine.asn:
            self._update_connectivity_matrix_from_trace()
        
        # then call the parent's method
        return super(ConnectivityK7, self).get_pdr(source, destination, channel)
    
    def get_rssi(self, source, destination, channel):
        
        # update PDR matrix if we are a new row in our K7 file
        if  self.connectivity_matrix_timestamp < self.engine.asn:
            self._update_connectivity_matrix_from_trace()
        
        # then call the parent's method
        return super(ConnectivityK7, self).get_rssi(source, destination, channel)
    
    # ======================= private =========================================
    
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

class ConnectivityPisterHack(ConnectivityBase):
    """
    Pister-Hack connectivity.
    """
    
    PISTER_HACK_LOWER_SHIFT =         40 # dB
    TWO_DOT_FOUR_GHZ        = 2400000000 # Hz
    SPEED_OF_LIGHT          =  299792458 # m/s
    
    def _init_connectivity_matrix(self):
        
        for source in self.engine.motes:
            for destination in self.engine.motes:
                for channel in range(self.settings.phy_numChans):
                    rssi = self._compute_rssi_pisterhack(source, destination)
                    pdr  = self._rssi_to_pdr(rssi)
                    self.connectivity_matrix[source.id][destination.id][channel] = {
                        "pdr": pdr,
                        "rssi": rssi,
                    }
    
    def _compute_rssi_pisterhack(mote, neighbor):
        """
        computes RSSI between any two nodes (not only neighbors)
        according to the Pister-hack model.
        """

        # distance in m
        distance = self._get_distance(mote, neighbor)

        # sqrt and inverse of the free space path loss
        fspl = self.SPEED_OF_LIGHT / (4 * math.pi * distance * self.TWO_DOT_FOUR_GHZ)

        # simple friis equation in Pr=Pt+Gt+Gr+20log10(c/4piR)
        pr = (mote.txPower + mote.antennaGain + neighbor.antennaGain +
              (20 * math.log10(fspl)))

        # according to the receiver power (RSSI) we can apply the Pister hack
        # model.
        rssi = pr - random.uniform(0, self.PISTER_HACK_LOWER_SHIFT)

        return rssi
    
    def _get_distance(mote, neighbor):
        """
        mote.x and mote.y are in km. This function returns the distance in m.
        """

        return 1000*math.sqrt((mote.x - neighbor.x)**2 +
                              (mote.y - neighbor.y)**2)
