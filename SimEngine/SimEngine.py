#!/usr/bin/python
"""
\brief Discrete-event simulation engine.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
"""

# ========================== imports =========================================

import threading
import traceback

import Mote
import SimSettings
import SimLog
import Connectivity

# =========================== defines =========================================

# =========================== body ============================================

class SimEngine(threading.Thread):

    #===== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimEngine,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton

    def __init__(self, cpuID=None, run_id=None, failIfNotInit=False, verbose=False):

        if failIfNotInit and not cls._init:
            raise EnvironmentError('SimEngine singleton not initialized.')

        #===== start singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        #===== end singleton

        # store params
        self.cpuID                          = cpuID
        self.run_id                         = run_id
        self.verbose                        = verbose

        # local variables
        self.dataLock                       = threading.RLock()
        self.pauseSem                       = threading.Semaphore(0)
        self.simPaused                      = False
        self.goOn                           = True
        self.asn                            = 0
        self.startCb                        = []
        self.endCb                          = []
        self.events                         = []

        # init singletons
        self.log                            = SimLog.SimLog().log
        self.settings                       = SimSettings.SimSettings()
        self.motes                          = [Mote.Mote.Mote(mote_id) for mote_id in range(self.settings.exec_numMotes)]
        self.connectivity                   = Connectivity.Connectivity()

        # pass SimEngine to SimLog
        SimLog.SimLog().set_simengine(self)

        # select first mote as dagRoot
        self.motes[0].role_setDagRoot()

        # boot all motes
        for i in range(len(self.motes)):
            self.motes[i].boot()

        # initialize parent class
        threading.Thread.__init__(self)
        self.name                           = 'SimEngine'

    def destroy(self):

        # destroy my own instance
        cls = type(self)
        cls._instance                      = None
        cls._init                          = False

    #======================== thread ==========================================

    def run(self):
        """ event driven simulator, this thread manages the events """
        try:
            self.log(
                SimLog.LOG_THREAD_STATE,
                {
                    "name": self.name,
                    "state": "started"
                }
            )

            # schedule the endOfSimulation event if we are not simulating the join process
            if not self.settings.secjoin_enabled:
                self.scheduleAtAsn(
                    asn         = self.settings.tsch_slotframeLength*self.settings.exec_numSlotframesPerRun,
                    cb          = self._actionEndSim,
                    uniqueTag   = (None,'_actionEndSim'),
                )

            # schedule action at every end of cycle
            self.scheduleAtAsn(
                asn=self.asn + self.settings.tsch_slotframeLength - 1,
                cb=self._actionEndCycle,
                uniqueTag=(None, '_actionEndCycle'),
                priority=10,
            )

            # call the start callbacks
            for cb in self.startCb:
                cb()

            # consume events until self.goOn is False
            while self.goOn:

                with self.dataLock:

                    # abort simulation when no more events
                    if not self.events:
                        self.log(
                            SimLog.LOG_THREAD_STATE,
                            {
                                "name": self.name,
                                "state": "stopped"
                            }
                        )
                        break

                    # make sure we are in the future
                    (a, b, cb, c) = self.events[0]
                    if c[1] != '_actionPauseSim':
                        assert self.events[0][0] >= self.asn

                    # update the current ASN
                    self.asn = self.events[0][0]

                    # call callbacks at this ASN
                    while True:
                        if self.events[0][0] != self.asn:
                            break
                        (_, _, cb, _) = self.events.pop(0)
                        cb()

            # call the end callbacks
            for cb in self.endCb:
                cb()

            # log
            self.log(
                SimLog.LOG_THREAD_STATE,
                {
                    "name": self.name,
                    "state": "stopped"
                }
            )
        except Exception as e:
            print 'poipoipoipoipoi'
            traceback.print_exc()
            print 'poipoipoipoipoi'
            self.exc = e
        else:
            self.exc = None

    def join(self):
        super(SimEngine, self).join()
        if self.exc:
            raise self.exc

    #======================== public ==========================================

    #=== scheduling

    def scheduleAtStart(self,cb):
        with self.dataLock:
            self.startCb    += [cb]

    def scheduleIn(self, delay, cb, uniqueTag=None, priority=0, exceptCurrentASN=True):
        """ used to generate events. Puts an event to the queue """

        with self.dataLock:
            asn = int(self.asn + (float(delay) / float(self.settings.tsch_slotDuration)))

            self.scheduleAtAsn(asn, cb, uniqueTag, priority, exceptCurrentASN)

    def scheduleAtAsn(self, asn, cb, uniqueTag=None, priority=0, exceptCurrentASN=True):
        """ schedule an event at specific ASN """

        # make sure we are scheduling in the future
        assert asn > self.asn

        # remove all events with same uniqueTag (the event will be rescheduled)
        if uniqueTag:
            self.removeEvent(uniqueTag, exceptCurrentASN)

        with self.dataLock:

            # find correct index in schedule
            i = 0
            while i<len(self.events) and (self.events[i][0] < asn or (self.events[i][0] == asn and self.events[i][1] <= priority)):
                i +=1

            # add to schedule
            self.events.insert(i, (asn, priority, cb, uniqueTag))

    def removeEvent(self, uniqueTag, exceptCurrentASN=True):
        with self.dataLock:
            i = 0
            while i<len(self.events):
                if self.events[i][3]==uniqueTag and not (exceptCurrentASN and self.events[i][0]==self.asn):
                    self.events.pop(i)
                else:
                    i += 1

    def scheduleAtEnd(self,cb):
        with self.dataLock:
            self.endCb      += [cb]

    # === misc

    # delay in asn
    def terminateSimulation(self,delay):
        with self.dataLock:
            self.asnEndExperiment = self.asn+delay
            self.scheduleAtAsn(
                    asn         = self.asn+delay,
                    cb          = self._actionEndSim,
                    uniqueTag   = (None, '_actionEndSim'),
            )

    # === play/pause

    def play(self):
        self._actionResumeSim()

    def pauseAtAsn(self,asn):
        if not self.simPaused:
            self.scheduleAtAsn(
                asn         = asn,
                cb          = self._actionPauseSim,
                uniqueTag   = ('SimEngine', '_actionPauseSim'),
            )

    # === getters/setters

    def getAsn(self):
        return self.asn

    # ======================== private ========================================

    def _actionPauseSim(self):
        if not self.simPaused:
            self.simPaused = True
            self.pauseSem.acquire()

    def _actionResumeSim(self):
        if self.simPaused:
            self.simPaused = False
            self.pauseSem.release()

    def _actionEndSim(self):
        with self.dataLock:
            self.goOn = False

    def _actionEndCycle(self):
        """Called at each end of cycle."""

        cycle = int(self.asn / self.settings.tsch_slotframeLength)

        # print
        if self.verbose:
            print('   cycle: {0}/{1}'.format(cycle, self.settings.exec_numSlotframesPerRun-1))

        # schedule next statistics collection
        self.scheduleAtAsn(
            asn         = self.asn + self.settings.tsch_slotframeLength,
            cb          = self._actionEndCycle,
            uniqueTag   = (None, '_actionEndCycle'),
            priority    = 10,
        )

