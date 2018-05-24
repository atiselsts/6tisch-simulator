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

    def receive(self, packet):
        self.mote.sf.recvPacket(packet)

    # === ADD

    def issue_ADD_REQUEST(
            self,
            neighborid,
            num_cells=1,
            cell_options=[d.CELLOPTION_TX],
            cell_list=None
        ):

        # new SIXP command, bump the seqnum
        if neighborid not in self.seqnum:
            self.seqnum[neighborid] = 0
        self.seqnum[neighborid] += 1

        # create ADD request
        addRequest = {
            'type':                     d.PKT_TYPE_SIXP_ADD_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          cell_options,
                'NumCells':             num_cells,
                'CellList':             cell_list,
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

    # === DELETE

    def issue_DELETE_REQUEST(self, neighbor_id, num_cells=1, cell_list=None):

        # new SIXP command, bump the seqnum
        if neighbor_id not in self.seqnum:
            self.seqnum[neighbor_id] = 0
        self.seqnum[neighbor_id] += 1

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

    # === RELOCATE

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

