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

class ScheduleFullError(Exception):
    pass

# =========================== helpers =========================================

# =========================== body ============================================

class SixP(object):
    
    CELLLIST_LENGTH = 5
    
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
        if   packet['type']==d.PKT_TYPE_SIXP_ADD_REQUEST:
            self._receive_ADD_REQUEST(packet)
        elif packet['type']==d.PKT_TYPE_SIXP_ADD_RESPONSE:
            self._receive_ADD_RESPONSE(packet)
        elif packet['type']==d.PKT_TYPE_SIXP_DELETE_REQUEST:
            self._receive_DELETE_REQUEST(packet)
        elif packet['type']==d.PKT_TYPE_SIXP_DELETE_RESPONSE:
            self._receive_DELETE_RESPONSE(packet)
        else:
            raise SystemError()
    
    # === ADD
    
    def issue_ADD_REQUEST(self, neighborid):
        
        # new SIXP command, bump the seqnum
        if neighborid not in self.seqnum:
            self.seqnum[neighborid] = 0
        self.seqnum[neighborid] += 1
        
        # create celllist
        celllist = []
        for _ in range(self.CELLLIST_LENGTH):
            slotOffset = 0
            if len(self.mote.tsch.getSchedule())==self.settings.tsch_slotframeLength:
                raise ScheduleFullError()
            while slotOffset in self.mote.tsch.getSchedule():
                slotOffset = random.randint(1, self.settings.tsch_slotframeLength)
            channelOffset = random.randint(0, self.settings.phy_numChans-1)
            celllist += [
                {
                    'slotOffset':    slotOffset,
                    'channelOffset': channelOffset,
                }
            ]
        
        # create ADD request
        addRequest = {
            'type':                     d.PKT_TYPE_SIXP_ADD_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          [d.CELLOPTION_TX],
                'NumCells':             1,
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
    
    def _receive_ADD_REQUEST(self,addRequest):
        
        assert addRequest['app']['NumCells']==1
        assert addRequest['app']['CellOptions']==[d.CELLOPTION_TX]
        assert len(addRequest['app']['CellList'])==self.CELLLIST_LENGTH
        
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
        
        # make sure I could use at least one of the cell (FIXME: lift assert and return error code instead)
        assert added_slotOffset!=None
        assert added_channelOffset!=None
        
        # create ADD response
        celllist = []
        if added_slotOffset!=None:
            celllist += [
                {
                    'slotOffset':      added_slotOffset,
                    'channelOffset':   added_channelOffset,
                }
            ]
        addResponse = {
            'type':                    d.PKT_TYPE_SIXP_ADD_RESPONSE,
            'app': {
                'Code':                d.SIXP_RC_SUCCESS,
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
    
    def _receive_ADD_RESPONSE(self,addResponse):
        
        assert len(addResponse['app']['CellList'])==1
        
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_ADD_RESPONSE_RX,
            {
                '_mote_id':  self.mote.id,
                'packet':    addResponse,
            }
        )
        
        # add cell from celllist
        cell = addResponse['app']['CellList'][0]
        self.mote.tsch.addCell(
            slotOffset         = cell['slotOffset'],
            channelOffset      = cell['channelOffset'],
            neighbor           = addResponse['mac']['srcMac'],
            cellOptions        = [d.CELLOPTION_TX],
        )
    
    # === DELETE
    
    def issue_DELETE_REQUEST(self, neighborid):
        
        # new SIXP command, bump the seqnum
        if neighborid not in self.seqnum:
            self.seqnum[neighborid] = 0
        self.seqnum[neighborid] += 1
        
        # create celllist
        celllist = []
        for (slotOffset,channelOffset,n_id) in self.mote.tsch.getTxCells(neighborid):
            assert n_id==neighborid
            celllist += [
                {
                    'slotOffset':    slotOffset,
                    'channelOffset': channelOffset,
                }
            ]
            if len(celllist)==self.CELLLIST_LENGTH:
                break
        assert celllist
        
        # create DELETE request
        deleteRequest = {
            'type':                     d.PKT_TYPE_SIXP_DELETE_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          [d.CELLOPTION_TX],
                'NumCells':             1,
                'CellList':             celllist,
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               neighborid,
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
    
    def _receive_DELETE_REQUEST(self,deleteRequest):
        
        assert deleteRequest['app']['NumCells']==1
        assert deleteRequest['app']['CellOptions']==[d.CELLOPTION_TX]
        assert len(deleteRequest['app']['CellList'])>0
        assert len(deleteRequest['app']['CellList'])<=self.CELLLIST_LENGTH
        
        # log
        self.log(
            SimEngine.SimLog.LOG_SIXP_DELETE_REQUEST_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteRequest,
            }
        )
        
        # delete a cell taken at random in the celllist
        cell = random.choice(deleteRequest['app']['CellList'])
        assert (cell['slotOffset'],cell['channelOffset'],deleteRequest['mac']['srcMac']) in self.mote.tsch.getRxCells(deleteRequest['mac']['srcMac'])
        self.mote.tsch.deleteCell(
            slotOffset         = cell['slotOffset'],
            channelOffset      = cell['channelOffset'],
            neighbor           = deleteRequest['mac']['srcMac'],
            cellOptions        = [d.CELLOPTION_RX],
        )
        
        # create DELETE response
        deleteResponse = {
            'type':                     d.PKT_TYPE_SIXP_DELETE_RESPONSE,
            'app': {
                'Code':                 d.SIXP_RC_SUCCESS,
                'SeqNum':               deleteRequest['app']['SeqNum'],
                'CellList':             [
                    {
                        'slotOffset':   cell['slotOffset'],
                        'channelOffset':cell['channelOffset'],
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
    
    def _receive_DELETE_RESPONSE(self,deleteResponse):
        
        assert len(deleteResponse['app']['CellList'])==1
        
        # delete cell from celllist
        cell = deleteResponse['app']['CellList'][0]
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
