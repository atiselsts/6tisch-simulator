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
import threading

# Mote sub-modules
import app
import sixlowpan
import rpl
import sf
import sixp
import secjoin
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
        self.sixlowpan                 = sixlowpan.Sixlowpan(self)
        self.rpl                       = rpl.Rpl(self)
        self.sixp                      = sixp.SixP(self)
        self.secjoin                   = secjoin.SecJoin(self)
        self.tsch                      = tsch.Tsch(self)
        self.sf                        = sf.SchedulingFunction.get_sf(self)
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

        # app
        if not self.dagRoot:
            if self.settings.app_burstNumPackets and self.settings.app_burstTimestamp:
                self.app.schedule_mote_sendPacketBurstToDAGroot()
            else:
                self.app.schedule_mote_sendSinglePacketToDAGroot(firstPacket=True)

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

    def _myNeighbors(self):
        return [n.id for n in self.engine.motes if self.engine.connectivity.get_pdr(self.id,n.id,0) > 0]

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
            
            # activate the TSCH stack
            self.activate_tsch_stack()
            
            # give DAGroot's ID to each mote FIXME: remove
            for mote in self.engine.motes:
                mote.dagRootId  = self.id
            
            # schedule the first active cell
            self.tsch.tsch_schedule_active_cell()
            
        else:
            # I'm NOT the DAG root
            
            # schedule the first listeningForE cell
            self.tsch.tsch_schedule_listeningForEB_cell()

    #======================== private =========================================
