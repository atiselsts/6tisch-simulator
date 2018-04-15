#!/usr/bin/python
"""
\brief Wireless propagation model.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
"""

#============================ imports =========================================

import threading
import random
import math
from datetime import timedelta

from k7 import k7

import Topology
import SimSettings
import SimEngine
import Mote

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Propagation')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

#============================ defines =========================================



#============================ functions =======================================

def _dBmTomW(dBm):
    """ translate dBm to mW """
    return math.pow(10.0, dBm / 10.0)


def _mWTodBm(mW):
    """ translate dBm to mW """
    return 10 * math.log10(mW)

#============================ classes =========================================

class Propagation(object):

    def __new__(cls, *args, **kwargs):
        """
        This method instantiates the proper `Propagate` class given the simulator settings.
        :return: a Propagate class depending on the settings
        :rtype: PropagationFromModel | PropagationFormTrace
        """
        settings = SimSettings.SimSettings()
        if hasattr(settings, 'prop_type'):
            if settings.prop_type == 'trace':
                return PropagationTrace(settings.prop_trace)
            elif settings.prop_type == 'pisterhack':
                return PropagationPisterHack()
        else:
            return PropagationPisterHack()

class PropagationCreator(object):
    """
    This class is a meta class, it is not meant to be instantiated.
    """

    #===== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PropagationCreator, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton

    def __init__(self):
        #===== start singleton
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        #===== end singleton

        # store params
        self.settings                  = SimSettings.SimSettings()
        self.engine                    = SimEngine.SimEngine()

        # variables
        self.dataLock                  = threading.Lock()
        self.receivers                 = [] # motes with radios currently listening
        self.transmissions             = [] # ongoing transmissions
        self.slotframe_length          = self.settings.tsch_slotframeLength
        self.slot_duration             = self.settings.tsch_slotDuration
        self.with_interferences        = not self.settings.noInterference
        self.minRssi                   = self.settings.minRssi # dBm

        # schedule propagation task
        self._schedule_propagate()

    def destroy(self):
        self._instance                 = None
        self._init                     = False
        del self.__dict__

    #======================== public ==========================================

    #===== communication

    def startRx(self, mote, channel):
        """ add a mote as listener on a channel"""
        with self.dataLock:
            self.receivers += [{
                'mote':                mote,
                'channel':             channel,
            }]

    def startTx(self, channel, type, code, smac, dmac, srcIp, dstIp, srcRoute, payload):
        """ add a mote as using a channel for tx"""
        with self.dataLock:
            self.transmissions  += [{
                'channel':             channel,
                'type':                type,
                'code':                code,
                'smac':                smac,
                'dmac':                dmac,
                'srcIp':               srcIp,
                'dstIp':               dstIp,
                'sourceRoute':         srcRoute,
                'payload':             payload,
            }]

    def propagate(self):
        """ Simulate the propagation of pkts in a slot. """

        with self.dataLock:

            asn   = self.engine.getAsn()
            ts    = asn % self.slotframe_length

            arrivalTime = {}

            # store arrival times of transmitted packets
            for transmission in self.transmissions:
                arrivalTime[transmission['smac']] = transmission['smac'].clock_getOffsetToDagRoot()

            for transmission in self.transmissions:

                i           = 0 # index of a receiver
                isACKed     = False
                isNACKed    = False

                while i < len(self.receivers):

                    if self.receivers[i]['channel'] == transmission['channel']:
                        # this receiver is listening on the right channel

                        if self.receivers[i]['mote'] in transmission['dmac']:
                            # this packet is destined for this mote

                            if self.with_interferences:

                                # other transmissions on the same channel?
                                interferers = [t['smac'] for t in self.transmissions if (t != transmission) and (t['channel'] == transmission['channel'])]

                                interferenceFlag = 0
                                for itfr in interferers:
                                    if self.get_rssi(self.receivers[i]['mote'], itfr) > self.minRssi:
                                        interferenceFlag = 1

                                transmission['smac'].schedule[ts]['debug_interference'] += [interferenceFlag] # debug only

                                if interferenceFlag:
                                    transmission['smac'].stats_incrementRadioStats('probableCollisions')
                                if transmission['smac'].schedule[ts]['dir'] == Mote.DIR_TXRX_SHARED:
                                    if interferenceFlag:
                                        transmission['smac'].stats_sharedCellCollisionSignal()
                                    else:
                                        transmission['smac'].stats_sharedCellSuccessSignal()

                                lockOn = transmission['smac']
                                for itfr in interferers:
                                    if arrivalTime[itfr] < arrivalTime[lockOn] and self.get_rssi(self.receivers[i]['mote'], itfr) > self.minRssi:
                                        # lock on interference
                                        lockOn = itfr

                                if lockOn == transmission['smac']:
                                    # mote locked in the current signal

                                    transmission['smac'].schedule[ts]['debug_lockInterference'] += [0] # debug only

                                    # calculate pdr, including interference
                                    pdr = self.get_pdr(transmission['smac'], self.receivers[i]['mote'],
                                                       asn=asn, interferers=interferers,
                                                       channel=transmission['channel'])

                                    # pick a random number
                                    failure = random.random()
                                    if pdr >= failure:
                                        # packet is received correctly
                                        # this mote is delivered the packet
                                        isACKed, isNACKed = self.receivers[i]['mote'].radio_rxDone(
                                            type       = transmission['type'],
                                            code       = transmission['code'],
                                            smac       = transmission['smac'],
                                            dmac       = transmission['dmac'],
                                            srcIp      = transmission['srcIp'],
                                            dstIp      = transmission['dstIp'],
                                            srcRoute   = transmission['sourceRoute'],
                                            payload    = transmission['payload']
                                        )
                                        # this mote stops listening
                                        del self.receivers[i]

                                    else:
                                        # packet is NOT received correctly
                                        self.receivers[i]['mote'].radio_rxDone()
                                        del self.receivers[i]

                                else:
                                    # mote locked in an interfering signal

                                    # for debug
                                    transmission['smac'].schedule[ts]['debug_lockInterference'] += [1]

                                    # receive the interference as if it's a desired packet
                                    interferers.remove(lockOn)
                                    pseudo_interferers = interferers + [transmission['smac']]

                                    # calculate SINR where locked interference and other signals are considered S and I+N respectively
                                    pseudo_pdr = self.get_pdr(lockOn, self.receivers[i]['mote'],
                                                              asn=asn, interferers=pseudo_interferers,
                                                              channel=transmission['channel'])

                                    # pick a random number
                                    failure = random.random()
                                    if pseudo_pdr >= failure and self.receivers[i]['mote'].radio_isSync():
                                        # success to receive the interference and realize collision
                                        self.receivers[i]['mote'].schedule[ts]['rxDetectedCollision'] = True

                                    # desired packet is not received
                                    self.receivers[i]['mote'].radio_rxDone()
                                    del self.receivers[i]

                            else:  # ================ without interference ========

                                transmission['smac'].schedule[ts]['debug_interference']     += [0] # for debug only
                                transmission['smac'].schedule[ts]['debug_lockInterference'] += [0] # for debug only

                                # calculate pdr with no interference
                                pdr = self.get_pdr(transmission['smac'], self.receivers[i]['mote'],
                                                   asn=asn, channel=transmission['channel'])

                                # pick a random number
                                failure = random.random()

                                if pdr >= failure:
                                    # packet is received correctly

                                    # this mote is delivered the packet
                                    isACKed, isNACKed = self.receivers[i]['mote'].radio_rxDone(
                                        type       = transmission['type'],
                                        code       = transmission['code'],
                                        smac       = transmission['smac'],
                                        dmac       = transmission['dmac'],
                                        srcIp      = transmission['srcIp'],
                                        dstIp      = transmission['dstIp'],
                                        srcRoute   = transmission['sourceRoute'],
                                        payload    = transmission['payload']
                                    )

                                    # this mote stops listening
                                    del self.receivers[i]

                                else:
                                    # packet is NOT received correctly
                                    self.receivers[i]['mote'].radio_rxDone()
                                    del self.receivers[i]

                        else:
                            # this packet is NOT destined for this mote

                            # move to the next receiver
                            i += 1

                    else:
                        # this receiver is NOT listening on the right channel

                        # move to the next receiver
                        i += 1

                # indicate to source packet was sent
                transmission['smac'].radio_txDone(isACKed, isNACKed)

            # remaining receivers that do not receive a desired packet
            for r in self.receivers:

                if self.with_interferences:

                    interferers = [t['smac'] for t in self.transmissions if t['dmac'] != r['mote'] and t['channel'] == r['channel']]

                    lockOn = None
                    for itfr in interferers:

                        if not lockOn:
                            if self.get_rssi(r['mote'], itfr) > self.minRssi:
                                lockOn = itfr
                        else:
                            if self.get_rssi(r['mote'], itfr) > self.minRssi and arrivalTime[itfr] < arrivalTime[lockOn]:
                                lockOn = itfr

                    if lockOn:
                        # pdr calculation

                        # receive the interference as if it's a desired packet
                        interferers.remove(lockOn)

                        # calculate SINR where locked interference and other signals are considered S and I+N respectively
                        pseudo_pdr = self.get_pdr(lockOn, r['mote'],
                                                  asn=asn,
                                                  interferers=interferers,
                                                  channel=r['channel'])

                        # pick a random number
                        failure = random.random()
                        if pseudo_pdr >= failure and r['mote'].radio_isSync():
                            # success to receive the interference and realize collision
                            r['mote'].schedule[ts]['rxDetectedCollision'] = True

                # desired packet is not received
                r['mote'].radio_rxDone()

            # clear all outstanding transmissions
            self.transmissions              = []
            self.receivers                  = []

        self._schedule_propagate()

    def get_pdr(self, source, destination, asn=0, interferers=None, channel=None):
        """
        Returns the PDR of a link at a given time.
        :param Mote source:
        :param Mote destination:
        :param int asn:
        :param list interferers:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """
        raise NotImplementedError

    def get_rssi(self, source, destination, asn=0, channel=None):
        """
        Returns the RSSI of a link at a given time.
        :param Mote source:
        :param Mote destination:
        :param int asn:
        :param int channel:
        :return: The link mean RSSI
        :rtype: float
        """
        raise NotImplementedError

    # ======================= private =========================================

    def _schedule_propagate(self):
        with self.dataLock:
            self.engine.scheduleAtAsn(
                asn         = self.engine.getAsn() + 1, # so propagation happens in next slot
                cb          = self.propagate,
                uniqueTag   = (None, 'propagation'),
                priority    = 1,
            )

