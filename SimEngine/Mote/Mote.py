#!/usr/bin/python
"""
\brief Model of a 6TiSCH mote.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
\author Malisa Vucinic <malisa.vucinic@inria.fr>
\author Esteban Municio <esteban.municio@uantwerpen.be>
\author Glenn Daneels <glenn.daneels@uantwerpen.be>
"""

# =========================== imports =========================================

import copy
import random
import threading
import math

# Mote sub-modules
import app
import secjoin
import rpl
import sf
import sixp
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Mote')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

# =========================== defines =========================================

# =========================== body ============================================

class Mote(object):

    def __init__(self, id):

        # store params
        self.id                        = id

        # admin
        self.dataLock                  = threading.RLock()
        # identifiers
        self.dagRoot                   = False
        self.dagRootAddress            = None
        # stats
        self.firstBeaconAsn            = 0

        self.packetLatencies           = []      # in slots
        self.packetHops                = []

        # singletons (to access quicker than recreate every time)
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()
        self.propagation               = SimEngine.Propagation.Propagation()

        # stack
        # app
        self.app                       = app.App(self)
        # frag
        # rpl
        self.rpl                       = rpl.Rpl(self)
        # sf
        self.sf                        = sf.SchedulingFunction.get_sf(self.settings.sf_type)
        # 6P
        self.sixp                      = sixp.SixP(self)
        # secjoin
        self.secjoin                   = secjoin.SecJoin(self)
        # tsch
        self.schedule                  = {}      # indexed by ts, contains cell
        self.numCellsElapsed           = 0
        self.numCellsUsed              = 0
        self.numCellsToNeighbors       = {}      # indexed by neighbor, contains int
        self.numCellsFromNeighbors     = {}      # indexed by neighbor, contains int
        self.txQueue                   = []
        self.pktToSend                 = None
        self.waitingFor                = None
        self.timeCorrectedSlot         = None
        self.isSync                    = False
        self.firstEB                   = True    # flag to indicate first received enhanced beacon
        self._tsch_resetBroadcastBackoff()
        self.backoffPerNeigh           = {}
        self.backoffExponentPerNeigh   = {}
        # radio
        self.txPower                   = 0       # dBm
        self.antennaGain               = 0       # dBi
        self.noisepower                = -105    # dBm
        self.drift                     = random.uniform(-d.RADIO_MAXDRIFT, d.RADIO_MAXDRIFT)
        self.backoffBroadcast          = 0
        # wireless
        self.RSSI                      = {}      # indexed by neighbor
        self.PDR                       = {}      # indexed by neighbor
        # location
        # battery
        self.chargeConsumed            = 0

        # stats
        self.motestats                 = {}
        self._stats_resetMoteStats()
        self._stats_resetQueueStats()
        self._stats_resetLatencyStats()
        self._stats_resetHopsStats()
        self._stats_resetRadioStats()

    # ======================= stack ===========================================

    # ===== role

    def role_setDagRoot(self):
        self.dagRoot              = True
        self.rpl.setRank(0)
        self.rpl.setDagRank(0)
        self.daoParents           = {}  # dictionary containing parents of each node from whom DAG root received a DAO
        self.packetLatencies      = []  # in slots
        self.packetHops           = []
        self.secjoin.setIsJoined(True)
        self.isSync               = True

        # imprint DAG root's ID at each mote
        for mote in self.engine.motes:
            mote.dagRootAddress = self

    #===== stack

    def _stack_init_synced(self):
        # start the stack layer by layer, we are sync'ed and joined

        # TSCH
        self._tsch_schedule_sendEB(firstEB=True)

        # RPL
        self.rpl.activate()

        # if not join, set the neighbor variables when initializing stack.
        # with join this is done when the nodes become synced. If root, initialize here anyway
        if (not self.settings.secjoin_enabled) or self.dagRoot:
            for m in self._myNeighbors():
                self._tsch_resetBackoffPerNeigh(m)

        # scheduling function
        self.sf.housekeeping(self)

        # app
        if not self.dagRoot:
            if self.settings.app_burstNumPackets and self.settings.app_burstTimestamp:
                self.app.schedule_mote_sendPacketBurstToDAGroot()
            else:
                self.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)

    #===== tsch

    #BROADCAST cells
    def _tsch_resetBroadcastBackoff(self):
        self.backoffBroadcast = 0
        self.backoffBroadcastExponent = d.TSCH_MIN_BACKOFF_EXPONENT - 1

    #SHARED Dedicated cells
    def _tsch_resetBackoffPerNeigh(self, neigh):
        self.backoffPerNeigh[neigh] = 0
        self.backoffExponentPerNeigh[neigh] = d.TSCH_MIN_BACKOFF_EXPONENT - 1

    def _tsch_enqueue(self, packet):

        if not self.rpl.findNextHop(packet):
            # I don't have a route

            # increment mote state
            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_RPL_DROP_NO_ROUTE['type'])

            return False

        elif not (self.getTxCells() or self.getSharedCells()):
            # I don't have any transmit cells

            # increment mote state
            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_NO_TX_CELLS['type'])

            return False

        elif len(self.txQueue) >= d.TSCH_QUEUE_SIZE:
            #my TX queue is full.

            # However, I will allow to add an additional packet in some specific ocasions
            # This is because if the queues of the nodes are filled with DATA packets, new nodes won't be able to enter properly in the network. So there are exceptions.

            # if join is enabled, all nodes will wait until all nodes have at least 1 Tx cell. So it is allowed to enqueue 1 aditional DAO, JOIN or 6P packet
            if packet['type'] == d.APP_TYPE_JOIN or packet['type'] == d.RPL_TYPE_DAO or packet['type'] == d.IANA_6TOP_TYPE_REQUEST or packet['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                for p in self.txQueue:
                    if packet['type'] == p['type']:
                        #There is already a DAO, JOIN or 6P in que queue, don't add more
                        self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type'])
                        return False
                self.txQueue    += [packet]
                return True

            # update mote stats
            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_QUEUE_FULL['type'])

            return False

        else:
            # all is good

            # enqueue packet
            self.txQueue    += [packet]

            return True

    def _tsch_action_enqueueEB(self):
        """ enqueue EB packet into stack """

        # only start sending EBs if: I am a DAG root OR (I have a preferred parent AND dedicated cells to that parent)
        if self.dagRoot or (self.rpl.getPreferredParent() and self.numCellsToNeighbors.get(self.rpl.getPreferredParent(), 0) != 0):

            # create new packet
            newPacket = {
                'asn': self.engine.getAsn(),
                'type': d.TSCH_TYPE_EB,
                'code': None,
                'payload': [self.rpl.getDagRank()],  # the payload is the rpl rank
                'retriesLeft': 1,  # do not retransmit broadcast
                'srcIp': self,
                'dstIp': d.BROADCAST_ADDRESS,
                'sourceRoute': []
            }

            # enqueue packet in TSCH queue
            if not self._tsch_enqueue(newPacket):
                # update mote stats
                self._radio_drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])

    def _tsch_schedule_sendEB(self, firstEB=False):

        if self.settings.tsch_ebPeriod_sec == 0:
            # disable periodic EB transmission
            return

        with self.dataLock:

            asn = self.engine.getAsn()

            if self.settings.tsch_probBcast_enabled:
                futureAsn = int(self.settings.tsch_slotframeLength)
            else:
                futureAsn = int(math.ceil(
                    random.uniform(
                        0.8 * self.settings.tsch_ebPeriod_sec,
                        1.2 * self.settings.tsch_ebPeriod_sec,
                    ) / self.settings.tsch_slotDuration
                ))

            # schedule at start of next cycle
            self.engine.scheduleAtAsn(
                asn=asn + futureAsn,
                cb=self._tsch_action_sendEB,
                uniqueTag=(self.id, '_tsch_action_sendEB'),
                priority=3,
            )

    def _tsch_action_sendEB(self):

        with self.dataLock:

            if self.settings.tsch_probBcast_enabled:
                beaconProb = float(self.settings.tsch_probBcast_ebProb) / float(len(self.secjoin.areAllNeighborsJoined())) if len(self.secjoin.areAllNeighborsJoined()) else float(self.settings.tsch_probBcast_ebProb)
                sendBeacon = True if random.random() < beaconProb else False
            else:
                sendBeacon = True
            if self.rpl.getPreferredParent() or self.dagRoot:
                if self.secjoin.isJoined() or not self.settings.secjoin_enabled:
                    if sendBeacon:
                        self._tsch_action_enqueueEB()
                        self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_TX_EB['type'])

            self._tsch_schedule_sendEB()  # schedule next EB

    def _tsch_action_receiveEB(self, type, smac, payload):

        # abort if I'm the root
        if self.dagRoot:
            return

        # got an EB, increment stats
        self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_RX_EB['type'])

        if self.firstEB and not self.isSync:
            # this is the first EB I'm receiving while joining: sync!

            assert self.settings.secjoin_enabled

            # log
            self._log(
                d.INFO,
                "[tsch] synced on EB received from mote {0}.",
                (smac.id,),
            )

            self.firstBeaconAsn = self.engine.getAsn()
            self.firstEB        = False
            self.isSync         = True

            # set neighbors variables before starting request cells to the preferred parent
            for m in self._myNeighbors():
                self._tsch_resetBackoffPerNeigh(m)

            # add the minimal cell to the schedule (read from EB)
            self._tsch_add_minimal_cell()

            # trigger join process
            self.secjoin.scheduleJoinProcess()  # trigger the join process

    def _tsch_schedule_activeCell(self):

        asn        = self.engine.getAsn()
        tsCurrent  = asn % self.settings.tsch_slotframeLength

        # find closest active slot in schedule
        with self.dataLock:

            if not self.schedule:
                self.engine.removeEvent(uniqueTag=(self.id, '_tsch_action_activeCell'))
                return

            tsDiffMin             = None

            for (ts, cell) in self.schedule.items():
                if   ts == tsCurrent:
                    tsDiff        = self.settings.tsch_slotframeLength
                elif ts > tsCurrent:
                    tsDiff        = ts-tsCurrent
                elif ts < tsCurrent:
                    tsDiff        = (ts+self.settings.tsch_slotframeLength)-tsCurrent
                else:
                    raise SystemError()

                if (not tsDiffMin) or (tsDiffMin > tsDiff):
                    tsDiffMin     = tsDiff

        # schedule at that ASN
        self.engine.scheduleAtAsn(
            asn         = asn+tsDiffMin,
            cb          = self._tsch_action_activeCell,
            uniqueTag   = (self.id, '_tsch_action_activeCell'),
            priority    = 0,
        )

    def _tsch_action_activeCell(self):
        """
        active slot starts. Determine what todo, either RX or TX, use the propagation model to introduce
        interference and Rx packet drops.
        """

        asn = self.engine.getAsn()
        ts  = asn % self.settings.tsch_slotframeLength

        with self.dataLock:

            # make sure this is an active slot
            assert ts in self.schedule
            # make sure we're not in the middle of a TX/RX operation
            assert not self.waitingFor

            cell = self.schedule[ts]

            # Signal to scheduling function that a cell to a neighbor has been triggered
            self.sf.signal_cell_elapsed(self, cell['neighbor'], cell['dir'])

            if  cell['dir'] == d.DIR_RX:

                # start listening
                self.propagation.startRx(
                    mote          = self,
                    channel       = cell['ch'],
                )

                # indicate that we're waiting for the RX operation to finish
                self.waitingFor   = d.DIR_RX

            elif cell['dir'] == d.DIR_TX:

                # check whether packet to send
                self.pktToSend = None
                if self.txQueue:
                    for pkt in self.txQueue:
                        # send the frame if next hop matches the cell destination
                        if pkt['nextHop'] == [cell['neighbor']]:
                            self.pktToSend = pkt
                            break

                # send packet
                if self.pktToSend:

                    # Signal to scheduling function that a cell to a neighbor is used
                    self.sf.signal_cell_used(self, cell['neighbor'], cell['dir'], d.DIR_TX, pkt['type'])

                    cell['numTx'] += 1

                    if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                        if pkt['code'] == d.IANA_6TOP_CMD_ADD:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_REQ['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_REQ['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            raise SystemError()

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_RESP['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_RESP['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                            pass
                        else:
                            raise SystemError()

                    self.propagation.startTx(
                        channel   = cell['ch'],
                        type      = self.pktToSend['type'],
                        code      = self.pktToSend['code'],
                        smac      = self,
                        dmac      = [cell['neighbor']],
                        srcIp     = self.pktToSend['srcIp'],
                        dstIp     = self.pktToSend['dstIp'],
                        srcRoute  = self.pktToSend['sourceRoute'],
                        payload   = self.pktToSend['payload'],
                    )

                    # indicate that we're waiting for the TX operation to finish
                    self.waitingFor   = d.DIR_TX

            elif cell['dir'] == d.DIR_TXRX_SHARED:

                if cell['neighbor'] == self._myNeighbors():
                    self.pktToSend = None
                    if self.txQueue and self.backoffBroadcast == 0:
                        for pkt in self.txQueue:
                            # send join packets on the shared cell only on first hop
                            if pkt['type'] == d.APP_TYPE_JOIN and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # send 6P messages on the shared broadcast cell only if there is no dedicated cells to that neighbor
                            elif pkt['type'] == d.IANA_6TOP_TYPE_REQUEST and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # send 6P messages on the shared broadcast cell only if there is no dedicated cells to that neighbor
                            elif pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and len(self.getTxCells(pkt['nextHop'][0]))+len(self.getSharedCells(pkt['nextHop'][0])) == 0:
                                self.pktToSend = pkt
                                break
                            # DIOs and EBs always go on the shared broadcast cell
                            elif pkt['type'] == d.RPL_TYPE_DIO or pkt['type'] == d.TSCH_TYPE_EB:
                                self.pktToSend = pkt
                                break
                            else:
                                continue
                    # Decrement backoff
                    if self.backoffBroadcast > 0:
                        self.backoffBroadcast -= 1
                else:
                    if self.isSync:
                        # check whether packet to send
                        self.pktToSend = None
                        if self.txQueue and self.backoffPerNeigh[cell['neighbor']] == 0:
                            for pkt in self.txQueue:
                                # send the frame if next hop matches the cell destination
                                if pkt['nextHop'] == [cell['neighbor']]:
                                    self.pktToSend = pkt
                                    break

                    # Decrement backoffPerNeigh
                    if self.backoffPerNeigh[cell['neighbor']] > 0:
                        self.backoffPerNeigh[cell['neighbor']] -= 1
                # send packet
                if self.pktToSend:

                    cell['numTx'] += 1

                    # to scheduling function that a cell to a neighbor is used
                    self.sf.signal_cell_used(self, cell['neighbor'], cell['dir'], d.DIR_TX, pkt['type'])

                    if pkt['type'] == d.IANA_6TOP_TYPE_REQUEST:
                        if pkt['code'] == d.IANA_6TOP_CMD_ADD:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_REQ['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_REQ['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            assert False

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_RESP['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_RESP['type'])
                            self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.sixp.getSixtopStates()[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                            pass
                        else:
                            assert False

                    self.propagation.startTx(
                        channel   = cell['ch'],
                        type      = self.pktToSend['type'],
                        code      = self.pktToSend['code'],
                        smac      = self,
                        dmac      = self.pktToSend['nextHop'],
                        srcIp     = self.pktToSend['srcIp'],
                        dstIp     = self.pktToSend['dstIp'],
                        srcRoute  = self.pktToSend['sourceRoute'],
                        payload   = self.pktToSend['payload'],
                    )
                    # indicate that we're waiting for the TX operation to finish
                    self.waitingFor   = d.DIR_TX

                else:
                    # start listening
                    self.propagation.startRx(
                         mote          = self,
                         channel       = cell['ch'],
                     )
                    # indicate that we're waiting for the RX operation to finish
                    self.waitingFor = d.DIR_RX

            # schedule next active cell
            self._tsch_schedule_activeCell()

    def _tsch_addCells(self, neighbor, cellList):
        """ Adds cell(s) to the schedule

        :param Mote || list neighbor:
        :param list cellList:
        :return:
        """

        with self.dataLock:
            for cell in cellList:
                assert cell[0] not in self.schedule.keys()
                self.schedule[cell[0]] = {
                    'ch':                        cell[1],
                    'dir':                       cell[2],
                    'neighbor':                  neighbor,
                    'numTx':                     0,
                    'numTxAck':                  0,
                    'numRx':                     0,
                    'history':                   [],
                    'sharedCellSuccess':         0,                       # indicator of success for shared cells
                    'sharedCellCollision':       0,                       # indicator of a collision for shared cells
                    'rxDetectedCollision':       False,
                    'debug_canbeInterfered':     [],                      # [debug] shows schedule collision that can be interfered with minRssi or larger level
                    'debug_interference':        [],                      # [debug] shows an interference packet with minRssi or larger level
                    'debug_lockInterference':    [],                      # [debug] shows locking on the interference packet
                    'debug_cellCreatedAsn':      self.engine.getAsn(),    # [debug]
                }
                # log
                self.engine.log(
                    SimEngine.SimLog.LOG_TSCH_ADD_CELL,
                    {"ts": cell[0],
                     "channel": cell[1],
                     "direction": cell[2],
                     "source_id": self.id,
                     "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS
                    }
                )
            self._tsch_schedule_activeCell()

    def _tsch_removeCells(self, neighbor, tsList):
        """ removes cell(s) from the schedule """

        with self.dataLock:
            for cell in tsList:
                assert type(cell) == int
                # log
                self._log(
                    d.INFO,
                    "[tsch] remove cell=({0}) with {1}",
                    (cell, neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS),
                )
                self.engine.log(SimEngine.SimLog.LOG_TSCH_REMOVE_CELL,
                                {"ts": cell[0],
                                 "channel": cell[1],
                                 "direction": cell[2],
                                 "source_id": self.id,
                                 "neighbor_id": neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS})

                assert cell in self.schedule.keys()
                assert self.schedule[cell]['neighbor'] == neighbor
                self.schedule.pop(cell)

            self._tsch_schedule_activeCell()

    def _tsch_action_synchronize(self):

        if not self.isSync:
            channel = random.randint(0, self.settings.phy_numChans-1)
            # start listening
            self.propagation.startRx(
                mote=self,
                channel=channel,
            )
            # indicate that we're waiting for the RX operation to finish
            self.waitingFor = d.DIR_RX

            self._tsch_schedule_synchronize()

    def _tsch_schedule_synchronize(self):
        asn = self.engine.getAsn()

        self.engine.scheduleAtAsn(
            asn=asn + 1,
            cb=self._tsch_action_synchronize,
            uniqueTag=(self.id, '_tsch_action_synchronize'),
            priority=3,
        )

    def _tsch_add_minimal_cell(self):
        # add minimal cell
        self._tsch_addCells(self._myNeighbors(), [(0, 0, d.DIR_TXRX_SHARED)])

    #===== radio

    def _radio_drop_packet(self, pkt, reason):
        # remove all the element of pkt so that it won't be processed further
        for k in pkt.keys():
            del pkt[k]

        # increment mote stat
        self._stats_incrementMoteStats(reason)

    def radio_isSync(self):
        with self.dataLock:
            return self.isSync

    def radio_txDone(self, isACKed, isNACKed):
        """end of tx slot"""

        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        with self.dataLock:

            assert ts in self.schedule
            assert self.schedule[ts]['dir'] == d.DIR_TX or self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED
            assert self.waitingFor == d.DIR_TX

            # for debug
            ch = self.schedule[ts]['ch']
            rx = self.schedule[ts]['neighbor']
            canbeInterfered = 0
            for mote in self.engine.motes:
                if mote == self:
                    continue
                if ts in mote.schedule and ch == mote.schedule[ts]['ch'] and mote.schedule[ts]['dir'] == d.DIR_TX:
                    if mote.getRSSI(rx) > rx.minRssi:
                        canbeInterfered = 1
            self.schedule[ts]['debug_canbeInterfered'] += [canbeInterfered]

            if isACKed:
                # ACK received
                self._logChargeConsumed(d.CHARGE_TxDataRxAck_uC)

                # update schedule stats
                self.schedule[ts]['numTxAck'] += 1

                # update history
                self.schedule[ts]['history'] += [1]

                # update queue stats
                self._stats_logQueueDelay(asn-self.pktToSend['asn'])

                # time correction
                if self.schedule[ts]['neighbor'] == self.rpl.getPreferredParent():
                    self.timeCorrectedSlot = asn

                # received an ACK for the request, change state and increase the sequence number
                if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                    if self.pktToSend['code'] == d.IANA_6TOP_CMD_ADD:
                        assert self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDRESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (
                                    float(self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self.sixp.timer_fired,
                            uniqueTag=(self.id, uniqueTag),
                            priority=5,
                        )
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.id, uniqueTag)
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                        self._log(
                            d.DEBUG,
                            "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}",
                            (self.id, self.pktToSend['dstIp'].id, fireASN, str((self.id, uniqueTag))),
                        )
                    elif self.pktToSend['code'] == d.IANA_6TOP_CMD_DELETE:
                        assert self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETERESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (float(self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self.sixp.timer_fired,
                            uniqueTag=(self.id, uniqueTag),
                            priority=5,
                        )
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.id, uniqueTag)
                        self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                        self._log(
                            d.DEBUG,
                            "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}",
                            (self.id, self.pktToSend['dstIp'].id, fireASN, str((self.id, uniqueTag))),
                        )
                    else:
                        assert False

                # save it in a tmp variable
                # because it is possible that self.schedule[ts] does not exist anymore after receiving an ACK for a DELETE RESPONSE
                tmpNeighbor = self.schedule[ts]['neighbor']
                tmpDir = self.schedule[ts]['dir']

                if self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE: # received an ACK for the response, handle the schedule
                    self.sixp.receive_RESPONSE_ACK(self.pktToSend)

                # remove packet from queue
                self.txQueue.remove(self.pktToSend)
                # reset backoff in case of shared slot or in case of a tx slot when the queue is empty
                if tmpDir == d.DIR_TXRX_SHARED or (tmpDir == d.DIR_TX and not self.txQueue):
                    if tmpDir == d.DIR_TXRX_SHARED and tmpNeighbor != self._myNeighbors():
                        self._tsch_resetBackoffPerNeigh(tmpNeighbor)
                    else:
                        self._tsch_resetBroadcastBackoff()

            elif isNACKed:
                # NACK received
                self._logChargeConsumed(d.CHARGE_TxDataRxAck_uC)

                # update schedule stats as if it were successfully transmitted
                self.schedule[ts]['numTxAck'] += 1

                # update history
                self.schedule[ts]['history'] += [1]

                # time correction
                if self.schedule[ts]['neighbor'] == self.rpl.getPreferredParent():
                    self.timeCorrectedSlot = asn

                # decrement 'retriesLeft' counter associated with that packet
                i = self.txQueue.index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:

                    if len(self.txQueue) == d.TSCH_QUEUE_SIZE:

                        # only count drops of DATA packets that are part of the experiment
                        if self.pktToSend['type'] == d.APP_TYPE_DATA:
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_DATA_MAX_RETRIES['type'])

                        # update mote stats
                        self._stats_incrementMoteStats(SimEngine.SimLog.LOG_TSCH_DROP_MAX_RETRIES['type'])

                        # remove packet from queue
                        self.txQueue.remove(self.pktToSend)

                        # reset state for this neighbor
                        # go back to IDLE, i.e. remove the neighbor form the states
                        # but, in the case of a response msg, if the node received another, already new request, from the same node (because its timer fired), do not go to IDLE
                        if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:
                            # update mote stats
                            self._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.txQueue.remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []

                # reset backoff in case of shared slot or in case of a tx slot when the queue is empty
                if self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED or (self.schedule[ts]['dir'] == d.DIR_TX and not self.txQueue):
                    if self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED and self.schedule[ts]['neighbor'] != self._myNeighbors():
                        self._tsch_resetBackoffPerNeigh(self.schedule[ts]['neighbor'])
                    else:
                        self._tsch_resetBroadcastBackoff()
            elif self.pktToSend['dstIp'] == d.BROADCAST_ADDRESS:
                # broadcast packet is not acked, remove from queue and update stats
                self._logChargeConsumed(d.CHARGE_TxData_uC)
                self.txQueue.remove(self.pktToSend)
                self._tsch_resetBroadcastBackoff()

            else:
                # neither ACK nor NACK received
                self._logChargeConsumed(d.CHARGE_TxDataRxAck_uC)

                # increment backoffExponent and get new backoff value
                if self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED:
                    if self.schedule[ts]['neighbor'] == self._myNeighbors():
                        if self.backoffBroadcastExponent < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffBroadcastExponent += 1
                        self.backoffBroadcast = random.randint(0, 2 ** self.backoffBroadcastExponent - 1)
                    else:
                        if self.backoffExponentPerNeigh[self.schedule[ts]['neighbor']] < d.TSCH_MAX_BACKOFF_EXPONENT:
                            self.backoffExponentPerNeigh[self.schedule[ts]['neighbor']] += 1
                        self.backoffPerNeigh[self.schedule[ts]['neighbor']] = random.randint(0, 2 ** self.backoffExponentPerNeigh[self.schedule[ts]['neighbor']] - 1)

                # update history
                self.schedule[ts]['history'] += [0]

                # decrement 'retriesLeft' counter associated with that packet
                i = self.txQueue.index(self.pktToSend)
                if self.txQueue[i]['retriesLeft'] > 0:
                    self.txQueue[i]['retriesLeft'] -= 1

                # drop packet if retried too many time
                if self.txQueue[i]['retriesLeft'] == 0:

                    if  len(self.txQueue) == d.TSCH_QUEUE_SIZE:

                        # counts drops of DATA packets
                        if self.pktToSend['type'] == d.APP_TYPE_DATA:
                            self._stats_incrementMoteStats('droppedDataMacRetries')

                        # update mote stats
                        self._stats_incrementMoteStats('droppedMacRetries')

                        # remove packet from queue
                        self.txQueue.remove(self.pktToSend)

                        # reset state for this neighbor
                        # go back to IDLE, i.e. remove the neighbor form the states
                        if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:

                            # update mote stats
                            self._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.txQueue.remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.sixp.getSixtopStates()[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
            # end of radio activity, not waiting for anything
            self.waitingFor = None

    def radio_rxDone(self, type=None, code=None, smac=None, dmac=None, srcIp=None, dstIp=None, srcRoute=None, payload=None):
        """end of RX radio activity"""

        asn   = self.engine.getAsn()
        ts    = asn % self.settings.tsch_slotframeLength

        with self.dataLock:
            if self.isSync:
                assert ts in self.schedule
                assert self.schedule[ts]['dir'] == d.DIR_RX or self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED
                assert self.waitingFor == d.DIR_RX

            if smac and self in dmac:  # layer 2 addressing
                # I received a packet

                if self.isSync:
                    self.sf.signal_cell_used(self, self.schedule[ts]['neighbor'], self.schedule[ts]['dir'], d.DIR_RX, type)

                if [self] == dmac:  # unicast packet
                    self._logChargeConsumed(d.CHARGE_RxDataTxAck_uC)
                else:  # broadcast
                    self._logChargeConsumed(d.CHARGE_RxData_uC)

                if self.isSync:
                    # update schedule stats
                    self.schedule[ts]['numRx'] += 1

                if type == d.APP_TYPE_FRAG:
                    frag = {
                        'type':        type,
                        'code':        code,
                        'retriesLeft': d.TSCH_MAXTXRETRIES,
                        'smac':        smac,
                        'srcIp':       srcIp,
                        'dstIp':       dstIp,
                        'payload':     copy.deepcopy(payload),
                        'sourceRoute': copy.deepcopy(srcRoute)
                    }
                    self.waitingFor = None
                    if self.settings.frag_ff_enable:
                        if self.app.frag_ff_forward_fragment(frag) is True:
                            if self._tsch_enqueue(frag):
                                # ACK when succeeded to enqueue
                                return True, False
                            else:
                                # ACK anyway
                                self._radio_drop_packet(frag, SimEngine.SimLog.LOG_TSCH_DROP_FRAG_FAIL_ENQUEUE['type'])
                                return True, False
                        elif dstIp == self:
                            if self.app.frag_reassemble_packet(smac, payload) is True:
                                del payload['datagram_size']
                                del payload['datagram_offset']
                                del payload['datagram_tag']
                                type = d.APP_TYPE_DATA
                            else:
                                # not fully reassembled yet
                                return True, False
                        else:
                            # frag is out-of-order; ACK anyway since it's received successfully
                            return True, False
                    else:
                        if self.app.frag_reassemble_packet(smac, payload) is True:
                            # remove fragment information from the payload
                            del payload['datagram_size']
                            del payload['datagram_offset']
                            del payload['datagram_tag']
                            type = d.APP_TYPE_DATA
                        else:
                            # ACK here
                            return True, False

                if dstIp == d.BROADCAST_ADDRESS:
                    if type == d.RPL_TYPE_DIO:
                        # got a DIO
                        self.rpl.action_receiveDIO(type, smac, payload)

                        (isACKed, isNACKed) = (False, False)

                        self.waitingFor = None

                        return isACKed, isNACKed
                    elif type == d.TSCH_TYPE_EB:
                        self._tsch_action_receiveEB(type, smac, payload)

                        (isACKed, isNACKed) = (False, False)

                        self.waitingFor = None

                        return isACKed, isNACKed
                elif dstIp == self:
                    # receiving packet
                    if type == d.RPL_TYPE_DAO:
                        self.rpl.action_receiveDAO(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_ADD:  # received an 6P ADD request
                        self.sixp.receive_ADD_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_DELETE:  # received an 6P DELETE request
                        self.sixp.receive_DELETE_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_RESPONSE:  # received an 6P response
                        if self.sixp.receive_RESPONSE(type, code, smac, payload):
                            (isACKed, isNACKed) = (True, False)
                        else:
                            (isACKed, isNACKed) = (False, False)
                    elif type == d.APP_TYPE_DATA:  # application packet
                        self.app._action_dagroot_receivePacketFromMote(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_ACK:
                        self.app.action_mote_receiveE2EAck(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_JOIN:
                        self.secjoin.receiveJoinPacket(srcIp=srcIp, payload=payload, timestamp=asn)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.APP_TYPE_FRAG:
                        # never comes here; but just in case
                        (isACKed, isNACKed) = (True, False)
                    else:
                        assert False
                elif type == d.APP_TYPE_FRAG:
                    # do nothing for fragmented packet; just ack
                    (isACKed, isNACKed) = (True, False)
                else:
                    # relaying packet

                    if type == d.APP_TYPE_DATA:
                        # update the number of hops
                        newPayload     = copy.deepcopy(payload)
                        newPayload['hops'] += 1
                    else:
                        # copy the payload and forward
                        newPayload     = copy.deepcopy(payload)

                    # create packet
                    relayPacket = {
                        'asn':         asn,
                        'type':        type,
                        'code':        code,
                        'payload':     newPayload,
                        'retriesLeft': d.TSCH_MAXTXRETRIES,
                        'srcIp':       srcIp,
                        'dstIp':       dstIp,
                        'sourceRoute': srcRoute,
                    }

                    # enqueue packet in TSCH queue
                    if type == d.APP_TYPE_DATA and self.settings.frag_numFragments > 1:
                        self.app.fragment_and_enqueue_packet(relayPacket)
                        # we return ack since we've received the last fragment successfully
                        (isACKed, isNACKed) = (True, False)
                    else:
                        isEnqueued = self._tsch_enqueue(relayPacket)
                        if isEnqueued:

                            # update mote stats
                            self._stats_incrementMoteStats(SimEngine.SimLog.LOG_APP_RELAYED['type'])

                            (isACKed, isNACKed) = (True, False)

                        else:
                            self._radio_drop_packet(relayPacket,
                                                    SimEngine.SimLog.LOG_TSCH_DROP_RELAY_FAIL_ENQUEUE['type'])
                            (isACKed, isNACKed) = (False, True)

            else:
                # this was an idle listen

                # log charge usage
                if self.isSync:
                    self._logChargeConsumed(d.CHARGE_Idle_uC)
                else:
                    self._logChargeConsumed(d.CHARGE_IdleNotSync_uC)

                (isACKed, isNACKed) = (False, False)

            self.waitingFor = None

            return isACKed, isNACKed

    #===== wireless

    def getCellPDR(self, cell):
        """ returns the pdr of the cell """

        assert cell['neighbor'] is not type(list)

        with self.dataLock:
            if cell['numTx'] < d.NUM_SUFFICIENT_TX:
                return self.getPDR(cell['neighbor'])
            else:
                return float(cell['numTxAck']) / float(cell['numTx'])

    def setPDR(self, neighbor, pdr):
        """ sets the pdr to that neighbor"""
        with self.dataLock:
            self.PDR[neighbor] = pdr

    def getPDR(self, neighbor):
        """ returns the pdr to that neighbor"""
        with self.dataLock:
            return self.PDR[neighbor]

    def setRSSI(self, neighbor, rssi):
        """ sets the RSSI to that neighbor"""
        with self.dataLock:
            self.RSSI[neighbor.id] = rssi

    def getRSSI(self, neighbor):
        """ returns the RSSI to that neighbor"""
        with self.dataLock:
            return self.RSSI[neighbor.id]

    def _myNeighbors(self):
        return [n for n in self.PDR.keys() if self.PDR[n] > 0]

    #===== clock

    def clock_getOffsetToDagRoot(self):
        """
        calculate time offset compared to the DAGroot
        """

        if self.dagRoot:
            return 0.0

        asn                  = self.engine.getAsn()
        offset               = 0.0
        child                = self
        parent               = self.rpl.getPreferredParent()

        if child.timeCorrectedSlot:
            while True:
                secSinceSync     = (asn-child.timeCorrectedSlot)*self.settings.tsch_slotDuration  # sec
                # FIXME: for ppm, should we not /10^6?
                relDrift         = child.drift - parent.drift                                # ppm
                offset          += relDrift * secSinceSync                                   # us
                if parent.dagRoot:
                    break
                else:
                    child        = parent
                    parent       = child.rpl.getPreferredParent()

        return offset

    #===== location

    def setLocation(self, x, y):
        with self.dataLock:
            self.x = x
            self.y = y

    def getLocation(self):
        with self.dataLock:
            return self.x, self.y

    #==== battery

    def boot(self):
        if self.settings.secjoin_enabled:
            if self.dagRoot:
                self._tsch_add_minimal_cell()
                self._stack_init_synced()  # initialize the stack and start sending beacons and DIOs
            else:
                self._tsch_schedule_synchronize()  # permanent rx until node hears an enhanced beacon to sync
        else:
            self.isSync      = True         # without join we skip the always-on listening for EBs
            self.secjoin.setIsJoined(True)    # we consider all nodes have joined
            self._tsch_add_minimal_cell()
            self._stack_init_synced()

    def _logChargeConsumed(self, charge):
        with self.dataLock:
            self.chargeConsumed  += charge
            self.engine.log(SimEngine.SimLog.LOG_CHARGE_CONSUMED,
                            {"mote_id": self.id, "charge": charge})

    #======================== private =========================================

    #===== getters

    def getTxCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TX]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_TX and c['neighbor'] == neighbor]

    def getRxCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_RX]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_RX and c['neighbor'] == neighbor]

    def getSharedCells(self, neighbor = None):
        with self.dataLock:
            if neighbor is None:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if c['dir'] == d.DIR_TXRX_SHARED]
            else:
                return [(ts, c['ch'], c['neighbor']) for (ts, c) in self.schedule.items() if
                        c['dir'] == d.DIR_TXRX_SHARED and c['neighbor'] == neighbor]

    #===== stats

    # mote state

    def getMoteStats(self):

        # gather statistics
        with self.dataLock:
            dataPktQueues = 0
            for p in self.txQueue:
                if p['type'] == d.APP_TYPE_DATA:
                    dataPktQueues += 1

            returnVal = copy.deepcopy(self.motestats)
            returnVal['numTxCells']         = len(self.getTxCells())
            returnVal['numRxCells']         = len(self.getRxCells())
            returnVal['numDedicatedCells']  = len([(ts, c) for (ts, c) in self.schedule.items() if type(self) == type(c['neighbor'])])
            returnVal['numSharedCells']     = len(self.getSharedCells())
            returnVal['aveQueueDelay']      = self._stats_getAveQueueDelay()
            returnVal['aveLatency']         = self._stats_getAveLatency()
            returnVal['aveHops']            = self._stats_getAveHops()
            returnVal['probableCollisions'] = self._stats_getRadioStats('probableCollisions')
            returnVal['txQueueFill']        = len(self.txQueue)
            returnVal['chargeConsumed']     = self.chargeConsumed
            returnVal['numTx']              = sum([cell['numTx'] for (_, cell) in self.schedule.items()])
            returnVal['dataQueueFill']      = dataPktQueues
            returnVal['aveSixtopLatency']   = self._stats_getAveSixTopLatency()

        # reset the statistics
        self._stats_resetMoteStats()
        self._stats_resetQueueStats()
        self._stats_resetLatencyStats()
        self._stats_resetHopsStats()
        self._stats_resetRadioStats()
        self._stats_resetSixTopLatencyStats()

        return returnVal

    def _stats_resetMoteStats(self):
        with self.dataLock:
            self.motestats = {}

    def _stats_incrementMoteStats(self, name):
        """
        :param str name:
        :return:
        """
        with self.dataLock:
            if name in self.motestats:  # increment stat
                self.motestats[name] += 1
            else:
                self.motestats[name] = 1  # init stat

    # cell stats

    def getCellStats(self, ts_p, ch_p):
        """ retrieves cell stats """

        returnVal = None
        with self.dataLock:
            for (ts, cell) in self.schedule.items():
                if ts == ts_p and cell['ch'] == ch_p:
                    returnVal = {
                        'dir':            cell['dir'],
                        'neighbor':       [node.id for node in cell['neighbor']] if type(cell['neighbor']) is list else cell['neighbor'].id,
                        'numTx':          cell['numTx'],
                        'numTxAck':       cell['numTxAck'],
                        'numRx':          cell['numRx'],
                    }
                    break
        return returnVal

    def stats_sharedCellCollisionSignal(self):
        asn = self.engine.getAsn()
        ts = asn % self.settings.tsch_slotframeLength

        assert self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED

        with self.dataLock:
            self.schedule[ts]['sharedCellCollision'] = 1

    def stats_sharedCellSuccessSignal(self):
        asn = self.engine.getAsn()
        ts = asn % self.settings.tsch_slotframeLength

        assert self.schedule[ts]['dir'] == d.DIR_TXRX_SHARED

        with self.dataLock:
            self.schedule[ts]['sharedCellSuccess'] = 1

    def getSharedCellStats(self):
        returnVal = {}
        # gather statistics
        with self.dataLock:
            for (ts, cell) in self.schedule.items():
                if cell['dir'] == d.DIR_TXRX_SHARED:

                    returnVal['sharedCellCollision_{0}_{1}'.format(ts, cell['ch'])] = cell['sharedCellCollision']
                    returnVal['sharedCellSuccess_{0}_{1}'.format(ts, cell['ch'])] = cell['sharedCellSuccess']

                    # reset the statistics
                    cell['sharedCellCollision'] = 0
                    cell['sharedCellSuccess']   = 0

        return returnVal

    # queue stats

    def _stats_logQueueDelay(self, delay):
        with self.dataLock:
            self.queuestats['delay'] += [delay]
        self.engine.log(SimEngine.SimLog.LOG_QUEUE_DELAY, {"delay": delay})

    def _stats_getAveQueueDelay(self):
        d = self.queuestats['delay']
        return float(sum(d))/len(d) if len(d) > 0 else 0

    def _stats_resetQueueStats(self):
        with self.dataLock:
            self.queuestats = {
                'delay':               [],
            }

    # latency stats

    def _stats_logLatencyStat(self, latency):
        with self.dataLock:
            self.packetLatencies += [latency]

    def _stats_logSixTopLatencyStat(self, latency):
        with self.dataLock:
            l = self.sixp.getavgsixtopLatency()
            l += [latency]

    def _stats_getAveLatency(self):
        with self.dataLock:
            d = self.packetLatencies
            return float(sum(d))/float(len(d)) if len(d) > 0 else 0

    def _stats_getAveSixTopLatency(self):
        with self.dataLock:

            d = self.sixp.getavgsixtopLatency()
            return float(sum(d))/float(len(d)) if len(d) > 0 else 0

    def _stats_resetLatencyStats(self):
        with self.dataLock:
            self.packetLatencies = []

    def _stats_resetSixTopLatencyStats(self):
        with self.dataLock:
            l = self.sixp.getavgsixtopLatency()
            l = []

    # hops stats

    def _stats_logHopsStat(self, hops):
        with self.dataLock:
            self.packetHops += [hops]

    def _stats_getAveHops(self):
        with self.dataLock:
            d = self.packetHops
            return float(sum(d))/float(len(d)) if len(d) > 0 else 0

    def _stats_resetHopsStats(self):
        with self.dataLock:
            self.packetHops = []

    # radio stats

    def stats_incrementRadioStats(self, name):
        with self.dataLock:
            self.radiostats[name] += 1

    def _stats_getRadioStats(self, name):
        return self.radiostats[name]

    def _stats_resetRadioStats(self):
        with self.dataLock:
            self.radiostats = {
                'probableCollisions':      0,  # number of packets that can collide with another packets
            }

    #===== log

    def _log(self, severity, template, params=()):

        if   severity == d.DEBUG:
            if not log.isEnabledFor(logging.DEBUG):
                return
            logfunc = log.debug
        elif severity == d.INFO:
            if not log.isEnabledFor(logging.INFO):
                return
            logfunc = log.info
        elif severity == d.WARNING:
            if not log.isEnabledFor(logging.WARNING):
                return
            logfunc = log.warning
        elif severity == d.ERROR:
            if not log.isEnabledFor(logging.ERROR):
                return
            logfunc = log.error
        else:
            raise NotImplementedError()

        output  = []
        output += ['[ASN={0:>6} id={1:>4}] '.format(self.engine.getAsn(), self.id)]
        output += [template.format(*params)]
        output  = ''.join(output)
        logfunc(output)
