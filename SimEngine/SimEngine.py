"""
\brief Discrete-event simulation engine.
"""

# ========================== imports =========================================

import sys
import threading
import traceback

import Mote
import SimSettings
import SimLog
import Connectivity

# =========================== defines =========================================

DAGROOT_ID = 0 # select first mote as DagRoot# =========================== body ============================================

class DiscreteEventEngine(threading.Thread):
    
    #===== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DiscreteEventEngine,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton

    def __init__(self, cpuID=None, run_id=None, verbose=False):

        #===== singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        #===== singleton
        
        try:
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
            self.exc                            = None
            self.events                         = []
            self._init_additional_local_variables()

            # initialize parent class
            threading.Thread.__init__(self)
            self.name                           = 'DiscreteEventEngine'
        except:
            # an exception happened when initializing the instance
            
            # destroy the singleton
            cls._instance         = None
            cls._init             = False
            raise

    def destroy(self):
        if self._Thread__initialized:
            # initialization finished without exception
            
            if self.is_alive():
                # thread is start'ed
                self.play()           # cause one more loop in thread
                self._actionEndSim()  # causes self.gOn to be set to False
                self.join()           # wait until thread is dead
            else:
                # thread NOT start'ed yet, or crashed
                
                # destroy the singleton
                cls = type(self)
                cls._instance         = None
                cls._init             = False
        else:
            # initialization failed
            pass # do nothing, singleton already destroyed

    #======================== thread ==========================================

    def run(self):
        """ loop through events """
        try:
            # additional routine
            self._routine_thread_started()

            # consume events until self.goOn is False
            while self.goOn:

                with self.dataLock:
                    
                    # abort simulation when no more events
                    if not self.events:
                        break
                    
                    # make sure we are in the future
                    (a, b, cb, c) = self.events[0]
                    if c[1] != '_actionPauseSim':
                        assert self.events[0][0] >= self.asn
                    
                    # update the current ASN
                    self.asn = self.events[0][0]
                    
                    # find callbacks for this ASN
                    cbs = []
                    while True:
                        if (not self.events) or (self.events[0][0] != self.asn):
                            break
                        (_, _, cb, _) = self.events.pop(0)
                        cbs += [cb]
                        
                # call the callbacks (outside the dataLock)
                
                for cb in cbs:
                    cb()

        except Exception as e:
            # thread crashed
            
            # record the exception
            self.exc = e
            
            # additional routine
            self._routine_thread_crashed()
            
            # print
            print 'CRASH in DiscreteEventEngine!'
            traceback.print_exc()
            
        else:
            # thread ended (gracefully)
            
            # no exception
            self.exc = None
            
            # additional routine
            self._routine_thread_ended()
            
        finally:
            
            # destroy this singleton
            cls = type(self)
            cls._instance                      = None
            cls._init                          = False

    def join(self):
        super(DiscreteEventEngine, self).join()
        if self.exc:
            raise self.exc

    #======================== public ==========================================
    
    # === getters/setters

    def getAsn(self):
        return self.asn
    
    #=== scheduling
    
    def scheduleAtAsn(self, asn, cb, uniqueTag, intraSlotOrder=0):
        """
        Schedule an event at a particular ASN in the future.
        Also removed all future events with the same uniqueTag.
        """

        # make sure we are scheduling in the future
        assert asn > self.asn

        # remove all events with same uniqueTag (the event will be rescheduled)
        self.removeFutureEvent(uniqueTag)

        with self.dataLock:

            # find correct index in schedule
            i = 0
            while i<len(self.events) and (self.events[i][0] < asn or (self.events[i][0] == asn and self.events[i][1] <= intraSlotOrder)):
                i +=1

            # add to schedule
            self.events.insert(i, (asn, intraSlotOrder, cb, uniqueTag))
    
    def scheduleIn(self, delay, cb, uniqueTag, intraSlotOrder=0):
        """
        Schedule an event 'delay' ASNs into the future.
        Also removed all future events with the same uniqueTag.
        """

        with self.dataLock:
            asn = int(self.asn + (float(delay) / float(self.settings.tsch_slotDuration)))

            self.scheduleAtAsn(asn, cb, uniqueTag, intraSlotOrder)

    # === play/pause

    def play(self):
        self._actionResumeSim()

    def pauseAtAsn(self,asn):
        self.scheduleAtAsn(
            asn         = asn,
            cb          = self._actionPauseSim,
            uniqueTag   = ('DiscreteEventEngine', '_actionPauseSim'),
        )

    # === misc

    def removeFutureEvent(self, uniqueTag):
        with self.dataLock:
            i = 0
            while i<len(self.events):
                if (self.events[i][3]==uniqueTag) and (self.events[i][0]!=self.asn):
                    self.events.pop(i)
                else:
                    i += 1

    def terminateSimulation(self,delay):
        with self.dataLock:
            self.asnEndExperiment = self.asn+delay
            self.scheduleAtAsn(
                    asn         = self.asn+delay,
                    cb          = self._actionEndSim,
                    uniqueTag   = ('DiscreteEventEngine', '_actionEndSim'),
            )

    # ======================== private ========================================

    def _actionPauseSim(self):
        assert self.simPaused==False
        self.simPaused = True
        self.pauseSem.acquire()

    def _actionResumeSim(self):
        if self.simPaused:
            self.simPaused = False
            self.pauseSem.release()

    def _actionEndSim(self):
        with self.dataLock:
            self.goOn = False

    def _actionEndSlotframe(self):
        """Called at each end of slotframe_iteration."""

        slotframe_iteration = int(self.asn / self.settings.tsch_slotframeLength)

        # print
        if self.verbose:
            print('   slotframe_iteration: {0}/{1}'.format(slotframe_iteration, self.settings.exec_numSlotframesPerRun-1))

        # schedule next statistics collection
        self.scheduleAtAsn(
            asn              = self.asn + self.settings.tsch_slotframeLength,
            cb               = self._actionEndSlotframe,
            uniqueTag        = ('DiscreteEventEngine', '_actionEndSlotframe'),
            intraSlotOrder   = 10,
        )
    
    # ======================== abstract =======================================
    
    def _init_additional_local_variables(self):
        pass
    
    def _routine_thread_started(self):
        pass
    
    def _routine_thread_crashed(self):
        pass
    
    def _routine_thread_ended(self):
        pass