# ==================== Propagation From Model =================================

class PropagationPisterHack(PropagationCreator):
    _initchild = False

    def __init__(self):
        super(PropagationPisterHack, self).__init__()

        # ===== start singleton
        # don't re-initialize an instance (needed because singleton)
        if self._initchild:
            return
        self._initchild = True
        # ===== end singleton
        log.debug("Init Propagation using the Pister Hack model.")

        self.type = "pister-hack"

    def get_pdr(self, source, destination, asn=0, interferers=None, channel=None):
        """
        Returns the PDR of a link at a given time.
        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param int asn:
        :param list interferers:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """

        if interferers is None:
            interferers = []

        sinr  = self._computeSINR(source, destination, interferers)
        return self._computePdrFromSINR(sinr, destination)

    def get_rssi(self, source, destination, asn=0, channel=None):
        """
        Returns the RSSI of a link at a given time.
        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param int asn:
        :param int channel:
        :return: The link mean RSSI
        :rtype: float
        """
        return source.getRSSI(destination)

    # ======================== private ========================================

    def _computeSINR(self, source, destination, interferers):
        """ Compute the signal to noise ratio (SINR)

        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param kist interferers:
        :return: The SINR
        :rtype: int
        """

        noise = _dBmTomW(destination.noisepower)
        # S = RSSI - N
        signal = _dBmTomW(self.get_rssi(source, destination)) - noise
        if signal < 0.0:
            # RSSI has not to be below noise level. If this happens, return very low SINR (-10.0dB)
            return -10.0

        totalInterference = 0.0
        for interferer in interferers:
            # I = RSSI - N
            interference = _dBmTomW(self.get_rssi(interferer, destination)) - noise
            if interference < 0.0:
                # RSSI has not to be below noise level. If this happens, set interference 0.0
                interference = 0.0
            totalInterference += interference

        sinr = signal / (totalInterference + noise)

        return _mWTodBm(sinr)

    @staticmethod
    def _computePdrFromSINR(sinr, destination):
        """ Compute the packet delivery ration (PDR) from signal to noise ratio (SINR)

        :param int sinr:
        :param Mote.Mote destination:
        :return:
        :rtype: float
        """

        equivalentRSSI = _mWTodBm(
            _dBmTomW(sinr + destination.noisepower) +
            _dBmTomW(destination.noisepower)
        )

        pdr = Topology.Topology.rssiToPdr(equivalentRSSI)

        return pdr

