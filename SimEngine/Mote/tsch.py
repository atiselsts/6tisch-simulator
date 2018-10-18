
"""
"""

# =========================== imports =========================================

import copy
from itertools import chain
import random

import netaddr

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class Tsch(object):

    def __init__(self, mote):

        # store params
        self.mote = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine   = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()
        self.log      = SimEngine.SimLog.SimLog().log

        # local variables
        self.slotframes      = {}
        self.txQueue         = []
        self.neighbor_table  = []
        self.pktToSend       = None
        self.waitingFor      = None
        self.channel         = None
        self.active_cell     = None
        self.asnLastSync     = None
        self.isSync          = False
        self.join_proxy      = None
        self.iAmSendingEBs   = False
        self.clock           = Clock(self.mote)
        # backoff state
        self.backoff_exponent        = d.TSCH_MIN_BACKOFF_EXPONENT
        self.backoff_remaining_delay = 0

        # install the default slotframe
        self.add_slotframe(
            slotframe_handle = 0,
            length           = self.settings.tsch_slotframeLength
        )

    #======================== public ==========================================

    # getters/setters

    def getIsSync(self):
        return self.isSync

    def setIsSync(self,val):
        # set
        self.isSync = val

        if self.isSync:
            # log
            self.log(
                SimEngine.SimLog.LOG_TSCH_SYNCED,
                {
                    "_mote_id":   self.mote.id,
                }
            )

            self.asnLastSync = self.engine.getAsn()
            self._start_keep_alive_timer()

            # start SF
            self.mote.sf.start()

            # transition: listeningForEB->active
            self.engine.removeFutureEvent(      # remove previously scheduled listeningForEB cells
                uniqueTag=(self.mote.id, '_action_listeningForEB_cell')
            )
        else:
            # log
            self.log(
                SimEngine.SimLog.LOG_TSCH_DESYNCED,
                {
                    "_mote_id":   self.mote.id,
                }
            )

            self.stopSendingEBs()
            self.delete_minimal_cell()
            self.mote.sf.stop()
            self.join_proxy = None
            self.asnLastSync = None
            self.clock.desync()
            self._stop_keep_alive_timer()

            # transition: active->listeningForEB
            self.engine.removeFutureEvent(      # remove previously scheduled listeningForEB cells
                uniqueTag=(self.mote.id, '_action_active_cell')
            )
            self.schedule_next_listeningForEB_cell()

    def get_busy_slots(self, slotframe_handle=0):
        return self.slotframes[slotframe_handle].get_busy_slots()

    def get_available_slots(self, slotframe_handle=0):
        return self.slotframes[slotframe_handle].get_available_slots()

    def get_cell(self, slot_offset, channel_offset, mac_addr, slotframe_handle=0):
        slotframe = self.slotframes[slotframe_handle]
        cells = slotframe.get_cells_by_slot_offset(slot_offset)
        for cell in cells:
            if (
                    (cell.channel_offset == channel_offset)
                    and
                    (cell.mac_addr == mac_addr)
                ):
                return cell
        return None

    def get_cells(self, mac_addr=None, slotframe_handle=0):
        slotframe = self.slotframes[slotframe_handle]
        return slotframe.get_cells_by_mac_addr(mac_addr)

    # slotframe
    def get_slotframe(self, slotframe_handle):
        if slotframe_handle in self.slotframes:
            return self.slotframes[slotframe_handle]
        else:
            return None

    def add_slotframe(self, slotframe_handle, length):
        assert slotframe_handle not in self.slotframes
        self.slotframes[slotframe_handle] = SlotFrame(
            mote_id          = self.mote.id,
            slotframe_handle = slotframe_handle,
            num_slots        = length
        )

    def delete_slotframe(self, slotframe_handle):
        assert slotframe_handle in self.slotframes
        del self.slotframes[slotframe_handle]

    # EB / Enhanced Beacon

    def startSendingEBs(self):
        self.iAmSendingEBs = True

    def stopSendingEBs(self):
        self.iAmSendingEBs = True

    def schedule_next_listeningForEB_cell(self):

        assert not self.getIsSync()

        # schedule at next ASN
        self.engine.scheduleAtAsn(
            asn              = self.engine.getAsn()+1,
            cb               = self._action_listeningForEB_cell,
            uniqueTag        = (self.mote.id, '_action_listeningForEB_cell'),
            intraSlotOrder   = d.INTRASLOTORDER_STARTSLOT,
        )

    # minimal

    def add_minimal_cell(self):
        assert self.isSync

        # the minimal cell is allocated in slotframe 0
        self.addCell(
            slotOffset       = 0,
            channelOffset    = 0,
            neighbor         = None,
            cellOptions      = [
                d.CELLOPTION_TX,
                d.CELLOPTION_RX,
                d.CELLOPTION_SHARED
            ],
            slotframe_handle = 0
        )

    def delete_minimal_cell(self):
        # the minimal cell should be allocated in slotframe 0
        self.deleteCell(
            slotOffset       = 0,
            channelOffset    = 0,
            neighbor         = None,
            cellOptions      = [
                d.CELLOPTION_TX,
                d.CELLOPTION_RX,
                d.CELLOPTION_SHARED
            ],
            slotframe_handle = 0
        )

    # schedule interface

    def addCell(self, slotOffset, channelOffset, neighbor, cellOptions, slotframe_handle=0):

        assert isinstance(slotOffset, int)
        assert isinstance(channelOffset, int)
        assert isinstance(cellOptions, list)

        slotframe = self.slotframes[slotframe_handle]

        # add cell
        cell = Cell(slotOffset, channelOffset, cellOptions, neighbor)
        slotframe.add(cell)

        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self._schedule_next_active_slot()

    def deleteCell(self, slotOffset, channelOffset, neighbor, cellOptions, slotframe_handle=0):
        assert isinstance(slotOffset, int)
        assert isinstance(channelOffset, int)
        assert isinstance(cellOptions, list)

        slotframe = self.slotframes[slotframe_handle]

        # find a target cell. if the cell is not scheduled, the following
        # raises an exception
        cell = self.get_cell(slotOffset, channelOffset, neighbor, slotframe_handle)
        assert cell.mac_addr == neighbor
        assert cell.options == cellOptions

        # delete cell
        slotframe.delete(cell)

        # reschedule the next active cell, in case it is now earlier
        if self.getIsSync():
            self._schedule_next_active_slot()

    # tx queue interface with upper layers

    def enqueue(self, packet, priority=False):

        assert packet['type'] != d.PKT_TYPE_EB
        assert 'srcMac' in packet['mac']
        assert 'dstMac' in packet['mac']

        goOn = True

        # check there is space in txQueue
        if goOn:
            if (
                    (priority is False)
                    and
                    (len(self.txQueue) >= d.TSCH_QUEUE_SIZE)
                ):
                # my TX queue is full

                # drop
                self.mote.drop_packet(
                    packet  = packet,
                    reason  = SimEngine.SimLog.DROPREASON_TXQUEUE_FULL,
                )

                # couldn't enqueue
                goOn = False

        # check that I have cell to transmit on
        if goOn:
            shared_tx_cells = filter(
                lambda cell: d.CELLOPTION_TX in cell.options,
                self.mote.tsch.get_cells(None)
            )
            dedicated_tx_cells = filter(
                lambda cell: d.CELLOPTION_TX in cell.options,
                self.mote.tsch.get_cells(packet['mac']['dstMac'])
            )
            if (
                    (len(shared_tx_cells) == 0)
                    and
                    (len(dedicated_tx_cells) == 0)
                ):
                # I don't have any cell to transmit on

                # drop
                self.mote.drop_packet(
                    packet  = packet,
                    reason  = SimEngine.SimLog.DROPREASON_NO_TX_CELLS,
                )

                # couldn't enqueue
                goOn = False

        # if I get here, everyting is OK, I can enqueue
        if goOn:
            # set retriesLeft which should be renewed at every hop
            packet['mac']['retriesLeft'] = d.TSCH_MAXTXRETRIES
            if priority:
                self.txQueue.insert(0, packet)
            else:
                # add to txQueue
                self.txQueue    += [packet]

        return goOn

    def dequeue(self, packet):
        if packet in self.txQueue:
            self.txQueue.remove(packet)
        else:
            # do nothing
            pass

    def get_first_packet_to_send(self, dst_mac_addr=None):
        packet_to_send = None
        if dst_mac_addr is None:
            if len(self.txQueue) == 0:
                # txQueue is empty; we may return an EB
                if (
                        self.mote.clear_to_send_EBs_DATA()
                        and
                        self._decided_to_send_eb()
                    ):
                    packet_to_send = self._create_EB()
                else:
                    packet_to_send = None
            else:
                # return the first one in the TX queue, whose destination MAC
                # is not associated with any of allocated (dedicated) TX cells
                for packet in self.txQueue:
                    packet_to_send = packet # tentatively
                    for _, slotframe in self.slotframes.items():
                        dedicated_tx_cells = filter(
                            lambda cell: d.CELLOPTION_TX in cell.options,
                            slotframe.get_cells_by_mac_addr(packet['mac']['dstMac'])
                        )
                        if len(dedicated_tx_cells) > 0:
                            packet_to_send = None
                            break # try the next packet in TX queue

                    if packet_to_send is not None:
                        # found a good packet to send
                        break

                # if no suitable packet is found, packet_to_send remains None
        else:
            for packet in self.txQueue:
                if packet['mac']['dstMac'] == dst_mac_addr:
                    # return the first one having the dstMac
                    packet_to_send = packet
                    break
            # if no packet is found, packet_to_send remains None

        return packet_to_send

    def get_num_packet_in_tx_queue(self, dst_mac_addr=None):
        if dst_mac_addr is None:
            return len(self.txQueue)
        else:
            return len(
                [
                    pkt for pkt in self.txQueue if (
                        pkt['mac']['dstMac'] == dst_mac_addr
                    )
                ]
            )

    def remove_packets_in_tx_queue(self, type, dstMac=None):
        i = 0
        while i < len(self.txQueue):
            if (
                    (self.txQueue[i]['type'] == type)
                    and
                    (
                        (dstMac is None)
                        or
                        (self.txQueue[i]['mac']['dstMac'] == dstMac)
                    )
                ):
                del self.txQueue[i]
            else:
                i += 1

    def remove_tx_packet(self, packet):
        """remove a specific TX packet in the queue"""
        target_packet_index = None

        for i in range(len(self.txQueue)):
            tx_packet_copy = copy.deepcopy(self.txQueue[i])

            # remove retriesLeft element for comparison
            del tx_packet_copy['mac']['retriesLeft']

            if tx_packet_copy == packet:
                target_packet_index = i
                break

        if target_packet_index is not None:
            del self.txQueue[target_packet_index]


    # interface with radio

    def txDone(self, isACKed):
        assert isACKed in [True,False]

        asn         = self.engine.getAsn()
        active_cell = self.active_cell

        self.active_cell = None

        assert active_cell is not None
        assert d.CELLOPTION_TX in active_cell.options
        assert self.waitingFor == d.WAITING_FOR_TX

        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_TXDONE,
            {
                '_mote_id':       self.mote.id,
                'channel':        self.channel,
                'packet':         self.pktToSend,
                'isACKed':        isACKed,
            }
        )

        if self.pktToSend['mac']['dstMac'] == d.BROADCAST_ADDRESS:
            # I just sent a broadcast packet

            assert self.pktToSend['type'] in [
                d.PKT_TYPE_EB,
                d.PKT_TYPE_DIO,
                d.PKT_TYPE_DIS
            ]
            assert isACKed == False

            # EBs are never in txQueue, no need to remove.
            if self.pktToSend['type'] != d.PKT_TYPE_EB:
                self.dequeue(self.pktToSend)

        else:
            # I just sent a unicast packet...

            # TODO send txDone up; need a more general way
            if (
                    (isACKed is True)
                    and
                    (self.pktToSend['type'] == d.PKT_TYPE_SIXP)
                ):
                self.mote.sixp.recv_mac_ack(self.pktToSend)
            self.mote.rpl.indicate_tx(active_cell, self.pktToSend['mac']['dstMac'], isACKed)

            # update the backoff exponent
            self._update_backoff_state(
                isRetransmission = self._is_retransmission(self.pktToSend),
                isSharedLink     = d.CELLOPTION_SHARED in active_cell.options,
                isTXSuccess      = isACKed
            )

            if isACKed:
                # ... which was ACKed

                # update schedule stats
                active_cell.increment_num_tx_ack()

                # time correction
                if self.clock.source == self.pktToSend['mac']['dstMac']:
                    self.asnLastSync = asn # ACK-based sync
                    self.clock.sync()
                    self._reset_keep_alive_timer()

                # remove packet from queue
                self.dequeue(self.pktToSend)

            else:
                # ... which was NOT ACKed

                # decrement 'retriesLeft' counter associated with that packet
                assert self.pktToSend['mac']['retriesLeft'] >= 0
                self.pktToSend['mac']['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.pktToSend['mac']['retriesLeft'] < 0:

                    # remove packet from queue
                    self.dequeue(self.pktToSend)

                    # drop
                    self.mote.drop_packet(
                        packet = self.pktToSend,
                        reason = SimEngine.SimLog.DROPREASON_MAX_RETRIES,
                    )

        # end of radio activity, not waiting for anything
        self.waitingFor = None
        self.pktToSend  = None

    def rxDone(self, packet):

        # local variables
        asn         = self.engine.getAsn()
        active_cell = self.active_cell

        self.active_cell = None

        # copy the received packet to a new packet instance since the passed
        # "packet" should be kept as it is so that Connectivity can use it
        # after this rxDone() process.
        new_packet = copy.deepcopy(packet)
        packet = new_packet

        # make sure I'm in the right state
        if self.getIsSync():
            assert active_cell is not None
            assert active_cell.is_rx_on
            assert self.waitingFor == d.WAITING_FOR_RX

        # not waiting for anything anymore
        self.waitingFor = None

        # abort if received nothing (idle listen)
        if packet == None:
            return False # isACKed

        # add the source mote to the neighbor list if it's not listed yet
        if packet['mac']['srcMac'] not in self.neighbor_table:
            self.neighbor_table.append(packet['mac']['srcMac'])

        # abort if I received a frame for someone else
        if (
                (packet['mac']['dstMac'] != d.BROADCAST_ADDRESS)
                and
                (self.mote.is_my_mac_addr(packet['mac']['dstMac']) is False)
            ):
            return False # isACKed

        # if I get here, I received a frame at the link layer (either unicast for me, or broadcast)

        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_RXDONE,
            {
                '_mote_id':        self.mote.id,
                'packet':          packet,
            }
        )

        # time correction
        if self.clock.source == packet['mac']['srcMac']:
            self.asnLastSync = asn # packet-based sync
            self.clock.sync()
            self._reset_keep_alive_timer()

        # update schedule stats
        if self.getIsSync():
            active_cell.increment_num_rx()

        if   self.mote.is_my_mac_addr(packet['mac']['dstMac']):
            # link-layer unicast to me

            # ACK frame
            isACKed = True

            # dispatch to the right upper layer
            if   packet['type'] == d.PKT_TYPE_SIXP:
                self.mote.sixp.recv_packet(packet)
            elif packet['type'] == d.PKT_TYPE_KEEP_ALIVE:
                # do nothing but send back an ACK
                pass
            elif 'net' in packet:
                self.mote.sixlowpan.recvPacket(packet)
            else:
                raise SystemError()

        elif packet['mac']['dstMac'] == d.BROADCAST_ADDRESS:
            # link-layer broadcast

            # do NOT ACK frame (broadcast)
            isACKed = False

            # dispatch to the right upper layer
            if   packet['type'] == d.PKT_TYPE_EB:
                self._action_receiveEB(packet)
            elif 'net' in packet:
                assert packet['type'] in [
                    d.PKT_TYPE_DIO,
                    d.PKT_TYPE_DIS
                ]
                self.mote.sixlowpan.recvPacket(packet)
            else:
                raise SystemError()

        else:
            raise SystemError()

        return isACKed

    #======================== private ==========================================

    # listeningForEB

    def _action_listeningForEB_cell(self):
        """
        active slot starts, while mote is listening for EBs
        """

        assert not self.getIsSync()

        # choose random channel
        channel = random.randint(0, self.settings.phy_numChans-1)

        # start listening
        self.mote.radio.startRx(
            channel = channel,
        )

        # indicate that we're waiting for the RX operation to finish
        self.waitingFor = d.WAITING_FOR_RX

        # schedule next listeningForEB cell
        self.schedule_next_listeningForEB_cell()

    # active cell

    def _select_active_cell(self, candidate_cells):
        active_cell = None
        packet_to_send = None

        for cell in candidate_cells:
            if cell.is_tx_on():
                if (
                        (packet_to_send is None)
                        or
                        (
                            self.get_num_packet_in_tx_queue(packet_to_send['mac']['dstMac'])
                            <
                            self.get_num_packet_in_tx_queue(cell.mac_addr)
                        )
                    ):
                    # try to find a packet to send
                    _packet_to_send = self.get_first_packet_to_send(cell.mac_addr)

                    # take care of the retransmission backoff algorithm
                    if _packet_to_send is not None:
                        if (
                            cell.is_shared_on()
                            and
                            self._is_retransmission(_packet_to_send)
                            and
                            (self.backoff_remaining_delay > 0)
                        ):
                            self.backoff_remaining_delay -= 1
                            # skip this cell for transmission
                        else:
                            packet_to_send = _packet_to_send
                            active_cell = cell

            if (
                    cell.is_rx_on()
                    and
                    (packet_to_send is None)
                ):
                active_cell = cell

        return active_cell, packet_to_send


    def _schedule_next_active_slot(self):

        assert self.getIsSync()

        asn       = self.engine.getAsn()
        tsCurrent = asn % self.settings.tsch_slotframeLength

        # find closest active slot in schedule

        if not self.isSync:
            self.engine.removeFutureEvent(uniqueTag=(self.mote.id, '_action_active_cell'))
            return

        try:
            tsDiffMin = min(
                [
                    slotframe.get_num_slots_to_next_active_cell(asn)
                    for _, slotframe in self.slotframes.items() if (
                        len(slotframe.get_busy_slots()) > 0
                    )
                ]
            )
        except ValueError:
            # we don't have any cell; return without scheduling the next active
            # slot
            return

        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn            = asn+tsDiffMin,
            cb             = self._action_active_cell,
            uniqueTag      = (self.mote.id, '_action_active_cell'),
            intraSlotOrder = d.INTRASLOTORDER_STARTSLOT,
        )

    def _action_active_cell(self):

        # local shorthands
        asn = self.engine.getAsn()

        # make sure we're not in the middle of a TX/RX operation
        assert self.waitingFor == None
        # make sure we are not busy sending a packet
        assert self.pktToSend == None

        # section 6.2.6.4 of IEEE 802.15.4-2015:
        # "When, for any given timeslot, a device has links in multiple
        # slotframes, transmissions take precedence over receives, and lower
        # macSlotframeHandle slotframes takes precedence over higher
        # macSlotframeHandle slotframes."

        candidate_cells = []
        for _, slotframe in self.slotframes.items():
            candidate_cells = slotframe.get_cells_at_asn(asn)
            if len(candidate_cells) > 0:
                break

        if len(candidate_cells) == 0:
            # we don't have any cell at this asn. we may have used to have
            # some, which possibly were removed; do nothing
            pass
        else:
            # identify a cell to be activated
            self.active_cell, self.pktToSend = self._select_active_cell(candidate_cells)

        if self.active_cell:
            if self.pktToSend is None:
                assert self.active_cell.is_rx_on()
                self._action_RX()
            else:
                assert self.active_cell.is_tx_on()
                self._action_TX(self.pktToSend)
                if self.pktToSend['mac']['dstMac'] == self.clock.source:
                    # we're going to send a frame to our time source; reset the
                    # keep-alive timer
                    self._reset_keep_alive_timer()
        else:
            # do nothing
            pass

        # notify upper layers
        for cell in candidate_cells:
            if cell.is_tx_on():
                if cell.mac_addr is not None:
                    self.mote.sf.indication_dedicated_tx_cell_elapsed(
                        cell = cell,
                        used = (
                            (self.active_cell == cell)
                            and
                            (self.pktToSend is not None)
                        )
                    )

        # schedule the next active slot
        self._schedule_next_active_slot()

    def _action_TX(self,pktToSend):

        # update cell stats
        self.active_cell.increment_num_tx()

        # send packet to the radio
        self.mote.radio.startTx(
            channel = self.active_cell.channel_offset,
            packet  = pktToSend,
        )

        # indicate that we're waiting for the TX operation to finish
        self.waitingFor = d.WAITING_FOR_TX
        self.channel    = self.active_cell.channel_offset

    def _action_RX(self):

        # start listening
        self.mote.radio.startRx(
            channel = self.active_cell.channel_offset
        )

        # indicate that we're waiting for the RX operation to finish
        self.waitingFor = d.WAITING_FOR_RX
        self.channel    = self.active_cell.channel_offset

    # EBs

    def _decided_to_send_eb(self):
        # short-hand
        prob = float(self.settings.tsch_probBcast_ebProb)
        n    = 1 + len(self.neighbor_table)

        # following the Bayesian broadcasting algorithm
        return (
            (random.random() < (prob / n))
            and
            self.iAmSendingEBs
        )

    def _create_EB(self):

        join_metric = self.mote.rpl.getDagRank()
        if join_metric is None:
            newEB = None
        else:
            # create
            newEB = {
                'type':            d.PKT_TYPE_EB,
                'app': {
                    'join_metric': self.mote.rpl.getDagRank() - 1,
                },
                'mac': {
                    'srcMac':      self.mote.get_mac_addr(),
                    'dstMac':      d.BROADCAST_ADDRESS,     # broadcast
                },
            }

            # log
            self.log(
                SimEngine.SimLog.LOG_TSCH_EB_TX,
                {
                    "_mote_id": self.mote.id,
                    "packet":   newEB,
                }
            )

        return newEB

    def _action_receiveEB(self, packet):

        assert packet['type'] == d.PKT_TYPE_EB

        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_EB_RX,
            {
                "_mote_id": self.mote.id,
                "packet":   packet,
            }
        )

        # abort if I'm the root
        if self.mote.dagRoot:
            return

        if not self.getIsSync():
            # receiving EB while not sync'ed

            # I'm now sync'ed!
            self.clock.sync(packet['mac']['srcMac'])
            self.setIsSync(True) # mote

            # the mote that sent the EB is now by join proxy
            self.join_proxy = netaddr.EUI(packet['mac']['srcMac'])

            # add the minimal cell to the schedule (read from EB)
            self.add_minimal_cell() # mote

            # trigger join process
            self.mote.secjoin.startJoinProcess()

    # Retransmission backoff algorithm
    def _is_retransmission(self, packet):
        assert packet is not None
        if 'retriesLeft' not in packet['mac']:
            assert packet['mac']['dstMac'] == d.BROADCAST_ADDRESS
            return False
        else:
            return packet['mac']['retriesLeft'] < d.TSCH_MAXTXRETRIES

    def _decide_backoff_delay(self):
        # Section 6.2.5.3 of IEEE 802.15.4-2015: "The MAC sublayer shall delay
        # for a random number in the range 0 to (2**BE - 1) shared links (on
        # any slotframe) before attempting a retransmission on a shared link."
        self.backoff_remaining_delay = random.randint(
            0,
            pow(2, self.backoff_exponent) - 1
        )

    def _reset_backoff_state(self):
        old_be = self.backoff_exponent
        self.backoff_exponent = d.TSCH_MIN_BACKOFF_EXPONENT
        self.log(
            SimEngine.SimLog.LOG_TSCH_BACKOFF_EXPONENT_UPDATED,
            {
                '_mote_id': self.mote.id,
                'old_be'  : old_be,
                'new_be'  : self.backoff_exponent
            }
        )
        self._decide_backoff_delay()

    def _increase_backoff_state(self):
        old_be = self.backoff_exponent
        # In Figure 6-6 of IEEE 802.15.4, BE (backoff exponent) is updated as
        # "BE - min(BE 0 1, macMinBe)". However, it must be incorrect. The
        # right formula should be "BE = min(BE + 1, macMaxBe)", that we apply
        # here.
        self.backoff_exponent = min(
            self.backoff_exponent + 1,
            d.TSCH_MAX_BACKOFF_EXPONENT
        )
        self.log(
            SimEngine.SimLog.LOG_TSCH_BACKOFF_EXPONENT_UPDATED,
            {
                '_mote_id': self.mote.id,
                'old_be'  : old_be,
                'new_be'  : self.backoff_exponent
            }
        )
        self._decide_backoff_delay()

    def _update_backoff_state(
            self,
            isRetransmission,
            isSharedLink,
            isTXSuccess
        ):
        if isSharedLink:
            if isTXSuccess:
                # Section 6.2.5.3 of IEEE 802.15.4-2015: "A successful
                # transmission in a shared link resets the backoff window to
                # the minimum value."
                self._reset_backoff_state()
            else:
                if isRetransmission:
                    # Section 6.2.5.3 of IEEE 802.15.4-2015: "The backoff window
                    # increases for each consecutive failed transmission in a
                    # shared link."
                    self._increase_backoff_state()
                else:
                    # First attempt to transmit the packet
                    #
                    # Section 6.2.5.3 of IEEE 802.15.4-2015: "A device upon
                    # encountering a transmission failure in a shared link
                    # shall initialize the BE to macMinBe."
                    self._reset_backoff_state()

        else:
            # dedicated link (which is different from a dedicated *cell*)
            if isTXSuccess:
                # successful transmission
                if len(self.txQueue) == 0:
                    # Section 6.2.5.3 of IEEE 802.15.4-2015: "The backoff
                    # window is reset to the minimum value if the transmission
                    # in a dedicated link is successful and the transmit queue
                    # is then empty."
                    self._reset_backoff_state()
                else:
                    # Section 6.2.5.3 of IEEE 802.15.4-2015: "The backoff
                    # window does not change when a transmission is successful
                    # in a dedicated link and the transmission queue is still
                    # not empty afterwards."
                    pass
            else:
                # Section 6.2.5.3 of IEEE 802.15.4-2015: "The backoff window
                # does not change when a transmission is a failure in a
                # dedicated link."
                pass

    # Synchronization / Keep-Alive
    def _send_keep_alive_message(self):
        if self.clock.source is None:
            return

        packet = {
            'type': d.PKT_TYPE_KEEP_ALIVE,
            'mac': {
                'srcMac': self.mote.get_mac_addr(),
                'dstMac': self.clock.source
            }
        }
        self.enqueue(packet, priority=True)
        # the next keep-alive event will be scheduled on receiving an ACK

    def _start_keep_alive_timer(self):
        assert self.settings.tsch_keep_alive_interval >= 0
        if (
                (self.settings.tsch_keep_alive_interval == 0)
                or
                (self.mote.dagRoot is True)
            ):
            # do nothing
            pass
        else:
            # the clock drift of the child against the parent should be less
            # than macTsRxWait/2 so that they can communicate with each
            # other. Their clocks can be off by one clock interval at the
            # most. This means, the clock difference between the child and the
            # parent could be clock_interval just after synchronization. then,
            # the possible minimum guard time is ((macTsRxWait / 2) -
            # clock_interval). When macTsRxWait is 2,200 usec and
            # clock_interval is 30 usec, the minimum guard time is 1,070
            # usec. they will be desynchronized without keep-alive in 16
            # seconds as the paper titled "Adaptive Synchronization in
            # IEEE802.15.4e Networks" describes.
            #
            # the keep-alive interval should be configured in config.json with
            # "tsch_keep_alive_interval".
            self.engine.scheduleIn(
                delay          = self.settings.tsch_keep_alive_interval,
                cb             = self._send_keep_alive_message,
                uniqueTag      = self._get_keep_alive_event_tag(),
                intraSlotOrder = d.INTRASLOTORDER_STACKTASKS
            )

    def _stop_keep_alive_timer(self):
        self.engine.removeFutureEvent(
            uniqueTag = self._get_keep_alive_event_tag()
        )

    def _reset_keep_alive_timer(self):
        self._stop_keep_alive_timer()
        self._start_keep_alive_timer()

    def _get_keep_alive_event_tag(self):
        return '{0}-{1}'.format(self.mote.id, 'tsch.keep_alive_event')


