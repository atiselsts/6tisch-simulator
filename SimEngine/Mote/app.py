"""
An application lives on each node, except the root.
It sends (data) packets to the root
"""

# =========================== imports =========================================

import random
import copy

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('app')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class App(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()

        # local variables
        self.pkPeriod                       = self.settings.app_pkPeriod
        self.reassQueue                     = {}
        self.vrbTable                       = {}
        self.next_datagram_tag              = random.randint(0, 2**16-1)

    #======================== public ==========================================

    def schedule_mote_sendSinglePacketToDAGroot(self, firstPacket=False):
        """
        schedule an event to send a single packet
        """

        # disable app pkPeriod is zero
        if self.pkPeriod == 0:
            return

        # compute how long before transmission
        if firstPacket:
            # compute initial time within the range of [next asn, next asn+pkPeriod]
            delay            = self.settings.tsch_slotDuration + self.pkPeriod*random.random()
        else:
            # compute random delay
            delay            = self.pkPeriod*(1+random.uniform(-self.settings.app_pkPeriodVar, self.settings.app_pkPeriodVar))
        assert delay > 0

        # schedule
        self.engine.scheduleIn(
            delay            = delay,
            cb               = self._action_mote_sendSinglePacketToDAGroot,
            uniqueTag        = (self.mote.numCellsToNeighbors, '_action_mote_sendSinglePacketToDAGroot'),
            priority         = 2,
        )

    def schedule_mote_sendPacketBurstToDAGroot(self):
        """
        schedule an event to send a single burst of data (NOT periodic)
        """

        # schedule app_burstNumPackets packets at app_burstTimestamp
        for i in xrange(self.settings.app_burstNumPackets):
            self.engine.scheduleIn(
                delay        = self.settings.app_burstTimestamp,
                cb           = self._action_mote_enqueueDataForDAGroot,
                uniqueTag    = (self.mote.numCellsToNeighbors, '_app_action_enqueueData_burst_{0}'.format(i)),
                priority     = 2,
            )

    def action_mote_receiveE2EAck(self, srcIp, payload, timestamp):
        """
        mote receives end-to-end ACK from the DAGroot
        """

        assert not self.mote.dagRoot

    def fragment_and_enqueue_packet(self, packet):
        """
        fragment packet into fragments, and put in TSCH queue
        """

        # choose tag (same for all fragments)
        tag                       = self.next_datagram_tag
        self.next_datagram_tag    = (self.next_datagram_tag + 1) % 65536

        # create and put fragmets in TSCH queue
        for i in range(0, self.settings.frag_numFragments):

            # copy (fake) contents of the packets in fragment
            frag = copy.copy(packet)

            # change fields so looks like fragment
            frag['type']     = d.APP_TYPE_FRAG
            frag['payload']  = copy.deepcopy(packet['payload'])
            frag['payload']['datagram_size']    = self.settings.frag_numFragments
            frag['payload']['datagram_tag']     = tag
            frag['payload']['datagram_offset']  = i
            frag['sourceRoute'] = copy.deepcopy(packet['sourceRoute'])

            # put in TSCH queue
            if not self.mote.tsch.enqueue(frag):
                self.mote.radio.drop_packet(frag, SimEngine.SimLog.LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE['type'])
                # OPTIMIZATION: we could remove all fragments from queue if one is refused

    def frag_ff_forward_fragment(self, frag):
        """
        handle a fragment, and decide whether should be forwarded.

        return True if should be forwarded
        """

        assert self.settings.frag_ff_enable

        smac            = frag['smac']
        dstIp           = frag['dstIp']
        size            = frag['payload']['datagram_size']
        itag            = frag['payload']['datagram_tag']
        offset          = frag['payload']['datagram_offset']
        entry_lifetime  = 60 / self.settings.tsch_slotDuration

        # cleanup VRB table entries
        for mac in self.vrbTable.keys():
            # too old
            for tag in self.vrbTable[mac].keys():
                if (self.engine.getAsn() - self.vrbTable[mac][tag]['ts']) > entry_lifetime:
                    del self.vrbTable[mac][tag]
            # 0-length MAC address
            # FIXME: document
            if len(self.vrbTable[mac]) == 0:
                del self.vrbTable[mac]

        # handle first fragments
        if offset == 0:
            vrb_entry_num = 0
            for i in self.vrbTable:
                vrb_entry_num += len(self.vrbTable[i])

            if (not self.mote.dagRoot) and (vrb_entry_num == self.settings.frag_ff_vrbtablesize):
                # no room for a new entry
                self.mote.radio.drop_packet(frag, 'frag_vrb_table_full')
                return False

            if smac not in self.vrbTable:
                self.vrbTable[smac] = {}

            # In our design, vrbTable has (in-smac, in-tag, nexthop, out-tag).
            # However, it doesn't have nexthop mac address since
            # nexthop is determined at TSCH layer in this simulation.
            if itag in self.vrbTable[smac]:
                # duplicate first fragment
                frag['dstIp'] = None # this frame will be dropped by the caller
                return False
            else:
                self.vrbTable[smac][itag] = {}

            if dstIp == self.mote:
                # this is a special entry for fragments destined to the mote
                self.vrbTable[smac][itag]['otag'] = None
            else:
                self.vrbTable[smac][itag]['otag'] = self.next_datagram_tag
                self.next_datagram_tag = (self.next_datagram_tag + 1) % 65536
            self.vrbTable[smac][itag]['ts'] = self.engine.getAsn()

            if 'kill_entry_by_missing' in self.settings.frag_ff_options:
                self.vrbTable[smac][itag]['next_offset'] = 0

        # find entry in VRB table and forward fragment
        if (smac in self.vrbTable) and (itag in self.vrbTable[smac]):
            # VRB entry found!

            if self.vrbTable[smac][itag]['otag'] is None:
                # fragment for me

                # do no forward (but reassemble)
                return False

            if 'kill_entry_by_missing' in self.settings.frag_ff_options:
                if offset == self.vrbTable[smac][itag]['next_offset']:
                    self.vrbTable[smac][itag]['next_offset'] += 1
                else:
                    del self.vrbTable[smac][itag]
                    self.mote.radio.drop_packet(frag, 'frag_missing_frag')
                    return False

            frag['asn'] = self.engine.getAsn()
            frag['payload']['hops'] += 1 # update the number of hops
            frag['payload']['datagram_tag'] = self.vrbTable[smac][itag]['otag']
        else:
            # no VRB entry found!
            self.mote.radio.drop_packet(frag, 'frag_no_vrb_entry')
            return False

        # return True when the fragment is to be forwarded even if it cannot be
        # forwarded due to out-of-order or queue full
        if  (
                ('kill_entry_by_last' in self.settings.frag_ff_options) and
                (offset == (self.settings.frag_numFragments - 1))
            ):
            # this fragment is the last one
            del self.vrbTable[smac][itag]

        return True

    def frag_reassemble_packet(self, smac, payload):
        size                 = payload['datagram_size']
        tag                  = payload['datagram_tag']
        offset               = payload['datagram_offset']
        reass_queue_lifetime = 60 / self.settings.tsch_slotDuration

        # remove reassQueue elements
        if len(self.reassQueue) > 0:
            for s in list(self.reassQueue):
                for t in list(self.reassQueue[s]):
                    # to old
                    if (self.engine.getAsn() - self.reassQueue[s][t]['ts']) > reass_queue_lifetime:
                        del self.reassQueue[s][t]
                    # empty
                    if len(self.reassQueue[s]) == 0:
                        del self.reassQueue[s]

        # drop packet longer than reassembly queue elements
        if size > self.settings.frag_numFragments:
            # the size of reassQueue is the same number as self.settings.frag_numFragments.
            # larger packet than reassQueue should be dropped.
            self.mote.radio.drop_packet({'payload': payload}, 'frag_too_big_for_reass_queue')
            return False

        # create reassembly queue entry for new packet
        if (smac not in self.reassQueue) or (tag not in self.reassQueue[smac]):
            if not self.mote.dagRoot:
                reass_queue_num = 0
                for i in self.reassQueue:
                    reass_queue_num += len(self.reassQueue[i])
                if reass_queue_num == self.settings.frag_ph_numReassBuffs:
                    # no room for a new entry
                    self.mote.radio.drop_packet({'payload': payload}, 'frag_reass_queue_full')
                    return False
            else:
                pass

        if smac not in self.reassQueue:
            self.reassQueue[smac] = {}
        if tag not in self.reassQueue[smac]:
            self.reassQueue[smac][tag] = {'ts': self.engine.getAsn(), 'fragments': []}

        if offset not in self.reassQueue[smac][tag]['fragments']:
            self.reassQueue[smac][tag]['fragments'].append(offset)
        else:
            # it's a duplicate fragment or queue overflow
            return False

        if size == len(self.reassQueue[smac][tag]['fragments']):
            del self.reassQueue[smac][tag]
            if len(self.reassQueue[smac]) == 0:
                del self.reassQueue[smac]
            return True

        return False

    #======================== private ==========================================

    # app that periodically sends a single packet

    def _action_mote_sendSinglePacketToDAGroot(self):
        """
        send a single packet, and reschedule next one
        """

        # enqueue data
        self._action_mote_enqueueDataForDAGroot()

        # schedule sending next packet
        self.schedule_mote_sendSinglePacketToDAGroot()

    def _action_dagroot_receivePacketFromMote(self, srcIp, payload, timestamp):
        """
        dagroot received data packet
        """

        assert self.mote.dagRoot

        # update mote stats
        self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_REACHES_DAGROOT['type'])

        # log end-to-end latency
        self.mote._stats_logLatencyStat(timestamp - payload['asn_at_source']) # payload[0] is the ASN when sent

        # log the number of hops
        self.mote._stats_logHopsStat(payload['hops'])

        # send end-to-end ACK back to mote, if applicable
        if self.settings.app_e2eAck:

            destination = srcIp
            sourceRoute = self.mote.rpl.getSourceRoute([destination.id])

            if sourceRoute:

                # create e2e ACK
                newPacket = {
                    'asn':             self.engine.getAsn(),
                    'type':            d.APP_TYPE_ACK,
                    'code':            None,
                    'payload':         {},
                    'retriesLeft':     d.TSCH_MAXTXRETRIES,
                    'srcIp':           self,          # from DAGroot
                    'dstIp':           destination,   # to mote
                    'sourceRoute':     sourceRoute
                }

                # enqueue packet in TSCH queue
                if not self.mote.tsch.enqueue(newPacket):
                    self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_ACK_FAIL_ENQUEUE['type'])

    def _action_mote_enqueueDataForDAGroot(self):
        """
        enqueue data packet to the DAGroot
        """

        assert not self.mote.dagRoot

        # only send data if I have a preferred parent and dedicated cells to that parent
        if self.mote.rpl.getPreferredParent() and self.mote.numCellsToNeighbors.get(self.mote.rpl.getPreferredParent(), 0) > 0:

            # create new data packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.APP_TYPE_DATA,
                'code':           None,
                'payload':        { # payload overloaded is to calculate packet stats
                    'asn_at_source':   self.engine.getAsn(),    # ASN, used to calculate e2e latency
                    'hops':            1,                       # number of hops, used to calculate empirical hop count
                },
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self,               # from mote
                'dstIp':          self.mote.dagRootAddress,# to DAGroot
                'sourceRoute':    [],
            }

            # update mote stats
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_GENERATED['type'])

            # enqueue packet (or fragments) into TSCH queue
            if self.settings.frag_numFragments > 1:
                # multiple frames (fragmentation)

                self.fragment_and_enqueue_packet(newPacket)
            else:
                # single frame

                isEnqueued = self.mote.tsch.enqueue(newPacket)
                if not isEnqueued:
                    # update mote stats
                    self.mote.radio.drop_packet(newPacket,
                                                 SimEngine.SimLog.LOG_TSCH_DROP_DATA_FAIL_ENQUEUE['type'])
