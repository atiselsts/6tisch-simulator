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

        # stack
        self.app                       = app.App(self)
        self.secjoin                   = secjoin.SecJoin(self)
        self.rpl                       = rpl.Rpl(self)
        self.sixlowpan                 = sixlowpan.Sixlowpan(self)
        self.sf                        = sf.SchedulingFunction(self)
        self.sixp                      = sixp.SixP(self)
        self.tsch                      = tsch.Tsch(self)
        self.radio                     = radio.Radio(self)
        self.batt                      = batt.Batt(self)

    # ======================= stack ===========================================

    # ===== role

    def setDagRoot(self):
        self.dagRoot         = True
        self.dodagId         = self.id

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
            self.app.startSendingData()     # dagRoot
            # secjoin
            self.secjoin.setIsJoined(True)  # dagRoot
            # rpl
            self.rpl.start()
            # tsch
            self.tsch.clock.sync()
            self.tsch.setIsSync(True)       # dagRoot
            self.tsch.add_minimal_cell()    # dagRpot
            self.tsch.startSendingEBs()     # dagRoot

        else:
            # I'm NOT the DAG root

            # schedule the first listeningForE cell
            self.tsch.schedule_next_listeningForEB_cell()

    # ==== EBs and DIOs

    def clear_to_send_EBs_DATA(self):
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


        # I must have at least one dedicated cell to my preferred parent (if
        # running MSF)
        if returnVal==True:
            if  (
                    (self.dagRoot == False)
                    and
                    (type(self.sf) == sf.SchedulingFunctionMSF)
                    and
                    (
                        len(
                            filter(
                                lambda cell: d.CELLOPTION_TX in cell.options,
                                self.tsch.get_cells(self.rpl.getPreferredParent())
                            )
                        ) == 0
                    )
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