class Clock(object):
    def __init__(self, mote):
        # singleton
        self.engine   = SimEngine.SimEngine.SimEngine()
        self.settings = SimEngine.SimSettings.SimSettings()

        # local variables
        self.mote = mote

        # instance variables which can be accessed directly from outside
        self.source = None

        # private variables
        self._clock_interval = 1.0 / self.settings.tsch_clock_frequency
        self._error_rate     = self._initialize_error_rate()

        self.desync()

    @staticmethod
    def get_clock_by_mac_addr(mac_addr):
        engine = SimEngine.SimEngine.SimEngine()
        mote = engine.get_mote_by_mac_addr(mac_addr)
        return mote.tsch.clock

    def desync(self):
        self.source             = None
        self._clock_off_on_sync = 0
        self._accumulated_error = 0
        self._last_clock_access = None

    def sync(self, clock_source=None):
        if self.mote.dagRoot is True:
            # if you're the DAGRoot, you should have the perfect clock from the
            # point of view of the network.
            self._clock_off_on_sync = 0
        else:
            if clock_source is None:
                assert self.source is not None
            else:
                self.source = clock_source

            # the clock could be off by between 0 and 30 usec (clock interval)
            # from the clock source when 32.768 Hz oscillators are used on the
            # both sides. in addition, the clock source also off from a certain
            # amount of time from its source.
            off_from_source = random.random() * self._clock_interval
            source_clock = self.get_clock_by_mac_addr(self.source)
            self._clock_off_on_sync = off_from_source + source_clock.get_drift()

        self._accumulated_error = 0
        self._last_clock_access = self.engine.getAsn()

    def get_drift(self):
        if self.mote.dagRoot is True:
            # if we're the DAGRoot, we are the clock source of the entire
            # network. our clock never drifts from itself. Its clock drift is
            # taken into accout by motes who use our clock as their reference
            # clock.
            error = 0
        else:
            assert self._last_clock_access <= self.engine.getAsn()
            slot_duration = self.engine.settings.tsch_slotDuration
            elapsed_slots = self.engine.getAsn() - self._last_clock_access
            elapsed_time  = elapsed_slots * slot_duration
            error = elapsed_time * self._error_rate

        # update the variables
        self._accumulated_error += error
        self._last_clock_access = self.engine.getAsn()

        # return the result
        return self._clock_off_on_sync + self._accumulated_error

    def _initialize_error_rate(self):
        # private variables:
        # the clock drifts by its error rate. for simplicity, we double the
        # error rate to express clock drift from the time source. That is,
        # our clock could drift by 30 ppm at the most and the clock of time
        # source also could drift as well ppm. Then, our clock could drift
        # by 60 ppm from the clock of the time source.
        #
        # we assume the error rate is constant over the simulation time.
        max_drift = (
            float(self.settings.tsch_clock_max_drift_ppm) / pow(10, 6)
        )
        return random.uniform(-1 * max_drift * 2, max_drift * 2)


