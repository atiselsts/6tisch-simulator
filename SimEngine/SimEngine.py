"""
\brief Discrete-event simulation engine.
"""

# ========================== imports =========================================

import hashlib
import platform
import random
import sys
import threading
import time
import traceback

import Mote
import SimSettings
import SimLog
import Connectivity
import SimConfig

# =========================== defines =========================================

# =========================== body ============================================

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
            self.random_seed                    = None
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
            output  = []
            output += ['']
            output += ['==============================']
            output += ['']
            output += ['CRASH in {0}!'.format(self.name)]
            output += ['']
            output += [traceback.format_exc()]
            output += ['==============================']
            output += ['']
            output += ['The following settings are used:']
            output += ['']
            for k, v in SimSettings.SimSettings().__dict__.iteritems():
                if (
                        (k == 'exec_randomSeed')
                        and
                        (v in ['random', 'context'])
                    ):
                    # put the random seed value in output
                    # exec_randomSeed: random
                    v = '{0} ({1})'.format(v, self.random_seed)
                output += ['{0}: {1}'.format(str(k), str(v))]
            output += ['']
            output += ['==============================']
            output += ['']
            output  = '\n'.join(output)
            sys.stderr.write(output)

            # flush all the buffered log data
            SimLog.SimLog().flush()

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

    def get_mote_by_id(self, mote_id):
        return self.motes[mote_id]
    
    #=== scheduling
    
    def scheduleAtAsn(self, asn, cb, uniqueTag, intraSlotOrder):
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
    
    def scheduleIn(self, delay, cb, uniqueTag, intraSlotOrder):
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
            asn              = asn,
            cb               = self._actionPauseSim,
            uniqueTag        = ('DiscreteEventEngine', '_actionPauseSim'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
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
                    asn                = self.asn+delay,
                    cb                 = self._actionEndSim,
                    uniqueTag          = ('DiscreteEventEngine', '_actionEndSim'),
                    intraSlotOrder     = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
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
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
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
    
    DAGROOT_ID = 0
    
    def _init_additional_local_variables(self):
        self.settings                   = SimSettings.SimSettings()

        # set random seed
        if   self.settings.exec_randomSeed == 'random':
            self.random_seed = random.randint(0, sys.maxint)
        elif self.settings.exec_randomSeed == 'context':
            # with context for exec_randomSeed, an MD5 value of
            # 'startTime-hostname-run_id' is used for a random seed
            startTime = SimConfig.SimConfig.get_startTime()
            if startTime is None:
                startTime = time.time()
            context = (platform.uname()[1], str(startTime), str(self.run_id))
            md5 = hashlib.md5()
            md5.update('-'.join(context))
            self.random_seed = int(md5.hexdigest(), 16) % sys.maxint
        else:
            assert isinstance(self.settings.exec_randomSeed, int)
            self.random_seed = self.settings.exec_randomSeed
        # apply the random seed; log the seed after self.log is initialized
        random.seed(a=self.random_seed)

        self.motes                      = [Mote.Mote.Mote(m) for m in range(self.settings.exec_numMotes)]
        self.connectivity               = Connectivity.Connectivity()
        self.log                        = SimLog.SimLog().log
        SimLog.SimLog().set_simengine(self)

        # log the random seed
        self.log(
            SimLog.LOG_SIMULATOR_RANDOM_SEED,
            {
                'value': self.random_seed
            }
        )
        
        # select dagRoot
        self.motes[self.DAGROOT_ID].setDagRoot()

        # boot all motes
        for i in range(len(self.motes)):
            self.motes[i].boot()
    
    def _routine_thread_started(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                "name":   self.name,
                "state":  "started"
            }
        )
        
        # schedule end of simulation
        self.scheduleAtAsn(
            asn              = self.settings.tsch_slotframeLength*self.settings.exec_numSlotframesPerRun,
            cb               = self._actionEndSim,
            uniqueTag        = ('SimEngine','_actionEndSim'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

        # schedule action at every end of slotframe_iteration
        self.scheduleAtAsn(
            asn              = self.asn + self.settings.tsch_slotframeLength - 1,
            cb               = self._actionEndSlotframe,
            uniqueTag        = ('SimEngine', '_actionEndSlotframe'),
            intraSlotOrder   = Mote.MoteDefines.INTRASLOTORDER_ADMINTASKS,
        )

    def _routine_thread_crashed(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                "name": self.name,
                "state": "crash"
            }
        )

    def _routine_thread_ended(self):
        # log
        self.log(
            SimLog.LOG_SIMULATOR_STATE,
            {
                "name": self.name,
                "state": "stopped"
            }
        )
