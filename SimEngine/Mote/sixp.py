"""
"""

# =========================== imports =========================================

import random

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

class ScheduleFullError(Exception):
    pass

# =========================== helpers =========================================

# =========================== body ============================================

class SixP(object):

    def __init__(self, mote):

        # store params
        self.mote                 = mote

        # singletons (quicker access, instead of recreating every time)
        self.engine               = SimEngine.SimEngine.SimEngine()
        self.settings             = SimEngine.SimSettings.SimSettings()
        self.log                  = SimEngine.SimLog.SimLog().log

        # local variables
        self.seqnum               = {} # indexed by neighborid

    #======================== public/private ==================================

    # from upper layers

    def receive(self,packet):
        if   packet['type'] == d.PKT_TYPE_SIXP_ADD_REQUEST:
            self._receive_ADD_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_ADD_RESPONSE:
            self._receive_ADD_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_DELETE_REQUEST:
            self._receive_DELETE_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_DELETE_RESPONSE:
            self._receive_DELETE_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_CLEAR_REQUEST:
            self._receive_CLEAR_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_CLEAR_RESPONSE:
            self._receive_CLEAR_RESPONSE(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_RELOCATE_REQUEST:
            self._receive_RELOCATE_REQUEST(packet)
        elif packet['type'] == d.PKT_TYPE_SIXP_RELOCATE_RESPONSE:
            self._receive_RELOCATE_RESPONSE(packet)
        else:
            raise SystemError()

    # === ADD

    def issue_ADD_REQUEST(self, neighborid, num_cells=1, cell_options=[d.CELLOPTION_TX]):

        # new SIXP command, bump the seqnum
        if neighborid not in self.seqnum:
            self.seqnum[neighborid] = 0
        self.seqnum[neighborid] += 1

        # create celllist
        celllist = []
        for _ in range(num_cells):
            slotOffset = 0
            if len(self.mote.tsch.getSchedule()) == self.settings.tsch_slotframeLength:
                raise ScheduleFullError()
            while slotOffset in self.mote.tsch.getSchedule():
                slotOffset = random.randint(1, self.settings.tsch_slotframeLength)
            channelOffset = random.randint(0, self.settings.phy_numChans-1)
            celllist += [
                {
                    'slotOffset':    slotOffset,
                    'channelOffset': channelOffset,
                    'numTx':         0,
                    'numTxAck':      0
                }
            ]

        # create ADD request
        addRequest = {
            'type':                     d.PKT_TYPE_SIXP_ADD_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          cell_options,
                'NumCells':             num_cells,
                'CellList':             celllist,
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               neighborid,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   addRequest,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(addRequest)

    def _receive_ADD_REQUEST(self, addRequest):

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   addRequest,
            }
        )

        # look for cell that works in celllist
        added_slotOffset    = None
        added_channelOffset = None
        for cell in addRequest['app']['CellList']:
            if cell['slotOffset'] not in self.mote.tsch.getSchedule():

                # remember what I added
                added_slotOffset       = cell['slotOffset']
                added_channelOffset    = cell['channelOffset']

                # add to my schedule
                self.mote.tsch.addCell(
                    slotOffset         = cell['slotOffset'],
                    channelOffset      = cell['channelOffset'],
                    neighbor           = addRequest['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_RX],
                )

                break

        # make sure I could use at least one of the cell
        if added_slotOffset is None or added_channelOffset is None:
            code = d.SIXP_RC_ERR
        else:
            code = d.SIXP_RC_SUCCESS

        # create ADD response
        celllist = []
        if added_slotOffset is not None:
            celllist += [
                {
                    'slotOffset':      added_slotOffset,
                    'channelOffset':   added_channelOffset,
                }
            ]
        addResponse = {
            'type':                    d.PKT_TYPE_SIXP_ADD_RESPONSE,
            'app': {
                'Code':                code,
                'SeqNum':              addRequest['app']['SeqNum'],
                'CellList':            celllist,
            },
            'mac': {
                'srcMac':              self.mote.id,
                'dstMac':              addRequest['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_RESPONSE_TX,
            {
                '_mote_id':            self.mote.id,
                'packet':              addResponse,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(addResponse)

    def _receive_ADD_RESPONSE(self, response):
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_RESPONSE_RX,
            {
                '_mote_id':  self.mote.id,
                'packet':    response,
            }
        )

        # add cell from celllist
        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            cell = response['app']['CellList'][0]
            self.mote.tsch.addCell(
                slotOffset         = cell['slotOffset'],
                channelOffset      = cell['channelOffset'],
                neighbor           = response['mac']['srcMac'],
                cellOptions        = [d.CELLOPTION_TX],
            )

    # === DELETE

    def issue_DELETE_REQUEST(self, neighbor_id, num_cells=1):

        # new SIXP command, bump the seqnum
        if neighbor_id not in self.seqnum:
            self.seqnum[neighbor_id] = 0
        self.seqnum[neighbor_id] += 1

        # create celllist
        celllist = []
        for (slotOffset, cell) in self.mote.tsch.getTxCells(neighbor_id).items():
            assert cell['neighbor'] == neighbor_id
            celllist.append(
                {
                    'slotOffset':    slotOffset,
                    'channelOffset': cell['channelOffset'],
                }
            )
        assert celllist

        # create DELETE request
        deleteRequest = {
            'type':                     d.PKT_TYPE_SIXP_DELETE_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighbor_id],
                'CellOptions':          [d.CELLOPTION_TX],
                'NumCells':             num_cells,
                'CellList':             celllist,
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               neighbor_id,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteRequest,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(deleteRequest)

    def _receive_DELETE_REQUEST(self, deleteRequest):

        assert len(deleteRequest['app']['CellList']) > 0

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteRequest,
            }
        )

        # delete a cell taken at random in the celllist
        cell_to_delete = random.choice(deleteRequest['app']['CellList'])
        code = d.SIXP_RC_ERR
        for (slotOffcet, cell) in self.mote.tsch.getRxCells(deleteRequest['mac']['srcMac']).items():
            if (
                    cell_to_delete['slotOffset'] == slotOffcet and
                    cell_to_delete['channelOffset'] == cell['channelOffset'] and
                    deleteRequest['mac']['srcMac'] == cell['neighbor']
            ):
                code = d.SIXP_RC_SUCCESS
                self.mote.tsch.deleteCell(
                    slotOffset         = cell_to_delete['slotOffset'],
                    channelOffset      = cell_to_delete['channelOffset'],
                    neighbor           = deleteRequest['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_RX],
                )

        # create DELETE response
        deleteResponse = {
            'type':                     d.PKT_TYPE_SIXP_DELETE_RESPONSE,
            'app': {
                'Code':                 code,
                'SeqNum':               deleteRequest['app']['SeqNum'],
                'CellList':             [
                    {
                        'slotOffset':   cell_to_delete['slotOffset'],
                        'channelOffset':cell_to_delete['channelOffset'],
                    },
                ],
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               deleteRequest['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteResponse,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(deleteResponse)

    def _receive_DELETE_RESPONSE(self, deleteResponse):

        if deleteResponse['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in deleteResponse['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset         = cell['slotOffset'],
                    channelOffset      = cell['channelOffset'],
                    neighbor           = deleteResponse['mac']['srcMac'],
                    cellOptions        = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteResponse,
            }
        )

    # === CLEAR

    def issue_CLEAR_REQUEST(self, neighbor_id):
        # new SIXP command, bump the seqnum
        if neighbor_id not in self.seqnum:
            self.seqnum[neighbor_id] = 0
        self.seqnum[neighbor_id] += 1

        # create celllist
        cell_list = []
        for (slotOffset, cell) in self.mote.tsch.getTxCells(neighbor_id).items():
            assert cell['neighbor'] == neighbor_id
            cell_list.append(
                {
                    'slotOffset': slotOffset,
                    'channelOffset': cell['channelOffset'],
                }
            )
        assert cell_list

        # create CLEAR request
        clear_request = {
            'type': d.PKT_TYPE_SIXP_CLEAR_REQUEST,
            'app': {
                'SeqNum': self.seqnum[neighbor_id],
                'CellOptions': [d.CELLOPTION_TX],
                'CellList': cell_list,
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': neighbor_id,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet': clear_request,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(clear_request)

    def _receive_CLEAR_REQUEST(self, request):
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet': request,
            }
        )

        # remove all cells with the neighbor
        for cell in request['app']['CellList']:
            self.mote.tsch.deleteCell(
                slotOffset      = cell['slotOffset'],
                channelOffset   = cell['channelOffset'],
                neighbor        = request['mac']['srcMac'],
                cellOptions     = [d.CELLOPTION_RX],
            )

        # create CLEAR response
        response = {
            'type': d.PKT_TYPE_SIXP_CLEAR_RESPONSE,
            'app': {
                'Code': d.SIXP_RC_SUCCESS,
                'SeqNum': request['app']['SeqNum'],
                'CellList': request['app']['CellList'],
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': request['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(response)

    def _receive_CLEAR_RESPONSE(self, response):

        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in response['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset      = cell['slotOffset'],
                    channelOffset   = cell['channelOffset'],
                    neighbor        = response['mac']['srcMac'],
                    cellOptions     = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_CLEAR_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

    # === CLEAR

    def issue_RELOCATE_REQUEST(self, neighbor_id):
        # new SIXP command, bump the seqnum
        if neighbor_id not in self.seqnum:
            self.seqnum[neighbor_id] = 0
        self.seqnum[neighbor_id] += 1

        # create cell list
        cell_list = []
        for (slotOffset, cell) in self.mote.tsch.getTxCells(neighbor_id).items():
            assert cell['neighbor'] == neighbor_id
            cell_list.append(
                {
                    'slotOffset': slotOffset,
                    'channelOffset': cell['channelOffset'],
                }
            )
        assert cell_list

        # create RELOCATE request
        request = {
            'type': d.PKT_TYPE_SIXP_RELOCATE_REQUEST,
            'app': {
                'SeqNum': self.seqnum[neighbor_id],
                'CellOptions': [d.CELLOPTION_TX],
                'CellList': cell_list,
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': neighbor_id,
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet': request,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(request)

    def _receive_RELOCATE_REQUEST(self, request):

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet': request,
            }
        )

        if len(request['app']['CellList']) < 1:
            code = d.SIXP_RC_ERR_CELLLIST
        else:
            code = d.SIXP_RC_SUCCESS
            # remove all cells with the neighbor
            for cell in request['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset=cell['slotOffset'],
                    channelOffset=cell['channelOffset'],
                    neighbor=request['mac']['srcMac'],
                    cellOptions=[d.CELLOPTION_RX],
                )

        # create CLEAR response
        response = {
            'type': d.PKT_TYPE_SIXP_RELOCATE_RESPONSE,
            'app': {
                'Code': code,
                'SeqNum': request['app']['SeqNum'],
                'CellList': request['app']['CellList'],
            },
            'mac': {
                'srcMac': self.mote.id,
                'dstMac': request['mac']['srcMac'],
            },
        }

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )

        # enqueue
        self.mote.tsch.enqueue(response)

    def _receive_RELOCATE_RESPONSE(self, response):

        if response['app']['Code'] == d.SIXP_RC_SUCCESS:
            # delete cell from celllist
            for cell in response['app']['CellList']:
                self.mote.tsch.deleteCell(
                    slotOffset      = cell['slotOffset'],
                    channelOffset   = cell['channelOffset'],
                    neighbor        = response['mac']['srcMac'],
                    cellOptions     = [d.CELLOPTION_TX],
                )

        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_RELOCATE_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet': response,
            }
        )