class SlotFrame(object):
    def __init__(self, mote_id, slotframe_handle, num_slots):
        self.log = SimEngine.SimLog.SimLog().log

        self.mote_id = mote_id
        self.slotframe_handle = slotframe_handle
        self.length = num_slots
        self.slots  = [[] for _ in range(self.length)]
        # index by neighbor_mac_addr for quick access
        self.cells  = {}

    def __repr__(self):
        return 'slotframe(length: {0}, num_cells: {1})'.format(
            self.length,
            len(list(chain.from_iterable(self.slots)))
        )

    def add(self, cell):
        assert cell.slot_offset < self.length
        self.slots[cell.slot_offset].append(cell)
        if cell.mac_addr not in self.cells.keys():
            self.cells[cell.mac_addr] = [cell]
        else:
            self.cells[cell.mac_addr].append(cell)

        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_ADD_CELL,
            {
                '_mote_id':        self.mote_id,
                'slotFrameHandle': self.slotframe_handle,
                'slotOffset':      cell.slot_offset,
                'channelOffset':   cell.channel_offset,
                'neighbor':        cell.mac_addr,
                'cellOptions':     cell.options
            }
        )

    def delete(self, cell):
        assert cell.slot_offset < self.length
        assert cell in self.slots[cell.slot_offset]
        assert cell in self.cells[cell.mac_addr]
        self.slots[cell.slot_offset].remove(cell)
        self.cells[cell.mac_addr].remove(cell)
        if len(self.cells[cell.mac_addr]) == 0:
            del self.cells[cell.mac_addr]

        # log
        self.log(
            SimEngine.SimLog.LOG_TSCH_DELETE_CELL,
            {
                '_mote_id':        self.mote_id,
                'slotFrameHandle': self.slotframe_handle,
                'slotOffset':      cell.slot_offset,
                'channelOffset':   cell.channel_offset,
                'neighbor':        cell.mac_addr,
                'cellOptions':     cell.options,
            }
        )

    def get_cells_by_slot_offset(self, slot_offset):
        assert slot_offset < self.length
        return self.slots[slot_offset]

    def get_cells_at_asn(self, asn):
        slot_offset = asn % self.length
        return self.get_cells_by_slot_offset(slot_offset)

    def get_cells_by_mac_addr(self, mac_addr):
        if mac_addr in self.cells.keys():
            return self.cells[mac_addr]
        else:
            return []

    def get_busy_slots(self):
        ret_val = []
        for i in range(self.length):
            if len(self.slots[i]) > 0:
                ret_val.append(i)
        return ret_val

    def get_num_slots_to_next_active_cell(self, asn):
        for diff in range(1, self.length + 1):
            slot_offset = (asn + diff) % self.length
            if len(self.slots[slot_offset]) > 0:
                return diff
        return None

    def get_available_slots(self):
        """
        Get the list of slot offsets that are not being used (no cell attached)
        :return: a list of slot offsets (int)
        :rtype: list
        """
        return [i for i, slot in enumerate(self.slots) if len(slot) == 0]

    def get_cells_filtered(self, mac_addr="", cell_options=None):
        """
        Returns a filtered list of cells
        Filtering can be done by cell options, mac_addr or both
        :param mac_addr: the neighbor mac_addr
        :param cell_options: a list of cell options
        :rtype: list
        """

        if mac_addr == "":
            target_cells = chain.from_iterable(self.slots)
        elif mac_addr not in self.cells:
            target_cells = []
        else:
            target_cells = self.cells[mac_addr]

        if cell_options is None:
            condition = lambda c: True
        else:
            condition = lambda c: sorted(c.options) == sorted(cell_options)

        # apply filter
        return filter(condition, target_cells)

    def set_length(self, new_length):
        # delete extra cells and slots if reducing slotframe length
        if new_length < self.length:
            # delete cells
            cells = [c for cells in self.cells.itervalues() for c in cells]
            for cell in cells:
                if cell.slot_offset > (new_length + 1):
                    self.delete(cell)
            # delete slots
            self.slots = self.slots[:new_length]
        # add slots if increasing slotframe length
        elif new_length > self.length:
            # add slots
            self.slots += [[] for _ in range(self.length, new_length)]

        # apply the new length
        self.length = new_length

