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
        
        # singletons (to access quicker than recreate every time)
        self.engine               = SimEngine.SimEngine.SimEngine()
        self.settings             = SimEngine.SimSettings.SimSettings()
        self.log                  = SimEngine.SimLog.SimLog().log

        # local variables
        self.seqnum               = {} # indexed by neighborid

    #======================== public ==========================================

    # from upper layers
    
    def issue_ADD_REQUEST(self, neighborid):
        
        # new 6P command, bump the seqnum
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
            'type':                     d.PKT_TYPE_6P_ADD_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          d.DIR_TX,
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
            SimEngine.SimLog.LOG_6P_ADD_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   addRequest
            }
        )
        
        # enqueue
        self.mote.tsch.enqueue(addRequest)

    def issue_DELETE_REQUEST(self, neighborid):
        
        # new 6P command, bump the seqnum
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
            'type':                     d.PKT_TYPE_6P_DELETE_REQUEST,
            'app': {
                'SeqNum':               self.seqnum[neighborid],
                'CellOptions':          d.DIR_TX,
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
            SimEngine.SimLog.LOG_6P_DELETE_REQUEST_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteRequest
            }
        )
        
        # enqueue
        self.mote.tsch.enqueue(deleteRequest)
    
    # from upper layers
    
    def receive(self,packet):
        if   packet['type']==d.PKT_TYPE_6P_ADD_REQUEST:
            self.receive_ADD_REQUEST(packet)
        elif packet['type']==d.PKT_TYPE_6P_ADD_RESPONSE:
            self.receive_ADD_RESPONSE(packet)
        elif packet['type']==d.PKT_TYPE_6P_DELETE_REQUEST:
            self.receive_DELETE_REQUEST(packet)
        elif packet['type']==d.PKT_TYPE_6P_DELETE_RESPONSE:
            self.receive_DELETE_RESPONSE(packet)
        else:
            raise SystemError()
    
    #======================== private =========================================
    
    # === ADD
    
    def receive_ADD_REQUEST(self,packet):
        
        assert packet['app']['NumCells']==1
        assert packet['app']['CellOptions']==d.DIR_TX
        assert len(packet['app']['CellList'])==self.CELLLIST_LENGTH
        
        added_slotOffset    = None
        added_channelOffset = None
        
        # look for cell that works in celllist
        for cell in packet['app']['CellList']:
            if cell['slotOffset'] not in self.mote.tsch.getSchedule():
                
                # remember what I added
                added_slotOffset       = cell['slotOffset']
                added_channelOffset    = cell['channelOffset']
                
                # add to my schedule
                self.mote.tsch.addCell(
                    neighbor           = packet['mac']['srcMac'],
                    slotoffset         = cell['slotOffset'],
                    channeloffset      = cell['channelOffset'],
                    direction          = d.DIR_RX,
                )
                
                break
        
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
            'type':                     d.PKT_TYPE_6P_ADD_RESPONSE,
            'app': {
                'Code':                 d.SIXP_RC_SUCCESS,
                'SeqNum':               packet['app']['SeqNum'],
                'CellList':             celllist,
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               packet['mac']['srcMac'],
            },
        }
        
        # log
        self.log(
            SimEngine.SimLog.LOG_6P_ADD_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   addResponse
            }
        )
        
        # enqueue
        self.mote.tsch.enqueue(addResponse)
    
    def receive_ADD_RESPONSE(self,packet):
        
        assert len(packet['app']['CellList'])==1
        
        # add cell from celllist
        cell = packet['app']['CellList'][0]
        self.mote.tsch.addCell(
            neighbor           = packet['mac']['srcMac'],
            slotoffset         = cell['slotOffset'],
            channeloffset      = cell['channelOffset'],
            direction          = d.DIR_TX,
        )
        
        # log
        self.log(
            SimEngine.SimLog.LOG_6P_ADD_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   packet
            }
        )
    
    # === DELETE
    
    def receive_DELETE_REQUEST(self,packet):
        
        assert packet['app']['NumCells']==1
        assert packet['app']['CellOptions']==d.DIR_TX
        assert len(packet['app']['CellList'])>0
        assert len(packet['app']['CellList'])<=self.CELLLIST_LENGTH
        
        # delete a cell taken at random in the celllist
        cell = random.choice(packet['app']['CellList'])
        assert (cell['slotOffset'],cell['channelOffset'],packet['mac']['srcMac']) in self.mote.tsch.getRxCells(packet['mac']['srcMac'])
        self.mote.tsch.removeCell(
            neighbor           = packet['mac']['srcMac'],
            slotoffset         = cell['slotOffset'],
            channeloffset      = cell['channelOffset'],
            direction          = d.DIR_RX,
        )
        
        # create DELETE response
        deleteResponse = {
            'type':                     d.PKT_TYPE_6P_DELETE_RESPONSE,
            'app': {
                'Code':                 d.SIXP_RC_SUCCESS,
                'SeqNum':               packet['app']['SeqNum'],
                'CellList':             [
                    {
                        'slotOffset':   cell['slotOffset'],
                        'channelOffset':cell['channelOffset'],
                    },
                ],
            },
            'mac': {
                'srcMac':               self.mote.id,
                'dstMac':               packet['mac']['srcMac'],
            },
        }
        
        # log
        self.log(
            SimEngine.SimLog.LOG_6P_DELETE_RESPONSE_TX,
            {
                '_mote_id': self.mote.id,
                'packet':   deleteResponse
            }
        )
        
        # enqueue
        self.mote.tsch.enqueue(deleteResponse)
    
    def receive_DELETE_RESPONSE(self,packet):
        
        assert len(packet['app']['CellList'])==1
        
        # delete cell from celllist
        cell = packet['app']['CellList'][0]
        self.mote.tsch.removeCell(
            neighbor           = packet['mac']['srcMac'],
            slotoffset         = cell['slotOffset'],
            channeloffset      = cell['channelOffset'],
            direction          = d.DIR_TX,
        )
        
        # log
        self.log(
            SimEngine.SimLog.LOG_6P_DELETE_RESPONSE_RX,
            {
                '_mote_id': self.mote.id,
                'packet':   packet
            }
        )