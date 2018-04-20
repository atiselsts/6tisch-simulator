"""
Secure joining layer of a mote.

secjoin starts after having received the first EB.
When secjoin done, _stack_init_synced() is called.
"""

# =========================== imports =========================================

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('secjoin')
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

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
        self.propagation                    = SimEngine.Propagation.Propagation()

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
        self.engine.scheduleIn(
            delay       = self.settings.tsch_slotDuration + self.settings.secjoin_joinTimeout * random.random(),
            cb          = self._initiateJoinProcess,
            uniqueTag   = (self.mote.id, 'secjoin._initiateJoinProcess'),
            priority    = 2,
        )

    def receiveJoinPacket(self, srcIp, payload, timestamp):
        """
        Receiving a join packet (same function for join request and response).

        FIXME: different functions for join request and response.
        """

        # remove pending retransmission event
        self.engine.removeEvent(
            (self.mote.id, '_join_action_retransmission')
        )

        # log
        self._log(
            d.INFO,
            "[join] Received join packet from {0} with token {1}",
            (srcIp.id, payload[0])
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
            self.mote._stack_init_synced()

    def areAllNeighborsJoined(self):
        """
        Are all my neighbors joined?
        """
        return [nei for nei in self.mote._myNeighbors() if nei.secjoin.isJoined is True]

    #======================== private ==========================================

    def _initiateJoinProcess(self):
        """
        Start the join process.
        """
        if not self.mote.dagRoot:
            if self.mote.rpl.getPreferredParent():
                if not self.isJoined:
                    self._sendJoinPacket(
                        token          = self.settings.secjoin_numExchanges - 1,
                        destination    = self.mote.dagRootAddress,
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
            sourceRoute = self.mote.rpl.getSourceRoute([destination.id])

        if sourceRoute or not self.mote.dagRoot:
            # create new packet
            newPacket = {
                'asn':            self.engine.getAsn(),
                'type':           d.APP_TYPE_JOIN,
                'code':           None,
                'payload':        [
                    token,
                    self.mote.id if not self.mote.dagRoot else None,
                    self.mote.rpl.getPreferredParent().id if not self.mote.dagRoot else None,
                ],
                'retriesLeft':    d.TSCH_MAXTXRETRIES,
                'srcIp':          self, # DAG root
                'dstIp':          destination,
                'sourceRoute':    sourceRoute
            }

            # enqueue packet in TSCH queue
            isEnqueued = self.mote._tsch_enqueue(newPacket)

            if isEnqueued:
                # increment traffic
                self.mote._log(
                    d.INFO,
                    "[join] Enqueued join packet for mote {0} with token = {1}",
                    (destination.id, token),
                )
            else:
                # update mote stats
                self.mote._radio_drop_packet(newPacket, SimEngine.SimLog.LOG_TSCH_DROP_FAIL_ENQUEUE['type'])

            # save last token sent
            self._joinRetransmissionPayload = token

            # schedule retransmission (will be canceled if response received)
            if not self.mote.dagRoot:
                self.engine.scheduleIn(
                    delay         = self.settings.tsch_slotDuration + self.settings.secjoin_joinTimeout,
                    cb            = self._retransmitJoinPacket,
                    uniqueTag     = (self.mote.id, '_join_action_retransmission'),
                    priority      = 2,
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
            self.mote_log(
                d.INFO,
                "[join] Mote joined",
            )

            # schedule bootstrap of the preferred parent
            self.sf.schedule_parent_change(self)

            # check if all motes have joined, if so end the simulation after exec_numSlotframesPerRun
            if self.settings.secjoin_enabled and all(mote.secjoin.isJoined is True for mote in self.engine.motes):
                if self.settings.exec_numSlotframesPerRun != 0:
                    # experiment time in ASNs
                    simTime = self.settings.exec_numSlotframesPerRun * self.settings.tsch_slotframeLength
                    # offset until the end of the current cycle
                    offset = self.settings.tsch_slotframeLength - (self.engine.asn % self.settings.tsch_slotframeLength)
                    # experiment time + offset
                    delay = simTime + offset
                else:
                    # simulation will finish in the next asn
                    delay = 1
                # end the simulation
                self.engine.terminateSimulation(delay)

    def _retransmitJoinPacket(self):
        """
        Send join packet again.
        """
        if not self.mote.dagRoot and not self.isJoined:
            self._sendJoinPacket(
                self._joinRetransmissionPayload,
                self.mote.dagRootAddress,
            )