class Cell(object):
    def __init__(
            self,
            slot_offset,
            channel_offset,
            options,
            mac_addr=None,
            is_advertising=False
        ):

        # FIXME: is_advertising is not used effectively now

        # slot_offset and channel_offset are 16-bit values
        assert slot_offset    < 0x10000
        assert channel_offset < 0x10000

        self.slot_offset    = slot_offset
        self.channel_offset = channel_offset
        self.options        = options
        self.mac_addr       = mac_addr

        if is_advertising:
            self.link_type = d.LINKTYPE_ADVERTISING
        else:
            self.link_type = d.LINKTYPE_NORMAL

        # stats
        self.num_tx     = 0
        self.num_tx_ack = 0
        self.num_rx     = 0

    def __repr__(self):

        return 'cell({0})'.format(
            ', '.join(
                [
                    'slot_offset: {0}'.format(self.slot_offset),
                    'channel_offset: {0}'.format(self.channel_offset),
                    'mac_addr: {0}'.format(self.mac_addr),
                    'options: [{0}]'.format(', '.join(self.options))
                ]
            )
        )

    def increment_num_tx(self):
        self.num_tx += 1

        # Seciton 5.3 of draft-ietf-6tisch-msf-00: "When NumTx reaches 256,
        # both NumTx and NumTxAck MUST be divided by 2.  That is, for example,
        # from NumTx=256 and NumTxAck=128, they become NumTx=128 and
        # NumTxAck=64. This operation does not change the value of the PDR, but
        # allows the counters to keep incrementing.
        if self.num_tx == 256:
            self.num_tx /= 2
            self.num_tx_ack /= 2

    def increment_num_tx_ack(self):
        self.num_tx_ack += 1

    def increment_num_rx(self):
        self.num_rx += 1

    def is_tx_on(self):
        return d.CELLOPTION_TX in self.options

    def is_rx_on(self):
        return d.CELLOPTION_RX in self.options

    def is_shared_on(self):
        return d.CELLOPTION_SHARED in self.options
