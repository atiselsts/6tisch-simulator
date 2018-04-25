"""
"""

# =========================== imports =========================================

import random
import threading

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SixP(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # admin
        self.dataLock                       = threading.RLock()

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables

        # a dictionary that stores the different 6p states for each neighbor
        # in each entry the key is the neighbor.id
        # the values are:
        # - 'state', used for tracking the transaction state for each neighbor
        # - 'responseCode', used in the receiver node to act differently when a responseACK is received
        # - 'blockedCells', candidates cell pending for an operation
        self.sixtopStates              = {}
        self.tsSixTopReqRecv           = {}      # for every neighbor, it tracks the 6top transaction latency
        self.avgsixtopLatency          = []      # it tracks the average 6P transaction latency in a given frame

    #======================== public ==========================================

    # getters/setters

    def getSixtopStates(self):
        return self.sixtopStates

    def getavgsixtopLatency(self):
        return self.avgsixtopLatency

    # ADD request

    def issue_ADD_REQUEST(self, neighbor, numCells, dir, timeout):
        """
        Receives a request to add a cell from the SF.
        """

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
                        set(range(self.settings.tsch_slotframeLength)) - set(self.mote.tsch.getSchedule().keys()) - set(tsBlocked))
                    random.shuffle(availableTimeslots)
                    cells = dict([(ts, random.randint(0, self.settings.phy_numChans - 1)) for ts in
                                  availableTimeslots[:numCells * self.mote.sf.MIN_NUM_CELLS]])
                    cellList = [(ts, ch, dir) for (ts, ch) in cells.iteritems()]

                    self._enqueue_ADD_REQUEST(neighbor, cellList, numCells, dir,
                                                     self.sixtopStates[neighbor.id]['tx']['seqNum'])
                else:
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": "[6top] can not send 6top ADD request to {0} because timer "
                                    "still did not fire on mote {1}."
                                    .format(neighbor.id, self.mote.id)
                        }
                    )
            else:
                cells = neighbor._cell_reservation_response(self, numCells, dir)

                cellList = []
                for (ts, ch) in cells.iteritems():
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_ADD_CELL,
                        {
                            "ts": ts,
                            "channel": ch,
                            "direction": dir,
                            "mote_id": self.mote.id,
                            "neighbor_id": neighbor.id
                        }
                    )
                    cellList += [(ts, ch, dir)]
                self.mote.tsch.addCells(neighbor, cellList)

                # update counters
                if dir == d.DIR_TX:
                    if neighbor not in self.mote.numCellsToNeighbors:
                        self.mote.numCellsToNeighbors[neighbor] = 0
                    self.mote.numCellsToNeighbors[neighbor] += len(cells)
                elif dir == d.DIR_RX:
                    if neighbor not in self.mote.numCellsFromNeighbors:
                        self.mote.numCellsFromNeighbors[neighbor] = 0
                    self.mote.numCellsFromNeighbors[neighbor] += len(cells)
                else:
                    if neighbor not in self.mote.numCellsFromNeighbors:
                        self.mote.numCellsFromNeighbors[neighbor] = 0
                    self.mote.numCellsFromNeighbors[neighbor] += len(cells)
                    if neighbor not in self.mote.numCellsToNeighbors:
                        self.mote.numCellsToNeighbors[neighbor] = 0
                    self.mote.numCellsToNeighbors[neighbor] += len(cells)

                if len(cells) != numCells:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_ERROR,
                        {
                            'error': '[6top] scheduled {0} cells out of {1} required between motes '
                                     '{2} and {3}. cells={4}'
                                     .format(len(cells),
                                             numCells,
                                             self.mote.id,
                                             neighbor.id,
                                             cells)
                        }
                    )

    def receive_ADD_REQUEST(self, type, smac, payload):
        with self.dataLock:
            neighbor         = smac
            cellList         = payload[0]
            numCells         = payload[1]
            dirNeighbor      = payload[2]
            seq              = payload[3]

            # has the asn of when the req packet was enqueued in the neighbor
            self.tsSixTopReqRecv[neighbor] = payload[4]
            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_RX_ADD_REQ['type'])

            if smac.id in self.sixtopStates and 'rx' in self.sixtopStates[smac.id] and \
               self.sixtopStates[smac.id]['rx']['state'] != d.SIX_STATE_IDLE:
                for pkt in self.mote.tsch.getTxQueue():
                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and pkt['dstIp'].id == smac.id:
                        self.mote.tsch.getTxQueue().remove(pkt)
                        self.log(
                            SimEngine.SimLog.LOG_6TOP_QUEUE_DEL,
                            {
                                'pkt_type': pkt['type'],
                                'neighbor': smac.id
                            }
                        )
                returnCode = d.IANA_6TOP_RC_RESET  # error, neighbor has to abort transaction
                if smac.id not in self.sixtopStates:
                    self.sixtopStates[smac.id] = {}
                if 'rx' not in self.sixtopStates[smac.id]:
                    self.sixtopStates[smac.id]['rx'] = {}
                    self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                    self.sixtopStates[smac.id]['rx']['seqNum'] = 0
                self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_ADD_RECEIVED
                self._enqueue_RESPONSE(neighbor, [], returnCode, dirNeighbor, seq)
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
                set(range(self.settings.tsch_slotframeLength)) - set(self.mote.tsch.getSchedule().keys()) - set(tsBlocked))
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
            self._enqueue_RESPONSE(neighbor, newCellList, returnCode, newDir, seq)

    # DELETE request

    def issue_DELETE_REQUEST(self, neighbor, numCellsToRemove, dir, timeout):
        """
        Finds cells to neighbor, and remove it.
        """

        # get cells to the neighbors
        scheduleList = []

        # worst cell removing initialized by theoretical pdr
        for (ts, cell) in self.mote.tsch.getSchedule().iteritems():
            if (cell['neighbor'] == neighbor and cell['dir'] == d.DIR_TX) or (
                    cell['dir'] == d.DIR_TXRX_SHARED and cell['neighbor'] == neighbor):
                cellPDR = self.mote.getCellPDR(cell)
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
            self.log(
                SimEngine.SimLog.LOG_6TOP_INFO,
                {
                    "info": "[6top] remove cell ts={0} to {1} (pdr={2:.3f})"
                            .format(tscell[0], neighbor.id, tscell[3])
                }
            )
            tsList += [tscell[0]]

        assert len(tsList) == numCellsToRemove

        # remove cells
        self._cell_deletion_sender(neighbor, tsList, dir, timeout)

    def receive_DELETE_REQUEST(self, type, smac, payload):
        """ receive a 6P delete request message """
        with self.dataLock:

            neighbor = smac
            cellList = payload[0]
            numCells = payload[1]
            receivedDir = payload[2]
            seq = payload[3]

            self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_RX_DEL_REQ['type'])
            # has the asn of when the req packet was enqueued in the neighbor. Used for calculate avg 6top latency
            self.tsSixTopReqRecv[neighbor] = payload[4]

            if smac.id in self.sixtopStates and 'rx' in self.sixtopStates[smac.id] and \
               self.sixtopStates[smac.id]['rx']['state'] != d.SIX_STATE_IDLE:
                for pkt in self.mote.tsch.getTxQueue():
                    if pkt['type'] == d.IANA_6TOP_TYPE_RESPONSE and pkt['dstIp'].id == smac.id:
                        self.mote.tsch.getTxQueue().remove(pkt)
                returnCode = d.IANA_6TOP_RC_RESET  # error, neighbor has to abort transaction
                if smac.id not in self.sixtopStates:
                    self.sixtopStates[smac.id] = {}
                if 'rx' not in self.sixtopStates:
                    self.sixtopStates[smac.id]['rx'] = {}
                    self.sixtopStates[smac.id]['rx']['blockedCells'] = []
                    self.sixtopStates[smac.id]['rx']['seqNum'] = 0
                self.sixtopStates[smac.id]['rx']['state'] = d.SIX_STATE_REQUEST_DELETE_RECEIVED
                self._enqueue_RESPONSE(neighbor, [], returnCode, receivedDir, seq)
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
                self._enqueue_RESPONSE(neighbor, [], returnCode, receivedDir, seq)
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
                if cell not in self.mote.tsch.getSchedule().keys():
                    returnCode = d.IANA_6TOP_RC_NORES  # resources are not present

            # enqueue response
            self._enqueue_RESPONSE(neighbor, cellList, returnCode, newDir, seq)

    # response

    def receive_RESPONSE(self, type, code, smac, payload):
        """ receive a 6P response messages """

        self.log(
            SimEngine.SimLog.LOG_6TOP_RX_RESP,
            {
                "mote_id": self.mote.id,
                "rc": code,
                "type": type,
                "neighbor_id": smac.id
            }
        )

        with self.dataLock:
            if self.sixtopStates[smac.id]['tx']['state'] == d.SIX_STATE_WAIT_ADDRESPONSE:
                # TODO: now this is still an assert, later this should be handled appropriately
                assert code == d.IANA_6TOP_RC_SUCCESS or code == d.IANA_6TOP_RC_NORES or code == d.IANA_6TOP_RC_RESET  # RC_BUSY not implemented yet

                self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_ADD_RESP['type'])

                neighbor = smac
                receivedCellList = payload[0]
                numCells = payload[1]
                receivedDir = payload[2]
                seq = payload[3]

                # seqNum mismatch, transaction failed, ignore packet
                if seq != self.sixtopStates[neighbor.id]['tx']['seqNum']:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {'info': '[6top] The node {1} has received a wrong seqNum in a sixtop '
                                 'operation with mote {0}'
                                 .format(neighbor.id, self.mote.id)
                         }
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # transaction is considered as failed since the timeout has already scheduled for this ASN. Too late for removing the event, ignore packet
                if self.sixtopStates[neighbor.id]['tx']['timer']['asn'] == self.engine.getAsn():
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {1} has received a ADD response from mote {0} '
                                    'too late'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # delete the timer.
                uniqueTag = '_sixtop_timer_fired_dest_%s' % neighbor.id
                uniqueTag = (self.mote.id, uniqueTag)
                self.engine.removeEvent(uniqueTag=uniqueTag)

                # remove the pending retransmission event for the scheduling function
                self.engine.removeEvent((self.mote.id, 'action_parent_change_retransmission'))

                # log
                self.log(
                    SimEngine.SimLog.LOG_6TOP_INFO,
                    {
                        'info': "[6top] removed timer for mote {0} to neighbor {1} on asn {2}, tag"
                                " {3}"
                                .format(
                                    self.mote.id,
                                    neighbor.id,
                                    self.sixtopStates[neighbor.id]['tx']['timer']['asn'],
                                    str(uniqueTag)
                                )
                    }
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
                        self.log(
                            SimEngine.SimLog.LOG_6TOP_ADD_CELL,
                            {
                                "ts": ts,
                                "channel": ch,
                                "direction": cellDir,
                                "neighbor_id": neighbor.id,
                                "mote_id": self.mote.id,
                            }
                        )
                        cellList += [(ts, ch, newDir)]
                    self.mote.tsch.addCells(neighbor, cellList)

                    # update counters
                    if newDir == d.DIR_TX:
                        if neighbor not in self.mote.numCellsToNeighbors:
                            self.mote.numCellsToNeighbors[neighbor] = 0
                        self.mote.numCellsToNeighbors[neighbor] += len(receivedCellList)
                    elif newDir == d.DIR_RX:
                        if neighbor not in self.mote.numCellsFromNeighbors:
                            self.mote.numCellsFromNeighbors[neighbor] = 0
                        self.mote.numCellsFromNeighbors[neighbor] += len(receivedCellList)
                    else:
                        if neighbor not in self.mote.numCellsToNeighbors:
                            self.mote.numCellsToNeighbors[neighbor] = 0
                        self.mote.numCellsToNeighbors[neighbor] += len(receivedCellList)
                        if neighbor not in self.mote.numCellsFromNeighbors:
                            self.mote.numCellsFromNeighbors[neighbor] = 0
                        self.mote.numCellsFromNeighbors[neighbor] += len(receivedCellList)

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                elif code == d.IANA_6TOP_RC_NORES:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {0} do not have available resources to '
                                    'allocate for node {0}'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                # only when devices are not powerfull enough. Not used in the simulator
                elif code == d.IANA_6TOP_RC_BUSY:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {0} is busy and do not have available '
                                    'resources for perform another 6top add operation with '
                                    'mote {1}'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )
                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_BUSY
                elif code == d.IANA_6TOP_RC_RESET:  # should not happen
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {0} has detected an state inconsistency in a '
                                    '6top add operation with mote {1}'
                                    .format(neighbor.id, self.mote.id)
                        }
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

                self.mote._stats_incrementMoteStats(SimEngine.SimLog.LOG_6TOP_TX_DEL_RESP['type'])

                neighbor = smac
                receivedCellList = payload[0]
                numCells = payload[1]
                receivedDir = payload[2]
                seq = payload[3]

                # seqNum mismatch, transaction failed, ignore packet
                if seq != self.sixtopStates[neighbor.id]['tx']['seqNum']:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {1} has received a wrong seqNum in a sixtop '
                                    'operation with mote {0}'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # transaction is considered as failed since the timeout has already scheduled for this ASN. Too late for removing the event, ignore packet
                if self.sixtopStates[neighbor.id]['tx']['timer']['asn'] == self.engine.getAsn():
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            'info': '[6top] The node {1} has received a DELETE response from mote '
                                    '{0} too late'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return False

                # delete the timer.
                uniqueTag = '_sixtop_timer_fired_dest_%s' % neighbor.id
                uniqueTag = (self.mote.id, uniqueTag)
                self.engine.removeEvent(uniqueTag=uniqueTag)
                # remove the pending retransmission event for the scheduling function
                self.engine.removeEvent((self.mote.id, 'action_parent_change_retransmission'))

                # log
                self.log(
                    SimEngine.SimLog.LOG_6TOP_INFO,
                    {
                        'info': "[6top] removed timer for mote {0} to neighbor {1} on asn {2}, "
                                "tag {3}"
                                .format(
                                    self.mote.id,
                                    neighbor.id,
                                    self.sixtopStates[neighbor.id]['tx']['timer']['asn'],
                                    str(uniqueTag)
                                )
                    }
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

                    self.mote.tsch.removeCells(neighbor, receivedCellList)

                    self.mote.numCellsFromNeighbors[neighbor] -= len(receivedCellList)
                    assert self.mote.numCellsFromNeighbors[neighbor] >= 0

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                elif code == d.IANA_6TOP_RC_NORES:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": '[6top] The resources requested for delete were not available '
                                    'for {1} in {0}'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_NORES
                # only when devices are not powerfull enough. Not used in the simulator
                elif code == d.IANA_6TOP_RC_BUSY:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": '[6top] The node {0} is busy and has not available resources for perform '
                                    'another 6top deletion operation with mote {1}'
                                    .format(neighbor.id, self.mote.id)
                        }
                    )

                    # go back to IDLE, i.e. remove the neighbor form the states
                    self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_IDLE
                    self.sixtopStates[neighbor.id]['tx']['blockedCells'] = []
                    return True
                    # TODO: increase stats of RC_BUSY
                elif code == d.IANA_6TOP_RC_RESET:
                    # log
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {
                            "info": '[6top] The node {0} has detected an state inconsistency in a '
                                    '6top deletion operation with mote {1}'
                                    .format(neighbor.id, self.mote.id)
                        }
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

    def receive_RESPONSE_ACK(self, packet):
        with self.dataLock:

            if self.sixtopStates[packet['dstIp'].id]['rx']['state'] == d.SIX_STATE_WAIT_ADD_RESPONSE_SENDDONE:

                confirmedCellList = packet['payload'][0]
                receivedDir = packet['payload'][2]
                neighbor = packet['dstIp']
                code = packet['code']

                self.mote._stats_logSixTopLatencyStat(self.engine.asn - self.tsSixTopReqRecv[neighbor])
                self.tsSixTopReqRecv[neighbor] = 0

                if code == d.IANA_6TOP_RC_SUCCESS:
                    for (ts, ch, cellDir) in confirmedCellList:
                        # log
                        self.log(
                            SimEngine.SimLog.LOG_6TOP_RX_ACK,
                            {
                                "source_id": neighbor.id,
                                "destination_id": self.mote.id,
                                "ts": ts,
                                "channel": ch,
                                "direction": cellDir,
                                "rc": code,
                            }
                        )
                    self.mote.tsch.addCells(neighbor, confirmedCellList)

                    # update counters
                    if receivedDir == d.DIR_TX:
                        if neighbor not in self.mote.numCellsToNeighbors:
                            self.mote.numCellsToNeighbors[neighbor] = 0
                        self.mote.numCellsToNeighbors[neighbor] += len(confirmedCellList)
                    elif receivedDir == d.DIR_RX:
                        if neighbor not in self.mote.numCellsFromNeighbors:
                            self.mote.numCellsFromNeighbors[neighbor] = 0
                        self.mote.numCellsFromNeighbors[neighbor] += len(confirmedCellList)
                    else:
                        if neighbor not in self.mote.numCellsToNeighbors:
                            self.mote.numCellsToNeighbors[neighbor] = 0
                        self.mote.numCellsToNeighbors[neighbor] += len(confirmedCellList)
                        if neighbor not in self.mote.numCellsFromNeighbors:
                            self.mote.numCellsFromNeighbors[neighbor] = 0
                        self.mote.numCellsFromNeighbors[neighbor] += len(confirmedCellList)

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

                self.mote._stats_logSixTopLatencyStat(self.engine.asn - self.tsSixTopReqRecv[neighbor])
                self.tsSixTopReqRecv[neighbor] = 0

                if code == d.IANA_6TOP_RC_SUCCESS:
                    for ts in confirmedCellList:
                        # log
                        self.log(
                            SimEngine.SimLog.LOG_6TOP_INFO,
                            {
                                "info": '[6top] delete {3} cell ts={0} from {1} to {2}'
                                        .format(ts, self.mote.id, neighbor.id, receivedDir)
                            }
                        )
                    self.mote.tsch.removeCells(neighbor, confirmedCellList)

                self.mote.numCellsFromNeighbors[neighbor] -= len(confirmedCellList)
                assert self.mote.numCellsFromNeighbors[neighbor] >= 0

                # go back to IDLE, i.e. remove the neighbor form the states
                self.sixtopStates[neighbor.id]['rx']['state'] = d.SIX_STATE_IDLE
                self.sixtopStates[neighbor.id]['rx']['blockedCells'] = []
                self.sixtopStates[neighbor.id]['rx']['seqNum'] += 1

            else:
                # only add and delete are implemented so far
                assert False

    # misc

    def timer_fired(self):
        found = False
        for n in self.sixtopStates.keys():
            if 'tx' in self.sixtopStates[n] and 'timer' in self.sixtopStates[n]['tx'] and self.sixtopStates[n]['tx']['timer']['asn'] == self.engine.getAsn(): # if it is this ASN, we have the correct state and we have to abort it
                self.sixtopStates[n]['tx']['state'] = d.SIX_STATE_IDLE # put back to IDLE
                self.sixtopStates[n]['tx']['blockedCells'] = [] # transaction gets aborted, so also delete the blocked cells
                del self.sixtopStates[n]['tx']['timer']
                found = True
                # log
                self.log(
                    SimEngine.SimLog.LOG_6TOP_INFO,
                    {
                        "info": "[6top] fired timer on mote {0} for neighbor {1}."
                            .format(self.mote.id, n)
                    }
                )

        if not found: # if we did not find it, assert
            assert False

    #======================== private ==========================================

    # ADD request

    def _enqueue_ADD_REQUEST(self, neighbor, cellList, numCells, dir, seq):
        """ enqueue a new 6P ADD request """

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
        isEnqueued = self.mote.tsch.enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])
        else:
            # set state to sending request for this neighbor
            self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_SENDING_REQUEST
            self.sixtopStates[neighbor.id]['tx']['blockedCells'] = cellList

    # DELETE request

    def _enqueue_DELETE_REQUEST(self, neighbor, cellList, numCells, dir, seq):
        """ enqueue a new 6P DELETE request """

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
        isEnqueued = self.mote.tsch.enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])
        else:
            # set state to sending request for this neighbor
            self.sixtopStates[neighbor.id]['tx']['state'] = d.SIX_STATE_SENDING_REQUEST

    # response

    def _enqueue_RESPONSE(self, neighbor, cellList, returnCode, dir, seq):
        """ enqueue a new 6P ADD or DELETE response """

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
        isEnqueued = self.mote.tsch.enqueue(newPacket)

        if not isEnqueued:
            # update mote stats
            self.mote.radio.drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])

    # misc

    def _cell_reservation_response(self, neighbor, numCells, dirNeighbor):
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
                set(range(self.settings.tsch_slotframeLength)) - set(neighbor.tsch.getSchedule().keys()) - set(self.mote.tsch.getSchedule().keys()))
            random.shuffle(availableTimeslots)
            cells = dict([(ts, random.randint(0, self.settings.phy_numChans - 1)) for ts in availableTimeslots[:numCells]])
            cellList = []

            for ts, ch in cells.iteritems():
                cellList += [(ts, ch, newDir)]
            self.mote.tsch.addCells(neighbor, cellList)

            # update counters
            if newDir == d.DIR_TX:
                if neighbor not in self.mote.numCellsToNeighbors:
                    self.mote.numCellsToNeighbors[neighbor] = 0
                self.mote.numCellsToNeighbors[neighbor] += len(cells)
            elif newDir == d.DIR_RX:
                if neighbor not in self.mote.numCellsFromNeighbors:
                    self.mote.numCellsFromNeighbors[neighbor] = 0
                self.mote.numCellsFromNeighbors[neighbor] += len(cells)
            else:
                if neighbor not in self.mote.numCellsFromNeighbors:
                    self.mote.numCellsFromNeighbors[neighbor] = 0
                self.mote.numCellsFromNeighbors[neighbor] += len(cells)
                if neighbor not in self.mote.numCellsToNeighbors:
                    self.mote.numCellsToNeighbors[neighbor] = 0
                self.mote.numCellsToNeighbors[neighbor] += len(cells)

            return cells

    def _cell_deletion_sender(self, neighbor, tsList, dir, timeout):
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

                    self._enqueue_DELETE_REQUEST(neighbor, tsList, len(tsList), dir,
                                                        self.sixtopStates[neighbor.id]['tx']['seqNum'])
                else:
                    self.log(
                        SimEngine.SimLog.LOG_6TOP_INFO,
                        {"info": "[6top] can not send 6top DELETE request to {0} because timer "
                                 "still did not fire on mote {1}."
                                 .format(neighbor.id, self.mote.id)
                         }
                    )
            else:
                self.mote.tsch.removeCells(
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

                neighbor._cell_deletion_receiver(self, tsList, newDir)

                # update counters
                if dir == d.DIR_TX:
                    self.mote.numCellsToNeighbors[neighbor] -= len(tsList)
                elif dir == d.DIR_RX:
                    self.mote.numCellsFromNeighbors[neighbor] -= len(tsList)
                else:
                    self.mote.numCellsToNeighbors[neighbor] -= len(tsList)
                    self.mote.numCellsFromNeighbors[neighbor] -= len(tsList)

                assert self.mote.numCellsToNeighbors[neighbor] >= 0

    def _cell_deletion_receiver(self, neighbor, tsList, dir):
        with self.dataLock:
            self.mote.tsch.removeCells(
                neighbor=neighbor,
                tsList=tsList,
            )
            # update counters
            if dir == d.DIR_TX:
                self.mote.numCellsToNeighbors[neighbor] -= len(tsList)
            elif dir == d.DIR_RX:
                self.mote.numCellsFromNeighbors[neighbor] -= len(tsList)
            else:
                self.mote.numCellsToNeighbors[neighbor] -= len(tsList)
                self.mote.numCellsFromNeighbors[neighbor] -= len(tsList)
            assert self.mote.numCellsFromNeighbors[neighbor] >= 0
