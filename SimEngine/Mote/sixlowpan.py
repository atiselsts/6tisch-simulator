"""
6LoWPAN layer including reassembly/fragmentation
"""

# =========================== imports =========================================

from abc import abstractmethod
import copy
import random

# Simulator-wide modules
import SimEngine
import MoteDefines as d

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


class Sixlowpan(object):

    def __init__(self, mote):
        self.mote                 = mote
        self.settings             = SimEngine.SimSettings.SimSettings()
        self.engine               = SimEngine.SimEngine.SimEngine()
        self.fragmentation        = globals()[self.settings.fragmentation](self)
        self.tsch_max_payload_len = self.settings.tsch_max_payload_len
        self.next_datagram_tag    = random.randint(0, 2**16-1)
        self.reassembly_buffer    = {}

    def input(self, smac, packet):
        if packet['type'] == d.APP_TYPE_FRAG:
            self.fragmentation.input(smac, packet)
        elif packet['dstIp'] == self.mote:
            # TODO: support multiple apps
            assert self.mote.dagRoot
            self.mote.app._action_dagroot_receivePacketFromMote(srcIp=packet['srcIp'],
                                                                payload=packet['payload'],
                                                                timestamp=self.engine.getAsn())
        else:
            # update field
            packet['asn']         = self.engine.getAsn()
            packet['retriesLeft'] = d.TSCH_MAXTXRETRIES,
            if packet['type'] == d.APP_TYPE_DATA:
                # update the number of hops
                # TODO: this shouldn't be done in application payload.
                packet['payload']['hops'] += 1
            self.forward(packet)

    def forward(self, packet):
        if packet['payload']['length'] > self.tsch_max_payload_len:
            # packet doesn't fit into a single frame; needs fragmentation
            self.fragment(packet)
        elif not self.mote.tsch.enqueue(packet):
            self.mote.radio.drop_packet(packet,
                                         SimEngine.SimLog.LOG_TSCH_DROP_RELAY_FAIL_ENQUEUE['type'])
        else:
            # update mote stats
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RELAYED['type'])

    def output(self, packet):
        if packet['payload']['length'] > self.tsch_max_payload_len:
            # packet doesn't fit into a single frame; needs fragmentation
            self.fragment(packet)
        elif not self.mote.tsch.enqueue(packet):
            self.mote.radio.drop_packet(packet,
                                         SimEngine.SimLog.LOG_TSCH_DROP_DATA_FAIL_ENQUEUE['type'])

    def reassemble(self, smac, fragment):
        datagram_size         = fragment['payload']['datagram_size']
        datagram_offset       = fragment['payload']['datagram_offset']
        incoming_datagram_tag = fragment['payload']['datagram_tag']
        reass_queue_lifetime  = 60 / self.settings.tsch_slotDuration

        self._remove_expired_reassembly_queue()

        # drop packet longer than reassembly queue elements
        if datagram_size > self.settings.sixlowpan_reassembly_queue_len:
            self.mote.radio.drop_packet(fragment, 'frag_too_big_for_reass_queue')
            return None

        # make sure we can allocate a reassembly queue if necessary
        if (smac not in self.reassembly_buffer) or (incoming_datagram_tag not in self.reassembly_buffer[smac]):
            # dagRoot has no memory limitation for reassembly buffer
            if not self.mote.dagRoot:
                reass_queue_num = 0
                for i in self.reassembly_buffer:
                    reass_queue_num += len(self.reassembly_buffer[i])
                if reass_queue_num == self.settings.sixlowpan_reassembly_queue_num:
                    # no room for a new entry
                    self.mote.radio.drop_packet(fragment, 'frag_reass_queue_full')
                    return None

            # create a new reassembly queue
            if smac not in self.reassembly_buffer:
                self.reassembly_buffer[smac] = {}
            if incoming_datagram_tag not in self.reassembly_buffer[smac]:
                self.reassembly_buffer[smac][incoming_datagram_tag] = {'expiration': self.engine.getAsn() + reass_queue_lifetime,
                                                                       'fragments': []}

        if datagram_offset not in map(lambda x: x['datagram_offset'], self.reassembly_buffer[smac][incoming_datagram_tag]['fragments']):
            self.reassembly_buffer[smac][incoming_datagram_tag]['fragments'].append({'datagram_offset': datagram_offset,
                                                                                     'fragment_length': fragment['payload']['length']})
        else:
            # it's a duplicate fragment or queue overflow
            return None

        # check if we have a full packet in the reassembly queue
        length_list = map(lambda x: x['fragment_length'], self.reassembly_buffer[smac][incoming_datagram_tag]['fragments'])
        total_fragment_length = reduce(lambda x, y: x + y, length_list)
        if datagram_size > total_fragment_length:
            # reassembly is not completed
            return None
        elif datagram_size < total_fragment_length:
            # TODO fragment overwrapping is not implemented
            raise NotImplementedError

        del self.reassembly_buffer[smac][incoming_datagram_tag]
        if len(self.reassembly_buffer[smac]) == 0:
            del self.reassembly_buffer[smac]

        # construct an original packet
        packet = copy.copy(fragment)
        packet['type'] = fragment['payload']['original_type']
        packet['payload'] = copy.deepcopy(fragment['payload'])
        packet['payload']['length'] = datagram_size
        del packet['payload']['datagram_tag']
        del packet['payload']['datagram_size']
        del packet['payload']['datagram_offset']
        del packet['payload']['original_type']

        return packet

    def fragment(self, packet):
        """
        fragment packet into fragments, and put in TSCH queue
        """
        # choose tag (same for all fragments)
        outgoing_datagram_tag = self.get_next_datagram_tag()

        # create and put fragmets in TSCH queue
        number_of_fragments = packet['payload']['length'] / self.tsch_max_payload_len
        if packet['payload']['length'] % self.tsch_max_payload_len > 0:
            number_of_fragments += 1
        for i in range(0, number_of_fragments):

            # copy (fake) contents of the packets in fragment
            fragment = copy.copy(packet)
            # change fields so looks like fragment
            fragment['type']                     = d.APP_TYPE_FRAG
            fragment['payload']                  = copy.deepcopy(packet['payload'])
            fragment['payload']['original_type']            = packet['type']
            fragment['payload']['datagram_size'] = packet['payload']['length']
            fragment['payload']['datagram_tag']  = outgoing_datagram_tag
            fragment['payload']['datagram_offset']  = i * self.tsch_max_payload_len
            if (i * self.tsch_max_payload_len) < packet['payload']['length']:
                fragment['payload']['length'] = self.tsch_max_payload_len
            else:
                fragment['payload']['length'] = packet['payload']['length'] % self.tsch_max_payload_len
            fragment['sourceRoute'] = copy.deepcopy(packet['sourceRoute'])

            # put in TSCH queue
            if not self.mote.tsch.enqueue(fragment):
                self.mote.radio.drop_packet(fragment, SimEngine.SimLog.LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE['type'])
                # OPTIMIZATION: we could remove all fragments from queue if one is refused

    def get_next_datagram_tag(self):
        ret = self.next_datagram_tag
        self.next_datagram_tag = (ret + 1) % 65536
        return ret

    def _remove_expired_reassembly_queue(self):
        if len(self.reassembly_buffer) == 0:
            return

        for smac in list(self.reassembly_buffer):
            for incoming_datagram_tag in list(self.reassembly_buffer[smac]):
                # to old
                if self.engine.getAsn() > self.reassembly_buffer[smac][incoming_datagram_tag]['expiration']:
                    del self.reassembly_buffer[smac][incoming_datagram_tag]

            # empty
            if len(self.reassembly_buffer[smac]) == 0:
                del self.reassembly_buffer[smac]


