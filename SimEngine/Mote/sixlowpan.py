"""
6LoWPAN layer including reassembly/fragmentation
"""

# =========================== imports =========================================

from abc import abstractmethod
import copy
import math
import random

# Simulator-wide modules
import SimEngine
import MoteDefines as d

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Sixlowpan(object):

    def __init__(self, mote):
        self.mote                 = mote
        self.settings             = SimEngine.SimSettings.SimSettings()
        self.engine               = SimEngine.SimEngine.SimEngine()
        self.log                  = SimEngine.SimLog.SimLog().log
        self.fragmentation        = globals()[self.settings.fragmentation](self)
        self.next_datagram_tag    = random.randint(0, 2**16-1)
        # "reassembly_buffers" has mote instances as keys. Each value is a list.
        # A list is indexed by incoming datagram_tags.
        #
        # An element of the list a dictionary consisting of three key-values:
        # "net", "expiration" and "fragments".
        #
        # - "net" has srcIp and dstIp of the packet
        # - "fragments" holds received fragments, although only their
        # datagram_offset and lengths are stored in the "fragments" list.
        self.reassembly_buffers    = {}

    #======================== public ==========================================

    def send(self, packet):
        assert sorted(packet.keys()) == sorted(['type','net','app'])

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXLOWPAN_PKT_TX,
            {
                '_mote_id':       self.mote.id,
                'packet':         packet,
            }
        )

        if self._prepare_mac_header(packet):
            for pkt in self.fragment(packet):
                # fragment() returns a list of sending fragments. It could return a
                # list having one packet when the packet doesn't need fragmentation
                self.mote.tsch.enqueue(pkt)
        else:
            # we cannot find a next-hop; drop this packet
            self.mote.radio.drop_packet(
                pkt     = packet,
                reason  = SimEngine.SimLog.LOG_RPL_DROP_NO_ROUTE['type']
            )

    def fragment(self, packet):
        """Fragment the input packet into fragments

        This method returns fragments in a list. If the input packet doesn't
        need fragmentation, this methods returns the packet in a list.

        Formats of fragment packets are shown below:

            The format of the first fragment (no app field):
            {
                'net': {
                    'srcIp':                src_ip_address,
                    'dstIp':                dst_ip_address,
                    'packet_length':        packet_length,
                    'datagram_size':        original_packet_length,
                    'datagram_tag':         tag_for_the_packet,
                    'datagram_offset':      offset_for_this_fragment,
                    'sourceRoute':          (if applicable)
                }
            }

            The format of the last fragment (no srcIp/dstIp):
            {
                'net': {
                    'packet_length':        packet_length,
                    'datagram_size':        original_packet_length,
                    'datagram_tag':         tag_for_the_packet,
                    'datagram_offset':      offset_for_this_fragment,
                    'original_packet_type': original_packet_type,
                }
                'app':                      (if applicable)
            }

            The format of other fragments (neither app nor srcIp/dstIp):
            {
                'net': {
                    'packet_length':        packet_length,
                    'datagram_size':        original_packet_length,
                    'datagram_tag':         tag_for_the_packet,
                    'datagram_offset':      offset_for_this_fragment,
                }
            }
        """

        # 'type' and 'net' are mandatory fields of a packet here. in this
        # sense, a set of packet.keys() should have 'type' and 'net' in it.
        assert set(['type','net']).issubset(set(packet.keys()))

        returnVal = []

        if (
                (packet['type'] != d.NET_TYPE_FRAG)
                and
                ('packet_length' in packet['net'])
                and
                (self.settings.tsch_max_payload_len < packet['net']['packet_length'])
           ):
            # the packet needs fragmentation

            # choose tag (same for all fragments)
            outgoing_datagram_tag = self._get_next_datagram_tag()
            number_of_fragments   = int(math.ceil(float(packet['net']['packet_length']) / self.settings.tsch_max_payload_len))
            datagram_offset       = 0

            for i in range(0, number_of_fragments):

                # common part of fragment packet
                fragment = {
                    'type':                d.NET_TYPE_FRAG,
                    'net': {
                        'datagram_size':   packet['net']['packet_length'],
                        'datagram_tag':    outgoing_datagram_tag,
                        'datagram_offset': datagram_offset
                    }
                }

                # put additional fields to the first and the last fragment
                if   i == 0:
                    # the first fragment of a packet has srcIp, dstIp
                    fragment['net']['srcIp']                = packet['net']['srcIp']
                    fragment['net']['dstIp']                = packet['net']['dstIp']
                    if 'sourceRoute' in packet['net']:
                        fragment['net']['sourceRoute']      = copy.deepcopy(packet['net']['sourceRoute'])
                elif i == (number_of_fragments - 1):
                    # the last fragment of a packet has original_packet_type
                    # and 'app' field
                    fragment['app']                         = copy.deepcopy(packet['app'])
                    fragment['net']['original_packet_type'] = packet['type']

                # set the length of the fragment as packet_length
                if (
                        (i == 0) and
                        ((packet['net']['packet_length'] % self.settings.tsch_max_payload_len) > 0)
                   ):
                    # Make the first fragment have some room to handle size changes
                    # of the compressed header, although header compaction and
                    # inflation have been not implemented yet.
                    fragment['net']['packet_length'] = packet['net']['packet_length'] % self.settings.tsch_max_payload_len
                else:
                    fragment['net']['packet_length'] = self.settings.tsch_max_payload_len

                # update datagram_offset which will be used for the next fragment
                datagram_offset += fragment['net']['packet_length']

                # copy the MAC header
                fragment['mac'] = copy.deepcopy(packet['mac'])

                # add the fragment to a returning list
                returnVal.append(fragment)

                # log
                self.log(
                    SimEngine.SimLog.LOG_SIXLOWPAN_FRAG_GEN,
                    {
                        '_mote_id': self.mote.id,
                        'packet':   fragment
                    }
                )

        else:
            # the input packet doesn't need fragmentation
            returnVal = [packet]

        return returnVal

    def forward(self, packet):
        # input packet is either:
        # - a complete IPv6 packet which can be forwarded without fragmentation
        # - a complete IPv6 packet which needs fragmentation
        # - a fragment packet forwarded by fragment-forwarding

        # mandatory fields are type and net
        assert set(['type', 'net']).issubset(set(packet.keys()))

        # keep only headers that are needed
        fwdPacket = {
            'type':            copy.deepcopy(packet['type']),
            'net':             copy.deepcopy(packet['net']),
        }
        if 'app' in packet:
            fwdPacket['app'] = copy.deepcopy(packet['app'])


        if fwdPacket['type'] == d.NET_TYPE_FRAG:
            # this is a fragment-forwarding packet which should have the valid
            # MAC header
            fwdPacket['mac'] = copy.deepcopy(packet['mac'])
            ready_to_forward = True
        else:
            # prepare MAC header for the forwarding packet
            ready_to_forward = self._prepare_mac_header(fwdPacket)

        if ready_to_forward:
            # log
            self.log(
                SimEngine.SimLog.LOG_SIXLOWPAN_PKT_FWD,
                {
                    '_mote_id':       self.mote.id,
                    'packet':         fwdPacket,
                }
            )

            # fragment if needed; and forward the packet or the fragments
            for pkt in self.fragment(fwdPacket):
                if self._prepare_mac_header(pkt):
                    self.mote.tsch.enqueue(pkt)

    def reassemble(self, fragment):
        srcMac                = fragment['mac']['srcMac']
        datagram_size         = fragment['net']['datagram_size']
        datagram_offset       = fragment['net']['datagram_offset']
        incoming_datagram_tag = fragment['net']['datagram_tag']
        buffer_lifetime  = d.SIXLOWPAN_REASSEMBLY_BUFFER_LIFETIME / self.settings.tsch_slotDuration

        self._remove_expired_reassembly_buffer()

        # make sure we can allocate a reassembly buffer if necessary
        if (srcMac not in self.reassembly_buffers) or (incoming_datagram_tag not in self.reassembly_buffers[srcMac]):
            # dagRoot has no memory limitation for reassembly buffer
            if not self.mote.dagRoot:
                total_reassembly_buffers_num = 0
                for i in self.reassembly_buffers:
                    total_reassembly_buffers_num += len(self.reassembly_buffers[i])
                if total_reassembly_buffers_num == self.settings.sixlowpan_reassembly_buffers_num:
                    # no room for a new entry
                    self.mote.radio.drop_packet(fragment, 'frag_reassembly_buffer_full')
                    return

            # create a new reassembly buffer
            if srcMac not in self.reassembly_buffers:
                self.reassembly_buffers[srcMac] = {}
            if incoming_datagram_tag not in self.reassembly_buffers[srcMac]:
                self.reassembly_buffers[srcMac][incoming_datagram_tag] = {
                    'expiration': self.engine.getAsn() + buffer_lifetime,
                    'fragments': []
                }

        if datagram_offset not in map(lambda x: x['datagram_offset'], self.reassembly_buffers[srcMac][incoming_datagram_tag]['fragments']):

            if fragment['net']['datagram_offset'] == 0:
                # store srcIp and dstIp which only the first fragment has
                self.reassembly_buffers[srcMac][incoming_datagram_tag]['net'] = {
                    'srcIp':  fragment['net']['srcIp'],
                    'dstIp':  fragment['net']['dstIp']
                }

            self.reassembly_buffers[srcMac][incoming_datagram_tag]['fragments'].append({
                'datagram_offset': datagram_offset,
                'fragment_length': fragment['net']['packet_length']
            })
        else:
            # it's a duplicate fragment
            return

        # check whether we have a full packet in the reassembly buffer
        total_fragment_length = sum([f['fragment_length'] for f in self.reassembly_buffers[srcMac][incoming_datagram_tag]['fragments']])
        assert total_fragment_length <= datagram_size
        if total_fragment_length < datagram_size:
            # reassembly is not completed
            return

        # construct an original packet
        packet = copy.copy(fragment)
        packet['type'] = fragment['net']['original_packet_type']
        packet['net'] = copy.deepcopy(fragment['net'])
        packet['net']['srcIp'] = self.reassembly_buffers[srcMac][incoming_datagram_tag]['net']['srcIp']
        packet['net']['dstIp'] = self.reassembly_buffers[srcMac][incoming_datagram_tag]['net']['dstIp']
        packet['net']['packet_length'] = datagram_size
        del packet['net']['datagram_tag']
        del packet['net']['datagram_size']
        del packet['net']['datagram_offset']
        del packet['net']['original_packet_type']

        # reassembly is done; we don't need the reassembly buffer for the
        # packet any more. remove the buffer.
        del self.reassembly_buffers[srcMac][incoming_datagram_tag]
        if len(self.reassembly_buffers[srcMac]) == 0:
            del self.reassembly_buffers[srcMac]

        return packet

    def recv(self, packet):

        self.log(
            SimEngine.SimLog.LOG_SIXLOWPAN_PKT_RX,
            {
                '_mote_id':        self.mote.id,
                'packet':          packet,
            }
        )

        if packet['type'] == d.NET_TYPE_FRAG:
            # self.fragmentaiton.recv() returns a packet to be processed
            # here. `packet` could be None when no packet should be processed
            # further.
            packet = self.fragmentation.recv(packet)

        # process switch:
        # - packet is None       : do nothing
        # - packet is for us     : hand to app
        # - packet is for others : forward
        if not packet:
            # packet is None; do nothing
            pass

        elif (
                (packet['type'] != d.NET_TYPE_FRAG)
                and
                (
                    (packet['net']['dstIp'] == self.mote.id)
                    or
                    (packet['net']['dstIp'] == d.BROADCAST_ADDRESS)
                )
             ):
            # packet for us

            if   packet['type'] == d.APP_TYPE_JOIN:
                self.mote.secjoin.receiveJoinPacket(packet)
            elif packet['type'] == d.RPL_TYPE_DAO:
                self.mote.rpl.action_receiveDAO(packet)
            elif packet['type'] == d.RPL_TYPE_DIO:
                self.mote.rpl.action_receiveDIO(packet)
            elif packet['type'] == d.APP_TYPE_DATA:
                self.mote.app._action_receivePacket(packet)
            elif packet['type'] == d.APP_TYPE_ACK:
                self.mote.app.action_mote_receiveE2EAck(packet)

        else:
            # packet for others; forward it

            # application data packet specific process
            if (
                    ('app' in packet)
                    and
                    ('appcounter' in packet['app'])
               ):
                # update the number of hops
                # FIXME: this shouldn't be done in application payload.
                packet['app']['appcounter'] += 1 # update the number of hops

            self.forward(packet)


    #======================== private ==========================================

    def _prepare_mac_header(self, packet):
        returnVal = False

        if 'mac' not in packet:
            # need to prepare its MAC header
            assert 'srcIp' in packet['net']
            assert 'dstIp' in packet['net']
            # find link-layer destination
            dstMac = self.mote.rpl.findNextHopId(packet['net']['dstIp'])
            if dstMac == None:
                returnVal = False
            else:
                packet['mac'] = {
                    'srcMac': self.mote.id,
                    'dstMac': dstMac
                }
                returnVal = True
        else:
            assert 'srcMac' in packet['mac']
            returnVal = True

        return returnVal

    def _get_next_datagram_tag(self):
        ret = self.next_datagram_tag
        self.next_datagram_tag = (ret + 1) % 65536
        return ret

    def _remove_expired_reassembly_buffer(self):
        if len(self.reassembly_buffers) == 0:
            return

        for srcMac in self.reassembly_buffers.keys():
            for incoming_datagram_tag in self.reassembly_buffers[srcMac].keys():
                # remove a reassembly buffer which expires
                if self.reassembly_buffers[srcMac][incoming_datagram_tag]['expiration'] < self.engine.getAsn():
                    del self.reassembly_buffers[srcMac][incoming_datagram_tag]

            # remove an reassembly buffer entry if it's empty
            if len(self.reassembly_buffers[srcMac]) == 0:
                del self.reassembly_buffers[srcMac]


