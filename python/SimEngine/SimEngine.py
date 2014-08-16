#!/usr/bin/python
'''
\brief Discrete-event simulation engine.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
'''

#============================ logging =========================================

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('SimEngine')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import threading

import Propagation
import Topology
import Mote
import SimSettings

#============================ defines =========================================

#============================ body ============================================

class SimEngine(threading.Thread):
    
    #===== start singleton
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimEngine,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton
    
    def __init__(self,runNum=None):
        
        #===== start singleton
        if self._init:
            return
        self._init = True
        #===== end singleton
        
        # store params
        self.runNum                         = runNum
        
        # local variables
        self.settings                       = SimSettings.SimSettings()
        self.dataLock                       = threading.RLock()
        self.goOn                           = True
        self.asn                            = 0
        self.events                         = []
        self.motes                          = [Mote.Mote(id) for id in range(self.settings.numMotes)]
        
        # stats variables (TODO: move to other object)
        self.scheduledCells                 = set()
        self.collisionCells                 = set()
        self.inactivatedCells               = set()
        self.columnNames                    = []
        self.numAccumScheduledCells         = 0
        self.numAccumScheduledCollisions    = 0
        self.queueDelays                    = []
        
        # initialize propagation
        self.propagation                    = Propagation.Propagation()
        
        # initialize topology
        self.topology                       = Topology.Topology(self.motes)
        self.topology.createTopology()
        
        # boot all motes
        for i in range(len(self.motes)):
            self.motes[i].boot()
        
        # initialize parent class
        threading.Thread.__init__(self)
        self.name                           = 'SimEngine'
    
    def destroy(self):
        # destroy the propagation singleton
        self.propagation.destroy()
        
        # destroy my own instance
        self._instance                      = None
        self._init                          = False
    
    #======================== thread ==========================================
    
    def run(self):
        ''' event driven simulator, this thread manages the events '''
        
        # log
        log.info("thread {0} starting".format(self.name))
        
        while self.goOn:
            
            with self.dataLock:
                
                if not self.events:
                    log.info("end of simulation at ASN={0}".format(self.asn))
                    break
                
                # make sure we are in the future
                assert self.events[0][0] >= self.asn

                # call callbacks at this ASN (NOT monitoring)
                i = 0
                while True:
                    if self.events[i][0] != self.asn:
                        break
                    # last element in tuple of uniqueTag is 'monitoring'/'sendData'/'DIO'/activeCell'
                    if self.events[i][2][-1] != 'monitoring':
                        (_,cb,_) = self.events.pop(i)
                        cb()
                    else:
                        i += 1
                
                # count scheduled cells and schedule collisions after 'activeCell' called
                self._countSchedule()
                
                # tell the propagation engine to propagate
                self.propagation.propagate()
                
                # call remainder callbacks (i.e. monitoring)
                while True:
                    if self.events[0][0]!=self.asn:
                        break
                    (_,cb,_) = self.events.pop(0)
                    cb()
                
                cycle = int(self.asn/self.settings.slotframeLength)
                if self.asn%self.settings.slotframeLength==self.settings.slotframeLength-1: # end of each cycle
                    print('Run num: {0} cycle: {1}'.format(self.runNum, cycle))
                    
                    numGeneratedPkts   = self._countGeneratedPackets()
                    numPacketsInQueue  = self._countPacketsInQueue()
                    numOverflow        = self._countQueueFull()
                    numPacketsReached  = self.motes[0].getStats()['dataReceived']
                    avgQueueDelay      = 0
                    if self.queueDelays:
                        avgQueueDelay  = sum(self.queueDelays)/float(len(self.queueDelays))
                    timeBetweenOTFevents=[]
                    avgTimeBetweenOTFevents=0
                    for mote in self.motes:
                        if mote.timeBetweenOTFevents:
                            timeBetweenOTFevents+=[(sum(mote.timeBetweenOTFevents)+self.getAsn()-mote.asnOTFevent)/(len(mote.timeBetweenOTFevents)+1.0)]
                    if timeBetweenOTFevents:
                        avgTimeBetweenOTFevents=sum(timeBetweenOTFevents)/len(timeBetweenOTFevents)
                    if numGeneratedPkts-numPacketsInQueue > 0:
                        e2ePDR         = float(numPacketsReached)/float(numGeneratedPkts-numPacketsInQueue)
                    else:
                        e2ePDR         = 0.0
                    if numPacketsReached > 0:
                        avgLatency     = float(self.motes[0].accumLatency)/float(numPacketsReached)
                    else:
                        avgLatency     = 0.0
                    self._fileWriteRun({
                        'runNum':                          self.runNum,
                        'cycle':                           cycle,
                        'numAccumScheduledCells':          self.numAccumScheduledCells,
                        'numAccumScheduledCollisions':     self.numAccumScheduledCollisions,
                        'numAccumNoPktAtNSC':              self.propagation.numAccumNoPktAtNSC,
                        'numAccumPktAtNSC':                self.propagation.numAccumPktAtNSC,
                        'numAccumSuccessAtNSC':            self.propagation.numAccumSuccessAtNSC,
                        'numAccumNoPktAtSC':               self.propagation.numAccumNoPktAtSC,
                        'numAccumPktAtSC':                 self.propagation.numAccumPktAtSC,
                        'numAccumSuccessAtSC':             self.propagation.numAccumSuccessAtSC,
                        'numGeneratedPkts':                numGeneratedPkts,
                        'numPacketsReached':               numPacketsReached,
                        'numPacketsInQueue':               numPacketsInQueue,
                        'numOverflow':                     numOverflow,
                        'e2ePDR':                          e2ePDR,
                        'avgLatency':                      avgLatency,
                        'avgQueueDelay':                   avgQueueDelay,
                        'avgTimeBetweenOTFevents':         avgTimeBetweenOTFevents,
                    })
                    self.propagation.initStats()
                
                # stop after numCyclesPerRun cycles
                if cycle==self.settings.numCyclesPerRun:
                    self._fileWriteTopology()
                    self.goOn=False
                
                # update the current ASN
                self.asn += 1
        
        # log
        log.info("thread {0} ends".format(self.name))
    
    #======================== public ==========================================
    
    #=== scheduling
    
    def scheduleIn(self,delay,cb,uniqueTag=None):
        ''' used to generate events. Puts an event to the queue '''
        
        with self.dataLock:
            asn = int(self.asn+(float(delay)/float(self.settings.slotDuration)))
            
            self.scheduleAtAsn(asn,cb,uniqueTag)
    
    def scheduleAtAsn(self,asn,cb,uniqueTag=None):
        ''' schedule an event at specific ASN '''
        
        with self.dataLock:
            
            # make sure we are scheduling in the future
            assert asn>self.asn
            
            # remove all events with same uniqueTag
            if uniqueTag:
                i = 0
                while i<len(self.events):
                    (a,c,t) = self.events[i]
                    # remove the future event but do not remove events at the current asn
                    if (t==uniqueTag) and (a > self.asn):
                        del self.events[i]
                    else:
                        i += 1
            
            # find correct index in schedule
            i = 0
            found = False
            while found==False:
                if (i>=len(self.events) or self.events[i][0]>asn):
                    found = True
                else:
                    i += 1
            
            # add to schedule
            self.events.insert(i,(asn,cb,uniqueTag))
    
    def removeEvent(self,uniqueTag,exceptCurrentASN=False):
        i = 0
        with self.dataLock:
            while i<len(self.events):
                (a,c,t) = self.events[i]
                if not exceptCurrentASN:
                    if t==uniqueTag:
                        del self.events[i]
                    else:
                        # only increment when not removing
                        i += 1
                else: # events at current asn are not removed
                    if t==uniqueTag and a>self.asn:
                        del self.events[i]
                    else:
                        # only increment when not removing
                        i += 1
    
    #=== getters/setters
    
    def getAsn(self):
        with self.dataLock:
            return self.asn
    
    #======================== private =========================================
    
    def _fileWriteRun(self,elems):
        output          = []
        
        # columnNames
        if not self.columnNames:
            self.columnNames = sorted(elems.keys())
            output     += ['\n# '+' '.join(self.columnNames)]
        
        # dataline
        formatString    = ' '.join(['{{{0}:>{1}}}'.format(i,len(k)) for (i,k) in enumerate(self.columnNames)])
        formatString   += '\n'
        output         += [' '+formatString.format(*[elems[k] for k in self.columnNames])]
        
        # write to file
        with open(self.settings.getOutputFile(),'a') as f:
            f.write('\n'.join(output))
    
    def _fileWriteTopology(self):
        output  = []
        output += [
            '#pos runNum={0} {1}'.format(
                self.runNum,
                ' '.join(['{0}@({1:.5f},{2:.5f})@{3}'.format(mote.id,mote.x,mote.y,mote.rank) for mote in self.motes])
            )
        ]
        output += [
            '#links runNum={0} {1}'.format(
                self.runNum,
                ' '.join(['{0}-{1}@{2:.0f}dBm'.format(moteA,moteB,rssi) for (moteA,moteB,rssi) in self.topology.links])
            )
        ]
        output  = '\n'.join(output)
    
        with open(self.settings.getOutputFile(),'a') as f:
            f.write(output)
    
    def _countSchedule(self):
        # count scheduled cells and schedule collision at each asn
        
        with self.dataLock:
            
            # initialize at start of each cycle
            currentTs = self.asn % self.settings.slotframeLength
            if currentTs == 0:
                self.numAccumScheduledCells = 0
                self.numAccumScheduledCollisions = 0
                self.queueDelays=[]

            self.scheduledCells.clear()
            self.collisionCells.clear()
            self.inactivatedCells.clear() # store cells recently added by monitoring function but not activated yet
            for mote in self.motes:
                for (ts,ch,_) in mote.getTxCells():
                    if ts == currentTs:
                                                
                        activated = False
                        # check whether this cell is already activated
                        for tx in self.propagation.transmissions:
                            if tx['smac'] == mote:
                                activated = True
                                break
                        for no in self.propagation.notransmissions:
                            if no['smac'] == mote:
                                activated = True
                                break
                        
                        if not activated:
                            self.inactivatedCells.add((ts,ch))
                        elif (ts,ch) not in self.scheduledCells:
                            self.scheduledCells.add((ts,ch))
                        else:
                            self.collisionCells.add((ts,ch))

            self.numAccumScheduledCells += len(self.scheduledCells)
            self.numAccumScheduledCollisions += len(self.collisionCells)
                
    def _countPacketsInQueue(self):
        # count the number of packets in queues of all motes at current asn
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                numPkt += len(mote.txQueue)
            return numPkt
    
    def _countGeneratedPackets(self):
        # count the number of generated packets of all motes
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                stats = mote.getStats()
                numPkt += stats['dataGenerated']
            return numPkt

    def _countQueueFull(self):
        # count the number of generated packets of all motes
        
        with self.dataLock:
            numPkt = 0
            for mote in self.motes:
                stats = mote.getStats()
                numPkt += stats['dataQueueFull']
            return numPkt
    
    #======================== private =========================================