# ==================== Propagation From Trace =================================

class PropagationTrace(PropagationCreator):

    _initchild = False

    def __init__(self, trace):
        super(PropagationTrace, self).__init__()

        # ===== start singleton
        # don't re-initialize an instance (needed because singleton)
        if self._initchild:
            return
        self._initchild = True
        # ===== end singleton
        log.debug("Init Propagation using a trace.")

        self.type = "trace"
        self.header, self.trace = k7.read(trace)
        self.num_motes = self.header['node_count']

        # start date is when we have at least one value per source
        self.start_date = self.trace.groupby(["src"]).apply(lambda x: x.index[0]).max()
        self.stop_date = self.trace.index[-1]

        # create a dict containing transaction durations
        self.transaction_times = {}
        for source, source_df in self.trace.groupby(["src"]):
            start_date = None
            prev_id = None
            for t_id, t_df in source_df.groupby(["transaction_id"]):
                if start_date is not None and prev_id is not None:
                    # save previous transaction times
                    self.transaction_times[(source, prev_id)] = {"start": start_date,
                                                                 "stop": t_df.index.min() - timedelta(seconds=1)}
                start_date = t_df.index.min()
                prev_id = t_id

        log.debug("Trace loaded.")

    def get_pdr(self, source, destination, asn=0, interferers=None, channel=None):
        """
        Returns the PDR of a link at a given time.
        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param int asn:
        :param list interferers:
        :param int channel:
        :return: The link PDR
        :rtype: float
        """

        pdr = 0

        row = self.read_trace(source, destination, asn, channel)

        if row is not None:
            pdr = row.pdr
        if not 0 <= pdr <= 1:
            raise Exception("PDR value is not between 0 and 1.")
        log.debug("Source id: {0}, Destination id: {1}, pdr: {2}".format(source.id, destination.id, pdr))

        return pdr

    def get_rssi(self, source, destination, asn=0, channel=None):
        """
        Returns the RSSI of a link at a given time.
        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param int asn:
        :param int channel:
        :return: The link mean RSSI. If RSSI is not found in the trace, returns -100
        :rtype: float
        """

        rssi = -100

        row = self.read_trace(source, destination, asn, channel)

        if row is not None:
            rssi = row.mean_rssi
        if not -100 <= rssi <= 0:
            raise Exception("RSSI value is not between -100 and 0.")
        log.debug("Source id: {0}, Destination id: {1}, rssi: {2}".format(source.id, destination.id, rssi))

        return rssi

    def read_trace(self, source, destination, asn, channel):
        """
        Read the trace and return the first matching row.
        If there is no match, returns None
        :param Mote.Mote source:
        :param Mote.Mote destination:
        :param int asn:
        :param int channel:
        :return: None | pandas.core.series.Series
        """

        # convert asn to trace time
        current_absolute_time = asn * self.slot_duration
        current_relative_time = self.start_date + timedelta(seconds=current_absolute_time)

        # make sure simulation time does not exceed trace time
        if current_relative_time > self.stop_date:
            raise Exception("Simulation time exceeds trace time.")

        # Get the transactions given a source and time
        transaction_id = None
        for (t_src, t_id), transaction in self.transaction_times.iteritems():
            if transaction["start"] <= current_relative_time <= transaction["stop"] and t_src == source.id:
                transaction_id = t_id
                break

        # return matching row with nearest time
        return k7.match(self.trace, source.id, destination.id, channel, transaction_id)