class SimEngine(DiscreteEventEngine):

    def _init_additional_local_variables(self):
        self.settings                   = SimSettings.SimSettings()
        self.motes                      = [Mote.Mote.Mote(mote_id) for mote_id in range(self.settings.exec_numMotes)]
        self.connectivity               = Connectivity.Connectivity()
        self.log                        = SimLog.SimLog().log
        SimLog.SimLog().set_simengine(self)
        
        # select first mote as dagRoot
        self.motes[DAGROOT_ID].role_setDagRoot()

        # boot all motes
        for i in range(len(self.motes)):
            self.motes[i].boot()
    
    def _routine_thread_started(self):
        # log
        self.log(
            SimLog.LOG_THREAD_STATE,
            {
                "name":   self.name,
                "state":  "started"
            }
        )
        
        # schedule the endOfSimulation event if we are not simulating the join process
        if (not self.settings.secjoin_enabled):
            self.scheduleAtAsn(
                asn         = self.settings.tsch_slotframeLength*self.settings.exec_numSlotframesPerRun,
                cb          = self._actionEndSim,
                uniqueTag   = ('SimEngine','_actionEndSim'),
            )

        # schedule action at every end of slotframe_iteration
        self.scheduleAtAsn(
            asn              = self.asn + self.settings.tsch_slotframeLength - 1,
            cb               = self._actionEndSlotframe,
            uniqueTag        = ('SimEngine', '_actionEndSlotframe'),
            intraSlotOrder   = 10,
        )

    def _routine_thread_crashed(self):
        # log
        self.log(
            SimLog.LOG_THREAD_STATE,
            {
                "name": self.name,
                "state": "crash"
            }
        )

    def _routine_thread_ended(self):
        # log
        self.log(
            SimLog.LOG_THREAD_STATE,
            {
                "name": self.name,
                "state": "stopped"
            }
        )