class Fragmentation(object):

    def __init__(self, sixlowpan):
        self.sixlowpan = sixlowpan
        self.mote      = sixlowpan.mote
        self.settings  = sixlowpan.settings
        self.engine    = sixlowpan.engine

    @abstractmethod
    def input(self, fragment):
        raise NotImplementedError


class PerHopReassembly(Fragmentation):

    def input(self, smac, fragment):
        packet = self.sixlowpan.reassemble(smac, fragment)
        if packet:
            self.sixlowpan.input(smac, packet)


class FragmentForwarding(Fragmentation):

    def __init__(self, sixlowpan):
        super(FragmentForwarding, self).__init__(sixlowpan)
        self.vrb_table   = {}

    def input(self, smac, fragment):

        dstIp                 = fragment['dstIp']
        datagram_size         = fragment['payload']['datagram_size']
        datagram_offset       = fragment['payload']['datagram_offset']
        incoming_datagram_tag = fragment['payload']['datagram_tag']
        entry_lifetime        = 60 / self.settings.tsch_slotDuration

        self._remove_expired_vrb_table_entry()

        # handle first fragments
        if datagram_offset == 0:
            # check if we have enough memory for a new entry if necessary
            if self.mote.dagRoot:
                # dagRoot has no memory limitation for VRB Table
                pass
            else:
                vrb_entry_num = 0
                for i in self.vrb_table:
                    vrb_entry_num += len(self.vrb_table[i])
                    if vrb_entry_num == self.settings.fragmentation_ff_vrb_table_size:
                        # no room for a new entry
                        self.mote.radio.drop_packet(fragment, 'frag_vrb_table_full')
                        return

            if smac not in self.vrb_table:
                self.vrb_table[smac] = {}

            # By specification, a VRB Table entry is supposed to have:
            # - incoming smac
            # - incoming datagram_tag
            # - outgoing dmac (nexthop)
            # - outgoing datagram_tag
            # However, a VRB Table entry in this implementation doesn't have
            # nexthop mac address since nexthop is determined at TSCH layer in
            # this simulation.
            if incoming_datagram_tag in self.vrb_table[smac]:
                # duplicate first fragment is silently discarded
                return
            else:
                self.vrb_table[smac][incoming_datagram_tag] = {}

            if dstIp == self.mote:
                # this is a special entry for fragments destined to the mote
                self.vrb_table[smac][incoming_datagram_tag]['outgoing_datagram_tag'] = None
            else:
                self.vrb_table[smac][incoming_datagram_tag]['outgoing_datagram_tag'] = self.sixlowpan.get_next_datagram_tag()
            self.vrb_table[smac][incoming_datagram_tag]['expiration'] = self.engine.getAsn() + entry_lifetime

            if 'kill_entry_by_missing' in self.settings.fragmentation_ff_options:
                self.vrb_table[smac][incoming_datagram_tag]['next_offset'] = 0

        # find entry in VRB table and forward fragment
        if (smac in self.vrb_table) and (incoming_datagram_tag in self.vrb_table[smac]):
            # VRB entry found!

            if self.vrb_table[smac][incoming_datagram_tag]['outgoing_datagram_tag'] is None:
                # fragment for me
                # do no forward (but reassemble)
                packet = self.sixlowpan.reassemble(smac, fragment)
                if packet:
                    self.sixlowpan.input(smac, packet)
                return

            if 'kill_entry_by_missing' in self.settings.fragmentation_ff_options:
                if datagram_offset == self.vrb_table[smac][incoming_datagram_tag]['next_offset']:
                    self.vrb_table[smac][incoming_datagram_tag]['next_offset'] += fragment['payload']['length']
                else:
                    del self.vrb_table[smac][incoming_datagram_tag]
                    if len(self.vrb_table[smac]) == 0:
                        del self.vrb_table[smac]
                    self.mote.radio.drop_packet(fragment, 'frag_missing_frag')
                    return

            fragment['asn'] = self.engine.getAsn()
            # update the number of hops
            # TODO: this shouldn't be done in application payload.
            if fragment['payload']['original_type'] == d.APP_TYPE_DATA:
                fragment['payload']['hops'] += 1 # update the number of hops
            fragment['payload']['datagram_tag'] = self.vrb_table[smac][incoming_datagram_tag]['outgoing_datagram_tag']
            isEnqueued = self.mote.tsch.enqueue(fragment)
            if isEnqueued:
                # update mote stats
                self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RELAYED['type'])
            else:
                self.mote.radio.drop_packet(fragment,
                                             SimEngine.SimLog.LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE['type'])

            if (('kill_entry_by_last' in self.settings.fragmentation_ff_options) and
               ((fragment['payload']['datagram_offset'] + fragment['payload']['length']) == fragment['payload']['datagram_size'])):
                # this fragment is the last one
                del self.vrb_table[smac][incoming_datagram_tag]
                if len(self.vrb_table[smac]) == 0:
                    del self.vrb_table[smac]
        else:
            # no VRB entry found!
            self.mote.radio.drop_packet(fragment, 'frag_no_vrb_entry')
            return

    def _remove_expired_vrb_table_entry(self):
        if len(self.vrb_table) == 0:
            return

        for smac in self.vrb_table.keys():
            for incoming_datagram_tag in self.vrb_table[smac].keys():
                # too old
                if self.engine.getAsn() > self.vrb_table[smac][incoming_datagram_tag]['expiration']:
                    del self.vrb_table[smac][incoming_datagram_tag]
            # empty
            if len(self.vrb_table[smac]) == 0:
                del self.vrb_table[smac]
