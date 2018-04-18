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
import secjoin
import app
import sf
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
        # stats
        self.firstBeaconAsn            = 0
        
        # singletons (to access quicker than recreate every time)
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()
        self.propagation               = SimEngine.Propagation.Propagation()
        
        # stack
        # app
        self.app                       = app.App(self)
        # frag
        # rpl
        self.rank                      = None
        self.dagRank                   = None
        self.parentSet                 = []
        self.parents                   = {}      # dictionary containing parents of each node from whom DAG root received a DAO
        self.oldPreferredParent        = None    # preserve old preferred parent upon a change
        self.preferredParent           = None
        self.rplRxDIO                  = {}      # indexed by neighbor, contains int
        self.neighborRank              = {}      # indexed by neighbor
        self.neighborDagRank           = {}      # indexed by neighbor
        self.dagRootAddress            = None
        self.packetLatencies           = []      # in slots
        self.packetHops                = []
        # sf
        self.sf                        = sf.SchedulingFunction.get_sf(self.settings.sf_type)
        # 6P
        # 6top protocol
        # a dictionary that stores the different 6p states for each neighbor
        # in each entry the key is the neighbor.id
        # the values are:
        #                 'state', used for tracking the transaction state for each neighbor
        #                 'responseCode', used in the receiver node to act differently when a responseACK is received
        #                 'blockedCells', candidates cell pending for an operation
        self.sixtopStates              = {}
        self.tsSixTopReqRecv           = {}      # for every neighbor, it tracks the 6top transaction latency
        self.avgsixtopLatency          = []      # it tracks the average 6P transaction latency in a given frame
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
        self._stats_resetMoteStats()
        self._stats_resetQueueStats()
        self._stats_resetLatencyStats()
        self._stats_resetHopsStats()
        self._stats_resetRadioStats()
    
    # ======================= stack ===========================================

    # ===== role

    def role_setDagRoot(self):
        self.dagRoot              = True
        self.rank                 = 0
        self.dagRank              = 0
        self.parents              = {}
        self.packetLatencies      = []  # in slots
        self.packetHops           = []
        self.parents              = {}  # dictionary containing parents of each node from whom DAG root received a DAO
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
        self._rpl_init()

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
    
    #===== rpl
    
    # init
    
    def _rpl_init(self):
        '''
        Initialize the RPL layer
        '''
        
        # all nodes send DIOs
        self._rpl_schedule_sendDIO()
        
        # only non-root nodes send DAOs
        if not self.dagRoot:
            self._rpl_schedule_sendDAO(firstDAO=True)
    
    # DIO
    
    def _rpl_schedule_sendDIO(self):
        '''
        Send a DIO sometimes in the future.
        '''
        
        # stop if DIOs disabled
        if self.settings.rpl_dioPeriod==0:
            return

        with self.dataLock:

            asnNow    = self.engine.getAsn()

            if self.settings.tsch_probBcast_enabled:
                asnDiff = int(self.settings.tsch_slotframeLength)
            else:
                asnDiff = int(math.ceil(
                    random.uniform(
                        0.8 * self.settings.rpl_dioPeriod,
                        1.2 * self.settings.rpl_dioPeriod
                    ) / self.settings.tsch_slotDuration)
                )

            # schedule at start of next cycle
            self.engine.scheduleAtAsn(
                asn         = asnNow + asnDiff,
                cb          = self._rpl_action_sendDIO,
                uniqueTag   = (self.id, '_rpl_action_sendDIO'),
                priority    = 3,
            )

    def _rpl_action_sendDIO(self):
        '''
        decide whether to enqueue a DIO, enqueue DIO, schedule next DIO.
        '''
        
        with self.dataLock:
            
            # decide whether to enqueue a DIO
            if self.settings.tsch_probBcast_enabled:
                dioProb = float(self.settings.tsch_probBcast_dioProb) / float(len(self.secjoin.areAllNeighborsJoined())) if len(self.secjoin.areAllNeighborsJoined()) else float(self.settings.tsch_probBcast_dioProb)
                sendDio = True if random.random() < dioProb else False
            else:
                sendDio = True
            
            # enqueue DIO
            if sendDio:
                self._rpl_action_enqueueDIO()
            
            # schedule next DIO
            self._rpl_schedule_sendDIO()  

    def _rpl_action_enqueueDIO(self):
        '''
        enqueue DIO in TSCH queue
        '''

        # only send DIOs if I'm a DAGroot, or I have a preferred parent and dedicated cells to it
        if self.dagRoot or (self.preferredParent and self.numCellsToNeighbors.get(self.preferredParent, 0) != 0):

            self._stats_incrementMoteStats('rplTxDIO')

            # create new packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.RPL_TYPE_DIO,
                'code':           None,
                'payload':        [self.rank], # the payload is the rpl rank
                'retriesLeft':    1,           # do not retransmit (broadcast)
                'srcIp':          self,
                'dstIp':          d.BROADCAST_ADDRESS,
                'sourceRoute':    []
            }

            # enqueue packet in TSCH queue
            if not self._tsch_enqueue(newPacket):
                self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')

    def _rpl_action_receiveDIO(self, type, smac, payload):

        with self.dataLock:
            
            # DAGroot doesn't use DIOs
            if self.dagRoot:
                return
            
            # non sync'ed mote don't use DIO
            if not self.isSync:
                return
            
            # log
            self._log(
                d.INFO,
                "[rpl] Received DIO from mote {0}",
                (smac.id,)
            )

            # update my mote stats
            self._stats_incrementMoteStats('rplRxDIO')

            sender = smac

            rank = payload[0]

            # don't update poor link
            if self._rpl_calcRankIncrease(sender) > d.RPL_MAX_RANK_INCREASE:
                return

            # update rank/DAGrank with sender
            self.neighborDagRank[sender]    = rank / d.RPL_MIN_HOP_RANK_INCREASE
            self.neighborRank[sender]       = rank

            # update number of DIOs received from sender
            if sender not in self.rplRxDIO:
                self.rplRxDIO[sender]       = 0
            self.rplRxDIO[sender]          += 1

            # trigger RPL housekeeping
            self._rpl_housekeeping()

            # update time correction
            if self.preferredParent == sender:
                asn                         = self.engine.getAsn()
                self.timeCorrectedSlot      = asn

    # DAO
    
    def _rpl_schedule_sendDAO(self, firstDAO=False):
        '''
        Schedule to send a DAO sometimes in the future.
        '''
        
        # abort if DAO disabled
        if self.settings.rpl_daoPeriod==0:
            return

        with self.dataLock:
            
            asnNow = self.engine.getAsn()

            if firstDAO:
                asnDiff = 1
            else:
                asnDiff = int(math.ceil(
                    random.uniform(
                        0.8 * self.settings.rpl_daoPeriod,
                        1.2 * self.settings.rpl_daoPeriod
                    ) / self.settings.tsch_slotDuration)
                )
            
            # schedule sending a DAO
            self.engine.scheduleAtAsn(
                asn          = asnNow + asnDiff,
                cb           = self._rpl_action_sendDAO,
                uniqueTag    = (self.id, '_rpl_action_sendDAO'),
                priority     = 3,
            )
    
    def _rpl_action_sendDAO(self):
        '''
        Enqueue a DAO and schedule next one.
        '''
        with self.dataLock:
            
            # enqueue
            self._rpl_action_enqueueDAO()
            
            # schedule next DAO
            self._rpl_schedule_sendDAO()
    
    def _rpl_action_enqueueDAO(self):
        '''
        enqueue a DAO into TSCH queue
        '''
        
        assert not self.dagRoot

        # only send DAOs if I have a preferred parent to which I have dedicated cells
        if self.preferredParent and self.numCellsToNeighbors.get(self.preferredParent, 0) != 0:

            self._stats_incrementMoteStats('rplTxDAO')

            # create new packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.RPL_TYPE_DAO,
                'code':           None,
                'payload':        [
                    self.id,
                    self.preferredParent.id,
                ],
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self,
                'dstIp':          self.dagRootAddress,
                'sourceRoute':    [],
            }

            # enqueue packet in TSCH queue
            if not self._tsch_enqueue(newPacket):
                self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')

    def _rpl_action_receiveDAO(self, type, smac, payload):
        '''
        DAGroot receives DAO, store parent/child relationship for source route calculation.
        '''
        
        assert self.dagRoot
        
        with self.dataLock:
            
            # increment stats
            self._stats_incrementMoteStats('rplRxDAO')
            
            # store parent/child relationship for source route calculation
            self.parents.update({tuple([payload[0]]): [[payload[1]]]})
    
    # source route
    
    def _rpl_getSourceRoute(self, destAddr):
        '''
        Compute the source route to a given mote.

        :param destAddr: [in] The EUI64 address of the final destination.

        :returns: The source route, a list of EUI64 address, ordered from
            destination to source.
        '''

        sourceRoute = []
        with self.dataLock:
            parents = self.parents
            self._rpl_getSourceRoute_internal(destAddr, sourceRoute, parents)

        if sourceRoute:
            sourceRoute.pop()

        return sourceRoute

    def _rpl_getSourceRoute_internal(self, destAddr, sourceRoute, parents):
        
        # abort if no more parents
        if not destAddr:
            return
        
        # abort if I don't have a list of parents
        if not parents.get(tuple(destAddr)):
            return

        # first time add destination address
        if destAddr not in sourceRoute:
            sourceRoute += [destAddr]

        # pick a parent
        parent = parents.get(tuple(destAddr))[0]

        # avoid loops
        if parent not in sourceRoute:
            sourceRoute += [parent]

            # add non empty parents recursively
            nextparent = self._rpl_getSourceRoute_internal(parent, sourceRoute, parents)

            if nextparent:
                sourceRoute += [nextparent]
    
    # misc
    
    def _rpl_housekeeping(self):
        '''
        RPL housekeeping tasks.
        
        This routine refreshes
        - self.preferredParent
        - self.rank
        - self.dagRank
        - self.parentSet
        '''
        with self.dataLock:

            # calculate my potential rank with each of the motes I have heard a DIO from
            potentialRanks = {}
            for (neighbor, neighborRank) in self.neighborRank.items():
                # calculate the rank increase to that neighbor
                rankIncrease = self._rpl_calcRankIncrease(neighbor)
                if rankIncrease is not None and rankIncrease <= min([d.RPL_MAX_RANK_INCREASE, d.RPL_MAX_TOTAL_RANK-neighborRank]):
                    # record this potential rank
                    potentialRanks[neighbor] = neighborRank+rankIncrease

            # sort potential ranks
            sorted_potentialRanks = sorted(potentialRanks.iteritems(), key=lambda x: x[1])

            # switch parents only when rank difference is large enough
            for i in range(1, len(sorted_potentialRanks)):
                if sorted_potentialRanks[i][0] in self.parentSet:
                    # compare the selected current parent with motes who have lower potential ranks
                    # and who are not in the current parent set
                    for j in range(i):
                        if sorted_potentialRanks[j][0] not in self.parentSet:
                            if sorted_potentialRanks[i][1]-sorted_potentialRanks[j][1] < d.RPL_PARENT_SWITCH_THRESHOLD:
                                mote_rank = sorted_potentialRanks.pop(i)
                                sorted_potentialRanks.insert(j, mote_rank)
                                break

            # pick my preferred parent and resulting rank
            if sorted_potentialRanks:
                oldParentSet = set([parent.id for parent in self.parentSet])

                (newPreferredParent, newrank) = sorted_potentialRanks[0]

                # compare a current preferred parent with new one
                if self.preferredParent and newPreferredParent != self.preferredParent:
                    for (mote, rank) in sorted_potentialRanks[:d.RPL_PARENT_SET_SIZE]:
                        if mote == self.preferredParent:
                            # switch preferred parent only when rank difference is large enough
                            if rank-newrank < d.RPL_PARENT_SWITCH_THRESHOLD:
                                (newPreferredParent, newrank) = (mote, rank)

                # update mote stats
                if self.rank and newrank!=self.rank:
                    self._stats_incrementMoteStats('rplChurnRank')
                    # log
                    self._log(
                        d.INFO,
                        "[rpl] churn: rank {0}->{1}",
                        (self.rank, newrank),
                    )
                if (self.preferredParent is None) and (newPreferredParent is not None):
                    if not self.settings.secjoin_enabled:
                        # if we selected a parent for the first time, add one cell to it
                        # upon successful join, the reservation request is scheduled explicitly
                        self.sf.schedule_parent_change(self)
                elif self.preferredParent != newPreferredParent:
                    # update mote stats
                    self._stats_incrementMoteStats('rplChurnPrefParent')

                    # log
                    self._log(
                        d.INFO,
                        "[rpl] churn: preferredParent {0}->{1}",
                        (self.preferredParent.id, newPreferredParent.id),
                    )
                    # trigger 6P add to the new parent
                    self.oldPreferredParent = self.preferredParent
                    self.sf.schedule_parent_change(self)

                # store new preferred parent and rank
                (self.preferredParent, self.rank) = (newPreferredParent, newrank)

                # calculate my DAGrank
                self.dagRank = int(self.rank/d.RPL_MIN_HOP_RANK_INCREASE)

                # pick my parent set
                self.parentSet = [n for (n, _) in sorted_potentialRanks if self.neighborRank[n] < self.rank][:d.RPL_PARENT_SET_SIZE]
                assert self.preferredParent in self.parentSet

                if oldParentSet != set([parent.id for parent in self.parentSet]):
                    self._stats_incrementMoteStats('rplChurnParentSet')

    def _rpl_calcRankIncrease(self, neighbor):
        '''
        calculate the RPL rank increase with a particular neighbor.
        '''
        
        with self.dataLock:

            # estimate the ETX to that neighbor
            etx = self._estimateETX(neighbor)

            # return if that failed
            if not etx:
                return

            # per draft-ietf-6tisch-minimal, rank increase is (3*ETX-2)*d.RPL_MIN_HOP_RANK_INCREASE
            return int(((3*etx) - 2)*d.RPL_MIN_HOP_RANK_INCREASE)

    def _rpl_findNextHop(self, packet):
        '''
        Determines the next hop and writes that in the packet's 'nextHop' field.
        '''
        
        assert self != packet['dstIp']
        
        # abort if no preferred parent, or root
        if not (self.preferredParent or self.dagRoot):
            return False

        nextHop = None

        if   packet['dstIp'] == d.BROADCAST_ADDRESS:
            nextHop = self._myNeighbors()
        elif packet['type'] == d.IANA_6TOP_TYPE_REQUEST or packet['type'] == d.IANA_6TOP_TYPE_RESPONSE:
            # 6P packet: send directly to neighbor
            nextHop = [packet['dstIp']]
        elif packet['dstIp'] == self.dagRootAddress:
            # upstream packet: send to preferred parent
            nextHop = [self.preferredParent]
        elif packet['sourceRoute']:
            # dowstream packet: next hop read from source route
            nextHopId = packet['sourceRoute'].pop()
            for nei in self._myNeighbors():
                if [nei.id] == nextHopId:
                    nextHop = [nei]
        elif packet['dstIp'] in self._myNeighbors():
            nextHop = [packet['dstIp']]

        packet['nextHop'] = nextHop
        return True if nextHop else False

    #===== 6top
    
    # ADD
    
    def sixtop_ADD_REQUEST(self, neighbor, numCells, dir, timeout):
        '''
        Receives a request to add a cell from the SF.
        '''
        
        with self.dataLock:
            if self.settings.sixtop_messaging:
                
                if neighbor.id not in self.sixtopStates or (
                        neighbor.id in self.sixtopStates and 'tx' in self.sixtopStates[neighbor.id] and
                        self.sixtopStates[neighbor.id]['tx']['state'] == d.SIX_STATE_IDLE):

                    # if neighbor not yet in states dict, add it
                    if neighbor.id not in self.sixtopStates:
                        self.sixtopStates[neighbor.id] = {}
                    if 'tx' not in self.sixtopStates[neighbor.id]:
                        self.sixtopStates[neighbor.id]['tx'] = {}
                        self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                        self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                        self.sixtopStates[neighbor.id]['tx']['seqNum'] = 0
                        self.sixtopStates[neighbor.id]['tx']['timeout'] = timeout

                    # get blocked cells from other 6top operations
                    blockedCells = []
                    for n in self.sixtopStates.keys():
                        if n != neighbor.id:
                            if 'tx' in self.sixtopStates[n] and len(self.sixtopStates[n]['tx']['blockedCells']) > 0:
                                blockedCells += self.sixtopStates[n]['tx']['blockedCells']
                            if 'rx' in self.sixtopStates[n] and len(self.sixtopStates[n]['rx']['blockedCells']) > 0:
                                blockedCells += self.sixtopStates[n]['rx']['blockedCells']

                    # convert blocked cells into ts
                    tsBlocked = []
                    if len(blockedCells) > 0:
                        for c in blockedCells:
                            tsBlocked.append(c[0])

                    # randomly picking cells
                    availableTimeslots = list(
                        set(range(self.settings.tsch_slotframeLength)) - set(self.schedule.keys()) - set(tsBlocked))
                    random.shuffle(availableTimeslots)
                    cells = dict([(ts, random.randint(0, self.settings.phy_numChans - 1)) for ts in
                                  availableTimeslots[:numCells * self.sf.MIN_NUM_CELLS]])
                    cellList = [(ts, ch, dir) for (ts, ch) in cells.iteritems()]

                    self._sixtop_enqueue_ADD_REQUEST(neighbor, cellList, numCells, dir,
                                                     self.sixtopStates[neighbor.id]['tx']['seqNum'])
                else:
                    self._log(
                        d.DEBUG,
                        "[6top] can not send 6top ADD request to {0} because timer still did not fire on mote {1}.",
                        (neighbor.id, self.id),
                    )

            else:
                cells = neighbor._sixtop_cell_reservation_response(self, numCells, dir)

                cellList = []
                for (ts, ch) in cells.iteritems():
                    # log
                    self._log(
                        d.INFO,
                        '[6top] add TX cell ts={0},ch={1} from {2} to {3}',
                        (ts, ch, self.id, neighbor.id),
                    )
                    cellList += [(ts, ch, dir)]
                self._tsch_addCells(neighbor, cellList)

                # update counters
                if dir == d.DIR_TX:
                    if neighbor not in self.numCellsToNeighbors:
                        self.numCellsToNeighbors[neighbor] = 0
                    self.numCellsToNeighbors[neighbor] += len(cells)
                elif dir == d.DIR_RX:
                    if neighbor not in self.numCellsFromNeighbors:
                        self.numCellsFromNeighbors[neighbor] = 0
                    self.numCellsFromNeighbors[neighbor] += len(cells)
                else:
                    if neighbor not in self.numCellsFromNeighbors:
                        self.numCellsFromNeighbors[neighbor] = 0
                    self.numCellsFromNeighbors[neighbor] += len(cells)
                    if neighbor not in self.numCellsToNeighbors:
                        self.numCellsToNeighbors[neighbor] = 0
                    self.numCellsToNeighbors[neighbor] += len(cells)

                if len(cells) != numCells:
                    # log
                    self._log(
                        d.ERROR,
                        '[6top] scheduled {0} cells out of {1} required between motes {2} and {3}. cells={4}',
                        (len(cells), numCells, self.id, neighbor.id, cells),
                    )
    
    def _sixtop_enqueue_ADD_REQUEST(self, neighbor, cellList, numCells, dir, seq):
        """ enqueue a new 6P ADD request """

        self._log(
            d.INFO,
            '[6top] enqueueing a new 6P ADD message (seqNum = {0}) cellList={1}, numCells={2} from {3} to {4}',
            (seq, cellList, numCells, self.id, neighbor.id),
        )

        # create new packet
        newPacket = {
            'asn': self.engine.getAsn(),
            'type': d.IANA_6TOP_TYPE_REQUEST,
            'code': d.IANA_6TOP_CMD_ADD,
            'payload': [cellList, numCells, dir, seq, self.engine.getAsn()],
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': self,
            'dstIp': neighbor,  # currently upstream
            'sourceRoute': [],
        }

        # enqueue packet in TSCH queue
        isEnqueued = self._tsch_enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')
        else:
            # set state to sending request for this neighbor
            self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_SENDING_REQUEST
            self.sixtopStates[neighbor.id]['tx']['blockedCells'] = cellList

    def _sixtop_receive_ADD_REQUEST(self, type, smac, payload):
        with self.dataLock:
            neighbor         = smac
            cellList         = payload[0]
            numCells         = payload[1]
            dirNeighbor      = payload[2]
            seq              = payload[3]

            # has the asn of when the req packet was enqueued in the neighbor
            self.tsSixTopReqRecv[neighbor] = payload[4]
            self._stats_incrementMoteStats('6topRxAddReq')

            if smac.id in self.sixtopStates and 'rx' in self.sixtopStates[smac.id] and \
               self.sixtopStates[smac.id]['rx']['state'] != d.SIX_STATE_IDLE:
                for pkt in self.txQueue:
                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and pkt['dstIp'].id == smac.id:
                        self.txQueue.remove(pkt)
                        self._log(
                            d.INFO,
                            "[6top] removed a 6TOP_TYPE_RESPONSE packet (seqNum = {0}) in the queue of mote {1} to neighbor {2}, because a new TYPE_REQUEST (add, seqNum = {3}) was received.",
                            (pkt['payload'][3], self.id, smac.id, seq),
                        )
                returnCode = d.IANA_6TOP_RC_RESET  # error, neighbor has to abort transaction
                if smac.id not in self.sixtopStates:
                    self.sixtopStates[smac.id] = {}
                if 'rx' not in self.sixtopStates[smac.id]:
                    self.sixtopStates[smac.id]['rx'] = {}
                    self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                    self.sixtopStates[smac.id]['rx']['seqNum'] = 0
                self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_ADD_RECEIVED
                self._sixtop_enqueue_RESPONSE(neighbor, [], returnCode, dirNeighbor, seq)
                return

            # go to the correct state
            # set state to receiving request for this neighbor
            if smac.id not in self.sixtopStates:
                self.sixtopStates[smac.id] = {}
            if 'rx' not in self.sixtopStates[smac.id]:
                self.sixtopStates[smac.id]['rx'] = {}
                self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                self.sixtopStates[smac.id]['rx']['seqNum'] = 0

            self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_ADD_RECEIVED

            # set direction of cells
            if dirNeighbor == d.DIR_TX:
                newDir = d.DIR_RX
            elif dirNeighbor == d.DIR_RX:
                newDir = d.DIR_TX
            else:
                newDir = d.DIR_TXRX_SHARED

            # cells that will be in the response
            newCellList = []

            # get blocked cells from other 6top operations
            blockedCells = []
            for n in self.sixtopStates.keys():
                if n != neighbor.id:
                    if 'rx' in self.sixtopStates[n] and len(self.sixtopStates[n]['rx']['blockedCells']) > 0:
                        blockedCells += self.sixtopStates[n]['rx']['blockedCells']
                    if 'tx' in self.sixtopStates[n] and len(self.sixtopStates[n]['tx']['blockedCells']) > 0:
                        blockedCells += self.sixtopStates[n]['tx']['blockedCells']
            # convert blocked cells into ts
            tsBlocked = []
            if len(blockedCells) > 0:
                for c in blockedCells:
                    tsBlocked.append(c[0])

            # available timeslots on this mote
            availableTimeslots = list(
                set(range(self.settings.tsch_slotframeLength)) - set(self.schedule.keys()) - set(tsBlocked))
            random.shuffle(cellList)
            for (ts, ch, dir) in cellList:
                if len(newCellList) == numCells:
                    break
                if ts in availableTimeslots:
                    newCellList += [(ts, ch, newDir)]

            #  if len(newCellList) < numCells it is considered still a success as long as len(newCellList) is bigger than 0
            if len(newCellList) <= 0:
                returnCode = d.IANA_6TOP_RC_NORES  # not enough resources
            else:
                returnCode = d.IANA_6TOP_RC_SUCCESS  # enough resources

            # set blockCells for this 6top operation
            self.sixtopStates[neighbor.id]['rx']['blockedCells'] = newCellList

            # enqueue response
            self._sixtop_enqueue_RESPONSE(neighbor, newCellList, returnCode, newDir, seq)
    
    # DELETE
    
    def sixtop_DELETE_REQUEST(self, neighbor, numCellsToRemove, dir, timeout):
        """
        Finds cells to neighbor, and remove it.
        """

        # get cells to the neighbors
        scheduleList = []

        # worst cell removing initialized by theoretical pdr
        for (ts, cell) in self.schedule.iteritems():
            if (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TX) or (
                    cell['dir'] == d.DIR_TXRX_SHARED and cell['neighbor'] == neighbor):
                cellPDR = self.getCellPDR(cell)
                scheduleList += [(ts, cell['numTxAck'], cell['numTx'], cellPDR)]

        if self.settings.sixtop_removeRandomCell:
            # introduce randomness in the cell list order
            random.shuffle(scheduleList)
        else:
            # triggered only when worst cell selection is due
            # (cell list is sorted according to worst cell selection)
            scheduleListByPDR = {}
            for tscell in scheduleList:
                if not tscell[3] in scheduleListByPDR:
                    scheduleListByPDR[tscell[3]] = []
                scheduleListByPDR[tscell[3]] += [tscell]
            rssi = self.getRSSI(neighbor)
            theoPDR = Topology.Topology.rssiToPdr(rssi)
            scheduleList = []
            for pdr in sorted(scheduleListByPDR.keys()):
                if pdr < theoPDR:
                    scheduleList += sorted(scheduleListByPDR[pdr], key=lambda x: x[2], reverse=True)
                else:
                    scheduleList += sorted(scheduleListByPDR[pdr], key=lambda x: x[2])

        # remove a given number of cells from the list of available cells (picks the first numCellToRemove)
        tsList = []
        for tscell in scheduleList[:numCellsToRemove]:
            # log
            self._log(
                d.INFO,
                "[6top] remove cell ts={0} to {1} (pdr={2:.3f})",
                (tscell[0], neighbor.id, tscell[3]),
            )
            tsList += [tscell[0]]

        assert len(tsList) == numCellsToRemove

        # remove cells
        self._sixtop_cell_deletion_sender(neighbor, tsList, dir, timeout)

    def _sixtop_enqueue_DELETE_REQUEST(self, neighbor, cellList, numCells, dir, seq):
        """ enqueue a new 6P DELETE request """

        self._log(
            d.INFO,
            '[6top] enqueueing a new 6P DEL message cellList={0}, numCells={1} from {2} to {3}',
            (cellList, numCells, self.id, neighbor.id),
        )

        # create new packet
        newPacket = {
            'asn': self.engine.getAsn(),
            'type': d.IANA_6TOP_TYPE_REQUEST,
            'code': d.IANA_6TOP_CMD_DELETE,
            'payload': [cellList, numCells, dir, seq, self.engine.getAsn()],
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': self,
            'dstIp': neighbor,  # currently upstream
            'sourceRoute': [],
        }

        # enqueue packet in TSCH queue
        isEnqueued = self._tsch_enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')
        else:
            # set state to sending request for this neighbor
            self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_SENDING_REQUEST

    def _sixtop_receive_DELETE_REQUEST(self, type, smac, payload):
        """ receive a 6P delete request message """
        with self.dataLock:

            neighbor = smac
            cellList = payload[0]
            numCells = payload[1]
            receivedDir = payload[2]
            seq = payload[3]

            self._stats_incrementMoteStats('6topRxDelReq')
            # has the asn of when the req packet was enqueued in the neighbor. Used for calculate avg 6top latency
            self.tsSixTopReqRecv[neighbor] = payload[4]

            if smac.id in self.sixtopStates and 'rx' in self.sixtopStates[smac.id] and \
               self.sixtopStates[smac.id]['rx']['state'] != d.SIX_STATE_IDLE:
                for pkt in self.txQueue:
                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and pkt['dstIp'].id == smac.id:
                        self.txQueue.remove(pkt)
                        self._log(
                            d.INFO,
                            "[6top] removed a 6TOP_TYPE_RESPONSE packet in the queue of mote {0} to neighbor {1}, because a new TYPE_REQUEST (delete) was received.",
                            (self.id, smac.id),
                        )
                returnCode = d.IANA_6TOP_RC_RESET  # error, neighbor has to abort transaction
                if smac.id not in self.sixtopStates:
                    self.sixtopStates[smac.id] = {}
                if 'rx' not in self.sixtopStates:
                    self.sixtopStates[smac.id]['rx'] = {}
                    self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                    self.sixtopStates[smac.id]['rx']['seqNum'] = 0
                self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_DELETE_RECEIVED
                self._sixtop_enqueue_RESPONSE(neighbor, [], returnCode, receivedDir, seq)
                return

            # set state to receiving request for this neighbor
            if smac.id not in self.sixtopStates:
                self.sixtopStates[smac.id] = {}
            if 'rx' not in self.sixtopStates[neighbor.id]:
                self.sixtopStates[smac.id]['rx'] = {}
                self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                self.sixtopStates[smac.id]['rx']['seqNum'] = 0
                # if neighbor is not in sixtopstates and receives a delete, something has gone wrong. Send a RESET.
                returnCode = d.IANA_6TOP_RC_RESET  # error, neighbor has to abort transaction
                self._sixtop_enqueue_RESPONSE(neighbor, [], returnCode, receivedDir, seq)
                return

            self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_DELETE_RECEIVED

            # set direction of cells
            if receivedDir == d.DIR_TX:
                newDir = d.DIR_RX
            elif receivedDir == d.DIR_RX:
                newDir = d.DIR_TX
            else:
                newDir = d.DIR_TXRX_SHARED

            returnCode = d.IANA_6TOP_RC_SUCCESS  # all is fine

            for cell in cellList:
                if cell not in self.schedule.keys():
                    returnCode = d.IANA_6TOP_RC_NORES  # resources are not present

            # enqueue response
            self._sixtop_enqueue_RESPONSE(neighbor, cellList, returnCode, newDir, seq)
    
    # misc
    
    def _sixtop_timer_fired(self):
        found = False
        for n in self.sixtopStates.keys():
            if 'tx' in self.sixtopStates[n] and 'timer' in self.sixtopStates[n]['tx'] and self.sixtopStates[n]['tx']['timer']['asn'] == self.engine.getAsn(): # if it is this ASN, we have the correct state and we have to abort it
                self.sixtopStates[n]['tx']['state'] = d.SIX_STATE_IDLE # put back to IDLE
                self.sixtopStates[n]['tx']['blockedCells'] = [] # transaction gets aborted, so also delete the blocked cells
                del self.sixtopStates[n]['tx']['timer']
                found = True
                # log
                self._log(
                    d.INFO,
                    "[6top] fired timer on mote {0} for neighbor {1}.",
                    (self.id, n),
                )

        if not found: # if we did not find it, assert
            assert False

    def _sixtop_cell_reservation_response(self, neighbor, numCells, dirNeighbor):
        """ get a response from the neighbor. """

        with self.dataLock:

            # set direction of cells
            if dirNeighbor == d.DIR_TX:
                newDir = d.DIR_RX
            elif dirNeighbor == d.DIR_RX:
                newDir = d.DIR_TX
            else:
                newDir = d.DIR_TXRX_SHARED

            availableTimeslots = list(
                set(range(self.settings.tsch_slotframeLength)) - set(neighbor.schedule.keys()) - set(self.schedule.keys()))
            random.shuffle(availableTimeslots)
            cells = dict([(ts, random.randint(0, self.settings.phy_numChans - 1)) for ts in availableTimeslots[:numCells]])
            cellList = []

            for ts, ch in cells.iteritems():
                # log
                self._log(
                    d.INFO,
                    '[6top] add RX cell ts={0},ch={1} from {2} to {3}',
                    (ts, ch, self.id, neighbor.id),
                )
                cellList += [(ts, ch, newDir)]
            self._tsch_addCells(neighbor, cellList)

            # update counters
            if newDir == d.DIR_TX:
                if neighbor not in self.numCellsToNeighbors:
                    self.numCellsToNeighbors[neighbor] = 0
                self.numCellsToNeighbors[neighbor] += len(cells)
            elif newDir == d.DIR_RX:
                if neighbor not in self.numCellsFromNeighbors:
                    self.numCellsFromNeighbors[neighbor] = 0
                self.numCellsFromNeighbors[neighbor] += len(cells)
            else:
                if neighbor not in self.numCellsFromNeighbors:
                    self.numCellsFromNeighbors[neighbor] = 0
                self.numCellsFromNeighbors[neighbor] += len(cells)
                if neighbor not in self.numCellsToNeighbors:
                    self.numCellsToNeighbors[neighbor] = 0
                self.numCellsToNeighbors[neighbor] += len(cells)

            return cells

    def _sixtop_enqueue_RESPONSE(self, neighbor, cellList, returnCode, dir, seq):
        """ enqueue a new 6P ADD or DELETE response """

        self._log(
            d.INFO,
            '[6top] enqueueing a new 6P RESPONSE message cellList={0}, numCells={1}, returnCode={2}, seqNum={3} from {4} to {5}',
            (cellList, len(cellList), returnCode, seq, self.id, neighbor.id),
        )
        # create new packet
        newPacket = {
            'asn': self.engine.getAsn(),
            'type': d.IANA_6TOP_TYPE_RESPONSE,
            'code': returnCode,
            'payload': [cellList, len(cellList), dir, seq],
            'retriesLeft': d.TSCH_MAXTXRETRIES,
            'srcIp': self,
            'dstIp': neighbor,  # currently upstream
            'sourceRoute': [],
        }

        # enqueue packet in TSCH queue
        isEnqueued = self._tsch_enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')

    def _sixtop_receive_RESPONSE(self, type, code, smac, payload):
        """ receive a 6P response messages """

        with self.dataLock:
            if self.sixtopStates[smac.id]['tx']['state'] == d.SIX_STATE_WAIT_ADDRESPONSE:
                # TODO: now this is still an assert, later this should be handled appropriately
                assert code == d.IANA_6TOP_RC_SUCCESS or code == d.IANA_6TOP_RC_NORES or code == d.IANA_6TOP_RC_RESET  # RC_BUSY not implemented yet

                self._stats_incrementMoteStats('6topRxAddResp')

                neighbor = smac
                receivedCellList = payload[0]
                numCells = payload[1]
                receivedDir = payload[2]
                seq = payload[3]

                # seqNum mismatch, transaction failed, ignore packet
                if seq != self.sixtopStates[neighbor.id]['tx']['seqNum']:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {1} has received a wrong seqNum in a sixtop operation with mote {0}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # transaction is considered as failed since the timeout has already scheduled for this ASN. Too late for removing the event, ignore packet
                if self.sixtopStates[neighbor.id]['tx']['timer']['asn'] == self.engine.getAsn():
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {1} has received a ADD response from mote {0} too late',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # delete the timer.
                uniqueTag = '_sixtop_timer_fired_dest_%s' % neighbor.id
                uniqueTag = (self.id, uniqueTag)
                self.engine.removeEvent(uniqueTag=uniqueTag)

                # remove the pending retransmission event for the scheduling function
                self.engine.removeEvent((self.id, 'action_parent_change_retransmission'))
                self._log(
                    d.INFO,
                    "[6top] removed timer for mote {0} to neighbor {1} on asn {2}, tag {3}",
                    (self.id, neighbor.id, self.sixtopStates[neighbor.id]['tx']['timer']['asn'], str(uniqueTag)),
                )
                del self.sixtopStates[neighbor.id]['tx']['timer']

                self.sixtopStates[smac.id]['tx']['seqNum'] += 1

                # if the request was successfull and there were enough resources
                if code == d.IANA_6TOP_RC_SUCCESS:
                    cellList = []

                    # set direction of cells
                    if receivedDir == d.DIR_TX:
                        newDir = d.DIR_RX
                    elif receivedDir == d.DIR_RX:
                        newDir = d.DIR_TX
                    else:
                        newDir = d.DIR_TXRX_SHARED

                    for (ts, ch, cellDir) in receivedCellList:
                        # log
                        self._log(
                            d.INFO,
                            '[6top] add {4} cell ts={0},ch={1} from {2} to {3}',
                            (ts, ch, self.id, neighbor.id, newDir),
                        )
                        cellList += [(ts, ch, newDir)]
                    self._tsch_addCells(neighbor, cellList)

                    # update counters
                    if newDir == d.DIR_TX:
                        if neighbor not in self.numCellsToNeighbors:
                            self.numCellsToNeighbors[neighbor] = 0
                        self.numCellsToNeighbors[neighbor] += len(receivedCellList)
                    elif newDir == d.DIR_RX:
                        if neighbor not in self.numCellsFromNeighbors:
                            self.numCellsFromNeighbors[neighbor] = 0
                        self.numCellsFromNeighbors[neighbor] += len(receivedCellList)
                    else:
                        if neighbor not in self.numCellsToNeighbors:
                            self.numCellsToNeighbors[neighbor] = 0
                        self.numCellsToNeighbors[neighbor] += len(receivedCellList)
                        if neighbor not in self.numCellsFromNeighbors:
                            self.numCellsFromNeighbors[neighbor] = 0
                        self.numCellsFromNeighbors[neighbor] += len(receivedCellList)

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                elif code == d.IANA_6TOP_RC_NORES:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {0} do not have available resources to allocate for node {0}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_NORES
                # only when devices are not powerfull enough. Not used in the simulator
                elif code == d.IANA_6TOP_RC_BUSY:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {0} is busy and do not have available resources for perform another 6top add operation with mote {1}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_BUSY
                elif code == d.IANA_6TOP_RC_RESET:  # should not happen
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {0} has detected an state inconsistency in a 6top add operation with mote {1}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_BUSY
                else:
                    assert False

            elif self.sixtopStates[smac.id]['tx']['state'] == d.SIX_STATE_WAIT_DELETERESPONSE:
                # TODO: now this is still an assert, later this should be handled appropriately
                assert code == d.IANA_6TOP_RC_SUCCESS or code == d.IANA_6TOP_RC_NORES or code == d.IANA_6TOP_RC_RESET

                self._stats_incrementMoteStats('6topRxDelResp')

                neighbor = smac
                receivedCellList = payload[0]
                numCells = payload[1]
                receivedDir = payload[2]
                seq = payload[3]

                # seqNum mismatch, transaction failed, ignore packet
                if seq != self.sixtopStates[neighbor.id]['tx']['seqNum']:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {1} has received a wrong seqNum in a sixtop operation with mote {0}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # transaction is considered as failed since the timeout has already scheduled for this ASN. Too late for removing the event, ignore packet
                if self.sixtopStates[neighbor.id]['tx']['timer']['asn'] == self.engine.getAsn():
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {1} has received a DELETE response from mote {0} too late',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # delete the timer.
                uniqueTag = '_sixtop_timer_fired_dest_%s' % neighbor.id
                uniqueTag = (self.id, uniqueTag)
                self.engine.removeEvent(uniqueTag=uniqueTag)
                # remove the pending retransmission event for the scheduling function
                self.engine.removeEvent((self.id, 'action_parent_change_retransmission'))
                self._log(
                    d.INFO,
                    "[6top] removed timer for mote {0} to neighbor {1} on asn {2}, tag {3}",
                    (self.id, neighbor.id, self.sixtopStates[neighbor.id]['tx']['timer']['asn'], str(uniqueTag)),
                )
                del self.sixtopStates[neighbor.id]['tx']['timer']

                self.sixtopStates[smac.id]['tx']['seqNum'] += 1

                # if the request was successfull and there were enough resources
                if code == d.IANA_6TOP_RC_SUCCESS:

                    # set direction of cells
                    if receivedDir == d.DIR_TX:
                        newDir = d.DIR_RX
                    elif receivedDir == d.DIR_RX:
                        newDir = d.DIR_TX
                    else:
                        newDir = d.DIR_TXRX_SHARED

                    for ts in receivedCellList:
                        # log
                        self._log(
                            d.INFO,
                            '[6top] Delete {4} cell ts={0},ch={1} from {2} to {3}',
                            (ts, self.id, self.id, neighbor.id, newDir),
                        )

                    self._tsch_removeCells(neighbor, receivedCellList)

                    self.numCellsFromNeighbors[neighbor] -= len(receivedCellList)
                    assert self.numCellsFromNeighbors[neighbor] >= 0

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                elif code == d.IANA_6TOP_RC_NORES:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The resources requested for delete were not available for {1} in {0}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_NORES
                # only when devices are not powerfull enough. Not used in the simulator
                elif code == d.IANA_6TOP_RC_BUSY:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {0} is busy and has not available resources for perform another 6top deletion operation with mote {1}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_BUSY
                elif code == d.IANA_6TOP_RC_RESET:
                    # log
                    self._log(
                        d.INFO,
                        '[6top] The node {0} has detected an state inconsistency in a 6top deletion operation with mote {1}',
                        (neighbor.id, self.id),
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    # TODO: increase stats of RC_RESET
                    return True
                else:  # should not happen
                    assert False
            else:
                # only ADD and DELETE implemented so far
                # do not do an assert because it can be you come here if a timer expires
                # assert False
                pass

    def _sixtop_receive_RESPONSE_ACK(self, packet):
        with self.dataLock:

            if self.sixtopStates[packet['dstIp'].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:

                confirmedCellList = packet['payload'][0]
                receivedDir = packet['payload'][2]
                neighbor = packet['dstIp']
                code = packet['code']

                self._stats_logSixTopLatencyStat(self.engine.asn - self.tsSixTopReqRecv[neighbor])
                self.tsSixTopReqRecv[neighbor] = 0

                if code == d.IANA_6TOP_RC_SUCCESS:
                    for (ts, ch, cellDir) in confirmedCellList:
                        # log
                        self._log(
                            d.INFO,
                            '[6top] add {4} cell ts={0},ch={1} from {2} to {3}',
                            (ts, ch, self.id, neighbor.id, cellDir),
                        )
                    self._tsch_addCells(neighbor, confirmedCellList)

                    # update counters
                    if receivedDir == d.DIR_TX:
                        if neighbor not in self.numCellsToNeighbors:
                            self.numCellsToNeighbors[neighbor] = 0
                        self.numCellsToNeighbors[neighbor] += len(confirmedCellList)
                    elif receivedDir == d.DIR_RX:
                        if neighbor not in self.numCellsFromNeighbors:
                            self.numCellsFromNeighbors[neighbor] = 0
                        self.numCellsFromNeighbors[neighbor] += len(confirmedCellList)
                    else:
                        if neighbor not in self.numCellsToNeighbors:
                            self.numCellsToNeighbors[neighbor] = 0
                        self.numCellsToNeighbors[neighbor] += len(confirmedCellList)
                        if neighbor not in self.numCellsFromNeighbors:
                            self.numCellsFromNeighbors[neighbor] = 0
                        self.numCellsFromNeighbors[neighbor] += len(confirmedCellList)

                # go back to IDLE, i.e. remove the neighbor form the states
                # but if the node received another, already new request, from the same node (because its timer fired), do not go to IDLE
                self.sixtopStates[neighbor.id]['rx']['state'] = d.SIX_STATE_IDLE
                self.sixtopStates[neighbor.id]['rx']['blockedCells'] = []
                self.sixtopStates[neighbor.id]['rx']['seqNum'] += 1

            elif self.sixtopStates[packet['dstIp'].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:

                confirmedCellList = packet['payload'][0]
                receivedDir = packet['payload'][2]
                neighbor = packet['dstIp']
                code = packet['code']

                self._stats_logSixTopLatencyStat(self.engine.asn - self.tsSixTopReqRecv[neighbor])
                self.tsSixTopReqRecv[neighbor] = 0

                if code == d.IANA_6TOP_RC_SUCCESS:
                    for ts in confirmedCellList:
                        # log
                        self._log(
                            d.INFO,
                            '[6top] delete {3} cell ts={0} from {1} to {2}',
                            (ts, self.id, neighbor.id, receivedDir),
                        )
                    self._tsch_removeCells(neighbor, confirmedCellList)

                self.numCellsFromNeighbors[neighbor] -= len(confirmedCellList)
                assert self.numCellsFromNeighbors[neighbor] >= 0

                # go back to IDLE, i.e. remove the neighbor form the states
                self.sixtopStates[neighbor.id]['rx']['state'] = d.SIX_STATE_IDLE
                self.sixtopStates[neighbor.id]['rx']['blockedCells'] = []
                self.sixtopStates[neighbor.id]['rx']['seqNum'] += 1

            else:
                # only add and delete are implemented so far
                assert False

    def _sixtop_cell_deletion_sender(self, neighbor, tsList, dir, timeout):
        with self.dataLock:
            if self.settings.sixtop_messaging:
                if neighbor.id not in self.sixtopStates or (
                        neighbor.id in self.sixtopStates and 'tx' in self.sixtopStates[neighbor.id] and
                        self.sixtopStates[neighbor.id]['tx']['state'] == d.SIX_STATE_IDLE):

                    # if neighbor not yet in states dict, add it
                    if neighbor.id not in self.sixtopStates:
                        self.sixtopStates[neighbor.id] = {}
                    if 'tx' not in self.sixtopStates:
                        self.sixtopStates[neighbor.id]['tx'] = {}
                        self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                        self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                        self.sixtopStates[neighbor.id]['tx']['seqNum'] = 0
                        self.sixtopStates[neighbor.id]['tx']['timeout'] = timeout

                    self._sixtop_enqueue_DELETE_REQUEST(neighbor, tsList, len(tsList), dir,
                                                        self.sixtopStates[neighbor.id]['tx']['seqNum'])
                else:
                    self._log(
                        d.DEBUG,
                        "[6top] can not send 6top DELETE request to {0} because timer still did not fire on mote {1}.",
                        (neighbor.id, self.id),
                    )
            else:
                # log
                self._log(
                    d.INFO,
                    "[6top] remove timeslots={0} with {1}",
                    (tsList, neighbor.id),
                )
                self._tsch_removeCells(
                    neighbor=neighbor,
                    tsList=tsList,
                )

                newDir = d.DIR_RX
                if dir == d.DIR_TX:
                    newDir = d.DIR_RX
                elif dir == d.DIR_RX:
                    newDir = d.DIR_TX
                else:
                    newDir = d.DIR_TXRX_SHARED

                neighbor._sixtop_cell_deletion_receiver(self, tsList, newDir)

                # update counters
                if dir == d.DIR_TX:
                    self.numCellsToNeighbors[neighbor] -= len(tsList)
                elif dir == d.DIR_RX:
                    self.numCellsFromNeighbors[neighbor] -= len(tsList)
                else:
                    self.numCellsToNeighbors[neighbor] -= len(tsList)
                    self.numCellsFromNeighbors[neighbor] -= len(tsList)

                assert self.numCellsToNeighbors[neighbor] >= 0

    def _sixtop_cell_deletion_receiver(self, neighbor, tsList, dir):
        with self.dataLock:
            self._tsch_removeCells(
                neighbor=neighbor,
                tsList=tsList,
            )
            # update counters
            if dir == d.DIR_TX:
                self.numCellsToNeighbors[neighbor] -= len(tsList)
            elif dir == d.DIR_RX:
                self.numCellsFromNeighbors[neighbor] -= len(tsList)
            else:
                self.numCellsToNeighbors[neighbor] -= len(tsList)
                self.numCellsFromNeighbors[neighbor] -= len(tsList)
            assert self.numCellsFromNeighbors[neighbor] >= 0
    
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

        if not self._rpl_findNextHop(packet):
            # I don't have a route

            # increment mote state
            self._stats_incrementMoteStats('droppedNoRoute')

            return False

        elif not (self.getTxCells() or self.getSharedCells()):
            # I don't have any transmit cells

            # increment mote state
            self._stats_incrementMoteStats('droppedNoTxCells')

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
                        self._stats_incrementMoteStats('droppedQueueFull')
                        return False
                self.txQueue    += [packet]
                return True

            # update mote stats
            self._stats_incrementMoteStats('droppedQueueFull')

            return False

        else:
            # all is good

            # enqueue packet
            self.txQueue    += [packet]

            return True

    def _tsch_action_enqueueEB(self):
        """ enqueue EB packet into stack """

        # only start sending EBs if: I am a DAG root OR (I have a preferred parent AND dedicated cells to that parent)
        if self.dagRoot or (self.preferredParent and self.numCellsToNeighbors.get(self.preferredParent, 0) != 0):

            # create new packet
            newPacket = {
                'asn': self.engine.getAsn(),
                'type': d.TSCH_TYPE_EB,
                'code': None,
                'payload': [self.dagRank],  # the payload is the rpl rank
                'retriesLeft': 1,  # do not retransmit broadcast
                'srcIp': self,
                'dstIp': d.BROADCAST_ADDRESS,
                'sourceRoute': []
            }

            # enqueue packet in TSCH queue
            if not self._tsch_enqueue(newPacket):
                # update mote stats
                self._radio_drop_packet(newPacket, 'droppedFailedEnqueue')

    def _tsch_schedule_sendEB(self, firstEB=False):

        if self.settings.tsch_ebPeriod_sec==0:
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
            if self.preferredParent or self.dagRoot:
                if self.secjoin.isJoined() or not self.settings.secjoin_enabled:
                    if sendBeacon:
                        self._tsch_action_enqueueEB()
                        self._stats_incrementMoteStats('tschTxEB')

            self._tsch_schedule_sendEB()  # schedule next EB

    def _tsch_action_receiveEB(self, type, smac, payload):
        
        # abort if I'm the root
        if self.dagRoot:
            return

        # got an EB, increment stats
        self._stats_incrementMoteStats('tschRxEB')
        
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
                            self._stats_incrementMoteStats('6topTxAddReq')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self._stats_incrementMoteStats('6topTxDelReq')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            assert False

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self._stats_incrementMoteStats('6topTxAddResp')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self._stats_incrementMoteStats('6topTxDelResp')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
                            pass
                        else:
                            assert False

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
                            self._stats_incrementMoteStats('6topTxAddReq')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        elif pkt['code'] == d.IANA_6TOP_CMD_DELETE:
                            self._stats_incrementMoteStats('6topTxDelReq')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        else:
                            assert False

                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                        if self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_ADD_RECEIVED:
                            self._stats_incrementMoteStats('6topTxAddResp')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_REQUEST_DELETE_RECEIVED:
                            self._stats_incrementMoteStats('6topTxDelResp')
                            self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] = d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:
                            pass
                        elif self.sixtopStates[self.pktToSend['nextHop'][0].id]['rx']['state'] == d.SIX_STATE_WAIT_DELETE_RESPONSE_SENDDONE:
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
                self._log(
                    d.INFO,
                    "[tsch] add cell ts={0} ch={1} dir={2} with {3}",
                    (cell[0], cell[1], cell[2], neighbor.id if not type(neighbor) == list else d.BROADCAST_ADDRESS),
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
        if reason in self.motestats:
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
                if self.schedule[ts]['neighbor'] == self.preferredParent:
                    self.timeCorrectedSlot = asn

                # received an ACK for the request, change state and increase the sequence number
                if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                    if self.pktToSend['code'] == d.IANA_6TOP_CMD_ADD:
                        assert self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_ADDREQUEST_SENDDONE
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_ADDRESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (
                                    float(self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self._sixtop_timer_fired,
                            uniqueTag=(self.id, uniqueTag),
                            priority=5,
                        )
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.id, uniqueTag)
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
                        self._log(
                            d.DEBUG,
                            "[6top] activated a timer for mote {0} to neighbor {1} on asn {2} with tag {3}",
                            (self.id, self.pktToSend['dstIp'].id, fireASN, str((self.id, uniqueTag))),
                        )
                    elif self.pktToSend['code'] == d.IANA_6TOP_CMD_DELETE:
                        assert self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] == d.SIX_STATE_WAIT_DELETEREQUEST_SENDDONE
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_WAIT_DELETERESPONSE

                        # calculate the asn at which it should fire
                        fireASN = int(self.engine.getAsn() + (float(self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timeout']) / float(self.settings.tsch_slotDuration)))
                        uniqueTag = '_sixtop_timer_fired_dest_%s' % self.pktToSend['dstIp'].id
                        self.engine.scheduleAtAsn(
                            asn=fireASN,
                            cb=self._sixtop_timer_fired,
                            uniqueTag=(self.id, uniqueTag),
                            priority=5,
                        )
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer'] = {}
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer']['tag'] = (self.id, uniqueTag)
                        self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['timer']['asn'] = fireASN
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
                    self._sixtop_receive_RESPONSE_ACK(self.pktToSend)

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
                if self.schedule[ts]['neighbor'] == self.preferredParent:
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
                            self._stats_incrementMoteStats('droppedDataMacRetries')

                        # update mote stats
                        self._stats_incrementMoteStats('droppedMacRetries')

                        # remove packet from queue
                        self.txQueue.remove(self.pktToSend)

                        # reset state for this neighbor
                        # go back to IDLE, i.e. remove the neighbor form the states
                        # but, in the case of a response msg, if the node received another, already new request, from the same node (because its timer fired), do not go to IDLE
                        if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                            self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:
                            # update mote stats
                            self._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.txQueue.remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []

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
                            self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                            self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                        elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                            self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                            self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
                    else:
                        if self.pktToSend['type'] != d.APP_TYPE_DATA:

                            # update mote stats
                            self._stats_incrementMoteStats('droppedMacRetries')

                            # remove packet from queue
                            self.txQueue.remove(self.pktToSend)

                            if self.pktToSend['type'] == d.IANA_6TOP_TYPE_REQUEST:
                                self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['state'] = d.SIX_STATE_IDLE
                                self.sixtopStates[self.pktToSend['dstIp'].id]['tx']['blockedCells'] = []
                            elif self.pktToSend['type'] == d.IANA_6TOP_TYPE_RESPONSE:
                                self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['state'] = d.SIX_STATE_IDLE
                                self.sixtopStates[self.pktToSend['dstIp'].id]['rx']['blockedCells'] = []
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
                                self._radio_drop_packet(frag, 'droppedFragFailedEnqueue')
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
                        self._rpl_action_receiveDIO(type, smac, payload)

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
                        self._rpl_action_receiveDAO(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_ADD:  # received an 6P ADD request
                        self._sixtop_receive_ADD_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_REQUEST and code == d.IANA_6TOP_CMD_DELETE:  # received an 6P DELETE request
                        self._sixtop_receive_DELETE_REQUEST(type, smac, payload)
                        (isACKed, isNACKed) = (True, False)
                    elif type == d.IANA_6TOP_TYPE_RESPONSE:  # received an 6P response
                        if self._sixtop_receive_RESPONSE(type, code, smac, payload):
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
                    if (type == d.APP_TYPE_DATA and self.settings.frag_numFragments > 1):
                        self.app.fragment_and_enqueue_packet(relayPacket)
                        # we return ack since we've received the last fragment successfully
                        (isACKed, isNACKed) = (True, False)
                    else:
                        isEnqueued = self._tsch_enqueue(relayPacket)
                        if isEnqueued:

                            # update mote stats
                            self._stats_incrementMoteStats('appRelayed')

                            (isACKed, isNACKed) = (True, False)

                        else:
                            self._radio_drop_packet(relayPacket, 'droppedRelayFailedEnqueue')
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

    def _estimateETX(self, neighbor):

        with self.dataLock:

            # set initial values for numTx and numTxAck assuming PDR is exactly estimated
            pdr                   = self.getPDR(neighbor)
            numTx                 = d.NUM_SUFFICIENT_TX
            numTxAck              = math.floor(pdr*numTx)

            for (_, cell) in self.schedule.items():
                if (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TX) or (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TXRX_SHARED):
                    numTx        += cell['numTx']
                    numTxAck     += cell['numTxAck']

            # abort if about to divide by 0
            if not numTxAck:
                return

            # calculate ETX
            etx = float(numTx)/float(numTxAck)

            return etx

    def _myNeighbors(self):
        return [n for n in self.PDR.keys() if self.PDR[n] > 0]

    #===== clock

    def clock_getOffsetToDagRoot(self):
        """ calculate time offset compared to the DAGroot """

        if self.dagRoot:
            return 0.0

        asn                  = self.engine.getAsn()
        offset               = 0.0
        child                = self
        parent               = self.preferredParent

        while True:
            secSinceSync     = (asn-child.timeCorrectedSlot)*self.settings.tsch_slotDuration  # sec
            # FIXME: for ppm, should we not /10^6?
            relDrift         = child.drift - parent.drift                                # ppm
            offset          += relDrift * secSinceSync                                   # us
            if parent.dagRoot:
                break
            else:
                child        = parent
                parent       = child.preferredParent

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
            self.motestats = {
                # app
                'appGenerated':               0,   # number of packets app layer generated
                'appRelayed':                 0,   # number of packets relayed
                'appReachesDagroot':          0,   # number of packets received at the DAGroot
                'droppedFailedEnqueue':       0,   # dropped packets because failed enqueue them
                'droppedDataFailedEnqueue':   0,   # dropped DATA packets because app failed enqueue them
                # queue
                'droppedQueueFull':           0,   # dropped packets because queue is full
                # rpl
                'rplTxDIO':                   0,   # number of TX'ed DIOs
                'rplRxDIO':                   0,   # number of RX'ed DIOs
                'rplTxDAO':                   0,   # number of TX'ed DAOs
                'rplRxDAO':                   0,   # number of RX'ed DAOs
                'rplChurnPrefParent':         0,   # number of time the mote changes preferred parent
                'rplChurnRank':               0,   # number of time the mote changes rank
                'rplChurnParentSet':          0,   # number of time the mote changes parent set
                'droppedNoRoute':             0,   # packets dropped because no route (no preferred parent)
                'droppedNoTxCells':           0,   # packets dropped because no TX cells
                # 6top
                '6topTxRelocatedCells':       0,   # number of time tx-triggered 6top relocates a single cell
                '6topTxRelocatedBundles':     0,   # number of time tx-triggered 6top relocates a bundle
                '6topRxRelocatedCells':       0,   # number of time rx-triggered 6top relocates a single cell
                '6topTxAddReq':               0,   # number of 6P Add request transmitted
                '6topTxAddResp':              0,   # number of 6P Add responses transmitted
                '6topTxDelReq':               0,   # number of 6P del request transmitted
                '6topTxDelResp':              0,   # number of 6P del responses transmitted
                '6topRxAddReq':               0,   # number of 6P Add request received
                '6topRxAddResp':              0,   # number of 6P Add responses received
                '6topRxDelReq':               0,   # number of 6P Del request received
                '6topRxDelResp':              0,   # number of 6P Del responses received
                # tsch
                'droppedMacRetries':          0,   # packets dropped because more than d.TSCH_MAXTXRETRIES MAC retries
                'droppedDataMacRetries':      0,   # packets dropped because more than d.TSCH_MAXTXRETRIES MAC retries in a DATA packet
                'tschTxEB':                   0,   # number of TX'ed EBs
                'tschRxEB':                   0,   # number of RX'ed EBs
            }

    def _stats_incrementMoteStats(self, name):
        with self.dataLock:
            self.motestats[name] += 1

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
            self.avgsixtopLatency += [latency]

    def _stats_getAveLatency(self):
        with self.dataLock:
            d = self.packetLatencies
            return float(sum(d))/float(len(d)) if len(d) > 0 else 0

    def _stats_getAveSixTopLatency(self):
        with self.dataLock:

            d = self.avgsixtopLatency
            return float(sum(d))/float(len(d)) if len(d) > 0 else 0

    def _stats_resetLatencyStats(self):
        with self.dataLock:
            self.packetLatencies = []

    def _stats_resetSixTopLatencyStats(self):
        with self.dataLock:
            self.avgsixtopLatency = []

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
