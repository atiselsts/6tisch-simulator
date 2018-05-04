"""
Secure joining layer of a mote.
"""

# =========================== imports =========================================

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SecJoin(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self._isJoined                      = False
        self._joinRetransmissionPayload     = 0
        self._joinAsn                       = 0

    #======================== public ==========================================

    def setIsJoined(self, newState):
        assert newState in [True, False]
        self._isJoined = newState

    def isJoined(self):
        return self._isJoined

    def scheduleJoinProcess(self):
        """
        Schedule to start the join process sometimes in the future
        """
        
        if self.settings.secjoin_enabled:
            raise NotImplementedError()
            # initiate join process
            self.engine.scheduleIn(
                delay            = self.settings.tsch_slotDuration + self.settings.secjoin_joinTimeout * random.random(),
                cb               = self._initiateJoinProcess,
                uniqueTag        = (self.mote.id, 'secjoin._initiateJoinProcess'),
                intraSlotOrder   = 2,
            )
        else:
            # consider I'm already joined
            self.setIsJoined(True)

    def receiveJoinPacket(self, srcIp, payload, timestamp):
        """
        Receiving a join packet (same function for join request and response).

        FIXME: different functions for join request and response.
        """
        
        raise NotImplementedError()
        
        # remove pending retransmission event
        self.engine.removeFutureEvent(
            (self.mote.id, '_join_action_retransmission')
        )

        # log
        self.log(
            SimEngine.SimLog.LOG_JOIN_RX,
            {
                'source': srcIp.id,
                "token": payload[0]
            }
        )

        # this is a hack to allow downward routing of join packets before node has sent a DAO
        if self.mote.dagRoot:
            self.mote.rpl.updateDaoParents({tuple([payload[1]]): [[payload[2]]]})

        if payload[0] != 0:
            # FIXME: document

            newToken = payload[0] - 1
            self._sendJoinPacket(
                token        = newToken,
                destination  = srcIp,
            )
        else:
            # FIXME: document

            # record that I'm joined
            self._setJoined()

            # initialize the rest of the stack
            self.mote.activate_tsch_stack()

    def areAllNeighborsJoined(self):
        """
        Are all my neighbors joined?
        """
        return [nei for nei in self.mote._myNeighbors() if self.engine.motes[nei].secjoin.isJoined is True]

    #======================== private ==========================================

    def _initiateJoinProcess(self):
        """
        Start the join process.
        """
        if not self.mote.dagRoot:
            if self.mote.rpl.getPreferredParent()!=None:
                if not self.isJoined:
                    self._sendJoinPacket(
                        token          = self.settings.secjoin_numExchanges - 1,
                        destination    = self.mote.dagRootId,
                    )
            else: # node doesn't have a parent yet, re-scheduling
                self.scheduleJoinProcess()

    def _sendJoinPacket(self, token, destination):
        """
        Send join packet (same function for join request and response).

        Payload contains number of exchanges.

        FIXME: different functions for join request and response.
        """

        sourceRoute = []
        if self.mote.dagRoot:
            sourceRoute = self.mote.rpl.computeSourceRoute([destination.id])

        if sourceRoute or not self.mote.dagRoot:
            # create new packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.PKT_TYPE_JOIN,
                'code':           None,
                'payload':        [
                    token,
                    self.mote.id if not self.mote.dagRoot else None,
                    self.mote.rpl.getPreferredParent() if not self.mote.dagRoot else None,
                ],
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self, # DAG root
                'dstIp':          destination,
                'sourceRoute':    sourceRoute
            }
            
            # increment traffic
            self.log(
                SimEngine.SimLog.LOG_JOIN_TX,
                {
                    'destination': destination.id,
                    "token": token
                }
            )
            
            # enqueue packet in TSCH queue
            self.mote.tsch.enqueue(newPacket)

            # save last token sent
            self._joinRetransmissionPayload = token

            # schedule retransmission (will be canceled if response received)
            if not self.mote.dagRoot:
                self.engine.scheduleIn(
                    delay              = self.settings.tsch_slotDuration + self.settings.secjoin_joinTimeout,
                    cb                 = self._retransmitJoinPacket,
                    uniqueTag          = (self.mote.id, '_join_action_retransmission'),
                    intraSlotOrder     = 2,
                )

    def _setJoined(self):
        """
        Record that I'm now joined.
        """
        assert not self.mote.dagRoot

        if not self.isJoined:
            self.isJoined = True
            self._joinAsn  = self.engine.getAsn()

            # log
            self.log(SimEngine.SimLog.LOG_MOTE_STATE)

            # schedule bootstrap of the preferred parent
            self.mote.sf.schedule_parent_change(self)
    
    def _retransmitJoinPacket(self):
        """
        Send join packet again.
        """
        if not self.mote.dagRoot and not self.isJoined:
            self._sendJoinPacket(
                self._joinRetransmissionPayload,
                self.mote.dagRootId,
            )
