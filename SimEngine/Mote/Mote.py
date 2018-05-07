"""
Model of a 6TiSCH mote.
"""

# =========================== imports =========================================

import threading

# Mote sub-modules
import app
import secjoin
import rpl
import sixlowpan
import sf
import sixp
import tsch
import radio
import batt

import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== body ============================================

class Mote(object):

    def __init__(self, id):

        # store params
        self.id                        = id

        # admin
        self.dataLock                  = threading.RLock()
        
        # singletons (quicker access, instead of recreating every time)
        self.log                       = SimEngine.SimLog.SimLog().log
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()

        # stack state
        self.dagRoot                   = False
        self.dodagId                   = None
        self.neighbors                 = {}
        
        # stack
        self.app                       = app.App(self)
        self.secjoin                   = secjoin.SecJoin(self)
        self.rpl                       = rpl.Rpl(self)
        self.sixlowpan                 = sixlowpan.Sixlowpan(self)
        self.sf                        = sf.SchedulingFunction.get_sf(self)
        self.sixp                      = sixp.SixP(self)
        self.tsch                      = tsch.Tsch(self)
        self.radio                     = radio.Radio(self)
        self.batt                      = batt.Batt(self)

    # ======================= stack ===========================================

    # ===== role

    def setDagRoot(self):
        self.dagRoot         = True
        self.dodagId         = self.id
    
    # ==== wireless
    
    # FIXME: see #135
    def getPDR(self, neighbor):
        """ returns the pdr to that neighbor"""
        with self.dataLock:
            return self.engine.connectivity.get_pdr(
                source       = self.id,
                destination  = neighbor,
                channel      = 0, #FIXME channel
            )
    
    # ==== neighbors
    
    def _add_neighbor(self,neighbor_id):
        
        assert neighbor_id not in self.neighbors
        
        # create an empty entry
        self.neighbors[neighbor_id] = {
            'rank':           None,
            # freshness
            'lastHeardAsn':   None,
            # usage statistics
            'numTx':          0,
            'numTxAck':       0,
            'numRx':          0,
        }
        
        # send indication to SF
        self.sf.indication_neighbor_added(neighbor_id)
    
    def neighbors_indicate_rx(self,packet):
        '''
        From tsch, used to maintain neighbor table
        '''
        neighbor_id = packet['mac']['srcMac'] # alias
        
        # add neighbor, if needed
        if neighbor_id not in self.neighbors:
            self._add_neighbor(neighbor_id)
        
        # update neighbor table
        self.neighbors[neighbor_id]['numRx']         += 1
        self.neighbors[neighbor_id]['lastHeardAsn']   = self.engine.getAsn()
    
    def neighbors_indicate_tx(self,packet,isACKed):
        '''
        From tsch, used to maintain neighbor table
        '''
        neighbor_id = packet['mac']['dstMac'] # alias
        
        # make sure I have that neighbor in my neighbor table
        assert neighbor_id in self.neighbors
        
        # update neighbor table
        self.neighbors[neighbor_id]['numTx']         += 1
        if isACKed:
            self.neighbors[neighbor_id]['numTxAck']  += 1
        self.neighbors[neighbor_id]['lastHeardAsn']   = self.engine.getAsn()
    
    def isNeighbor(self,neighbor_id):
        return (neighbor_id in self.neighbors)
    
    def numNeighbors(self):
        return len(self.neighbors)
    
    # ==== location

    def setLocation(self, x, y):
        with self.dataLock:
            self.x = x
            self.y = y

    def getLocation(self):
        with self.dataLock:
            return self.x, self.y

    # ==== battery

    def boot(self):
        
        if self.dagRoot:
            # I'm the DAG root
            
            # app
            self.app.startSendingData()    # dagRoot
            # secjoin
            self.secjoin.setIsJoined(True) # dagRoot
            # rpl
            self.rpl.setRank(256)
            # sf
            self.sf.startMonitoring()    # dagRoot
            # tsch
            self.tsch.add_minimal_cell()
            self.tsch.setIsSync(True)    # dagRoot
            self.tsch.startSendingEBs()  # dagRoot
            self.tsch.startSendingDIOs() # dagRoot
            
            # schedule the first active cell
            self.tsch.tsch_schedule_next_active_cell()
            
        else:
            # I'm NOT the DAG root
            
            # schedule the first listeningForE cell
            self.tsch.tsch_schedule_next_listeningForEB_cell()
    
    # ==== EBs and DIOs
    
    def clear_to_send_EBs_DIOs_DATA(self):
        returnVal = True
        
        # I need to be synchronized
        if returnVal==True:
            if self.tsch.getIsSync()==False:
                returnVal = False
        
        # I need to have joined
        if returnVal==True:
            if self.secjoin.getIsJoined()==False:
                returnVal = False
        
        # I must have a preferred parent (or be the dagRoot)
        if returnVal==True:
            if self.dagRoot==False and self.rpl.getPreferredParent()==None:
                returnVal = False
        
        # I must have at least one TX cell to my preferred parent (if running MSF)
        if returnVal==True:
            if  (
                    (self.dagRoot == False)
                    and
                    (type(self.sf) == sf.MSF)
                    and
                    self.tsch.getTxCells(self.rpl.getPreferredParent())== 0
                ):
                    returnVal = False
        
        return returnVal
    
    # ==== dropping
    
    def drop_packet(self, packet, reason):
        
        # log
        self.log(
            SimEngine.SimLog.LOG_PACKET_DROPPED,
            {
                "_mote_id":  self.id,
                "packet":    packet,
                "reason":    reason,
            }
        )
        
        # remove all the element of packet so it cannot be processed further
        # Note: this is useless, but allows us to catch bugs in case packet is further processed
        for k in packet.keys():
            del packet[k]
    
    #======================== private =========================================
