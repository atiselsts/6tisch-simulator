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
        
        # identifiers
        self.dagRoot                   = False
        self.dagRootId                 = None

        # cell usage
        self.numCellsToNeighbors       = {}      # indexed by neighbor, contains int
        self.numCellsFromNeighbors     = {}      # indexed by neighbor, contains int

        # singletons (to access quicker than recreate every time)
        self.log                       = SimEngine.SimLog.SimLog().log
        self.engine                    = SimEngine.SimEngine.SimEngine()
        self.settings                  = SimEngine.SimSettings.SimSettings()

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
        self.dagRoot              = True

    # ==== stack

    def activate_tsch_stack(self):
        # start the stack layer by layer, we are sync'ed and joined

        # activate different layers
        self.tsch.activate()
        self.rpl.activate()
        self.sf.activate()
        self.app.activate()

    # ==== wireless

    def getCellPDR(self, cell):
        """ returns the pdr of the cell """

        assert cell['neighbor'] is not type(list)

        with self.dataLock:
            if cell['numTx'] < d.NUM_SUFFICIENT_TX:
                return self.getPDR(cell['neighbor'])
            else:
                return float(cell['numTxAck']) / float(cell['numTx'])
    
    def getPDR(self, neighbor):
        """ returns the pdr to that neighbor"""
        with self.dataLock:
            return self.engine.connectivity.get_pdr(
                source       = self.id,
                destination  = neighbor,
                channel      = 0, #FIXME
            )
    
    # ==== neighbors
    
    def _myNeighbors(self): # FIXME: discover neighbors
        return [n.id for n in self.engine.motes if self.engine.connectivity.get_pdr(self.id,n.id,0) > 0]
    
    def getNumNeighbors(self):
        return len(self._myNeighbors())
    
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
            
            # secjoin
            self.secjoin.setIsJoined(True)
            # rpl
            self.rpl.setRank(256)
            self.parentChildfromDAOs  = {}  # from DAOs, {'c': 'p', ...}
            # tsch
            self.tsch.add_minimal_cell()
            self.tsch.setIsSync(True)
            
            # activate the entire upper stack
            self.tsch.activate()
            self.rpl.activate()
            self.sf.activate()
            self.app.activate()
            
            # give DAGroot's ID to each mote FIXME: remove
            for mote in self.engine.motes:
                mote.dagRootId  = self.id
            
            # schedule the first active cell
            self.tsch.tsch_schedule_next_active_cell()
            
        else:
            # I'm NOT the DAG root
            
            # schedule the first listeningForE cell
            self.tsch.tsch_schedule_next_listeningForEB_cell()
    
    # ==== EBs and DIOs
    
    def clear_to_send_EBs_and_DIOs(self):
        returnVal = False
        if self.secjoin.isJoined() or (not self.settings.secjoin_enabled):
            # I have joined
            if  (
                    self.dagRoot
                    or
                    (
                        self.rpl.getPreferredParent()!=None
                        and
                        (
                            (
                                type(self.sf)==sf.MSF
                                and
                                self.numCellsToNeighbors.get(self.rpl.getPreferredParent(),0)>0
                            )
                            or
                            (
                                type(self.sf)!=sf.MSF
                            )
                        )
                    )
                ):
                
                # I am the root, or I have a preferred parent with dedicated cells to it
                returnVal = True
        return returnVal
    
    #======================== private =========================================
    