class Fragmentation(object):
    """The base class for forwarding implementations of fragments
    """

    def __init__(self, sixlowpan):
        self.sixlowpan = sixlowpan
        self.mote      = sixlowpan.mote
        self.settings  = SimEngine.SimSettings.SimSettings()
        self.engine    = SimEngine.SimEngine.SimEngine()
        self.log       = SimEngine.SimLog.SimLog().log

    #======================== public ==========================================

    @abstractmethod
    def recv(self, fragment):
        """This method is supposed to return a packet to be processed further

        This could return None.
        """
        raise NotImplementedError()


class PerHopReassembly(Fragmentation):
    """The typical 6LoWPAN reassembly and fragmentation implementation.

    Each intermediate node between the source node and the destination
    node of the fragments of a packet reasembles the original packet and
    fragment it again before forwarding the fragments to its next-hop.
    """
    #======================== public ==========================================

    def recv(self, fragment):
        """Reassemble an original packet
        """
        return self.sixlowpan.reassemble(fragment)


class FragmentForwarding(Fragmentation):
    """Fragment Forwarding implementation.

    A fragment is forwarded without reassembling the original packet
    using VRB Table. For further information, see this I-d:
    https://tools.ietf.org/html/draft-watteyne-6lo-minimal-fragment
    """

    def __init__(self, sixlowpan):
        super(FragmentForwarding, self).__init__(sixlowpan)
        self.vrb_table   = {}

    #======================== public ==========================================

    def recv(self, fragment):

        srcMac                = fragment['mac']['srcMac']
        datagram_size         = fragment['net']['datagram_size']
        datagram_offset       = fragment['net']['datagram_offset']
        incoming_datagram_tag = fragment['net']['datagram_tag']
        entry_lifetime        = d.SIXLOWPAN_VRB_TABLE_ENTRY_LIFETIME / self.settings.tsch_slotDuration

        self._remove_expired_vrb_table_entry()

        # handle first fragments
        if datagram_offset == 0:

            if fragment['net']['dstIp'] != self.mote.id:
                dstMac = self.mote.rpl.findNextHopId(fragment['net']['dstIp'])
                if dstMac == None:
                    # no route to the destination
                    return

            # check if we have enough memory for a new entry if necessary
            if self.mote.dagRoot:
                # dagRoot has no memory limitation for VRB Table
                pass
            else:
                total_vrb_table_entry_num = sum([len(e) for _, e in self.vrb_table.items()])
                assert total_vrb_table_entry_num <= self.settings.fragmentation_ff_vrb_table_size
                if total_vrb_table_entry_num == self.settings.fragmentation_ff_vrb_table_size:
                    # no room for a new entry
                    self.mote.radio.drop_packet(fragment, 'frag_vrb_table_full')
                    return


            if srcMac not in self.vrb_table:
                self.vrb_table[srcMac] = {}

            # By specification, a VRB Table entry is supposed to have:
            # - incoming srcMac
            # - incoming datagram_tag
            # - outgoing dstMac (nexthop)
            # - outgoing datagram_tag

            if incoming_datagram_tag in self.vrb_table[srcMac]:
                # duplicate first fragment is silently discarded
                return
            else:
                self.vrb_table[srcMac][incoming_datagram_tag] = {}

            if fragment['net']['dstIp']  == self.mote.id:
                # this is a special entry for fragments destined to the mote
                self.vrb_table[srcMac][incoming_datagram_tag]['outgoing_datagram_tag'] = None
            else:
                self.vrb_table[srcMac][incoming_datagram_tag]['dstMac']                = dstMac
                self.vrb_table[srcMac][incoming_datagram_tag]['outgoing_datagram_tag'] = self.sixlowpan._get_next_datagram_tag()

            self.vrb_table[srcMac][incoming_datagram_tag]['expiration'] = self.engine.getAsn() + entry_lifetime

            if 'missing_fragment' in self.settings.fragmentation_ff_discard_vrb_entry_policy:
                self.vrb_table[srcMac][incoming_datagram_tag]['next_offset'] = 0

        # when missing_fragment is in discard_vrb_entry_policy
        # - if the incoming fragment is the expected one, update the next_offset
        # - otherwise, remove the corresponding VRB table entry
        if (
                ('missing_fragment' in self.settings.fragmentation_ff_discard_vrb_entry_policy) and
                (srcMac in self.vrb_table) and
                (incoming_datagram_tag in self.vrb_table[srcMac])
           ):
            if datagram_offset == self.vrb_table[srcMac][incoming_datagram_tag]['next_offset']:
                self.vrb_table[srcMac][incoming_datagram_tag]['next_offset'] += fragment['net']['packet_length']
            else:
                del self.vrb_table[srcMac][incoming_datagram_tag]
                if len(self.vrb_table[srcMac]) == 0:
                    del self.vrb_table[srcMac]

        # find entry in VRB table and forward fragment
        if (srcMac in self.vrb_table) and (incoming_datagram_tag in self.vrb_table[srcMac]):
            # VRB entry found!

            if self.vrb_table[srcMac][incoming_datagram_tag]['outgoing_datagram_tag'] is None:
                # fragment for me: do not forward but reassemble. ret will have
                # either a original packet or None
                ret = self.sixlowpan.reassemble(fragment)

            else:
                # need to create a new packet in order to distinguish between the
                # received packet and a forwarding packet.
                fwdFragment = {
                    'type':       copy.deepcopy(fragment['type']),
                    'net':        copy.deepcopy(fragment['net']),
                    'mac': {
                        'srcMac': self.mote.id,
                        'dstMac': self.vrb_table[srcMac][incoming_datagram_tag]['dstMac']
                    }
                }

                # forwarding fragment should have the outgoing datagram_tag
                fwdFragment['net']['datagram_tag'] = self.vrb_table[srcMac][incoming_datagram_tag]['outgoing_datagram_tag']

                # copy app field if necessary
                if 'app' in fragment:
                    fwdFragment['app'] = copy.deepcopy(fragment['app'])

                ret = fwdFragment

        else:
            # no VRB table entry is found
            ret = None

        # when last_fragment is in discard_vrb_entry_policy
        # - if the incoming fragment is the last fragment of a packet, remove the corresponding entry
        # - otherwise, do nothing
        if (
                ('last_fragment' in self.settings.fragmentation_ff_discard_vrb_entry_policy) and
                (srcMac in self.vrb_table) and
                (incoming_datagram_tag in self.vrb_table[srcMac]) and
                ((fragment['net']['datagram_offset'] + fragment['net']['packet_length']) == fragment['net']['datagram_size'])
           ):
            del self.vrb_table[srcMac][incoming_datagram_tag]
            if len(self.vrb_table[srcMac]) == 0:
                del self.vrb_table[srcMac]

        return ret

    #======================== private ==========================================

    def _remove_expired_vrb_table_entry(self):
        if len(self.vrb_table) == 0:
            return

        for srcMac in self.vrb_table.keys():
            for incoming_datagram_tag in self.vrb_table[srcMac].keys():
                # too old
                if self.vrb_table[srcMac][incoming_datagram_tag]['expiration'] < self.engine.getAsn():
                    del self.vrb_table[srcMac][incoming_datagram_tag]
            # empty
            if len(self.vrb_table[srcMac]) == 0:
                del self.vrb_table[srcMac]
