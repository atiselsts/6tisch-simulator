#!/usr/bin/python
'''
\brief Collects and logs statistics about the ongoing simulation.

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
log = logging.getLogger('SimStats')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

#============================ imports =========================================

import SimEngine
import SimSettings

#============================ defines =========================================

#============================ body ============================================

class SimStats(object):
    
    #===== start singleton
    _instance      = None
    _init          = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimStats,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    #===== end singleton
    
    def __init__(self,runNum):
        
        #===== start singleton
        if self._init:
            return
        self._init = True
        #===== end singleton
        
        # store params
        self.runNum                         = runNum
        
        # local variables
        self.engine                         = SimEngine.SimEngine()
        self.settings                       = SimSettings.SimSettings()
        
        # stats
        self.stats                          = {}
        
        # start file
        if self.runNum==0:
            self._fileWriteHeader()
        
        # schedule actions
        self.engine.scheduleAtStart(
            cb          = self._actionStart,
        )
        self.engine.scheduleAtAsn(
            asn         = self.engine.getAsn()+self.settings.slotframeLength-1,
            cb          = self._actionEndCycle,
            uniqueTag   = (None,'_actionEndCycle'),
        )
        self.engine.scheduleAtEnd(
            cb          = self._actionEnd,
        )
    
    def destroy(self):
        # destroy my own instance
        self._instance                      = None
        self._init                          = False
    
    #======================== private =========================================
    
    def _actionStart(self):
        '''Called once at beginning of the simulation.'''
        pass
    
    def _actionEndCycle(self):
        '''Called at each end of cyle.'''
        
        cycle = int(self.engine.getAsn()/self.settings.slotframeLength)
        
        print('      cycle: {0}/{1}'.format(cycle,self.settings.numCyclesPerRun-1))
        '''
        # collect statistics
        self._collectStats()
        
        # write statistics to output file
        self._fileWriteStats({
            'runNum':                       self.runNum,
            'cycle':                        cycle,
            'numAccumScheduledCells':       self.numAccumScheduledCells,
            'numAccumScheduledCollisions':  self.numAccumScheduledCollisions,
            'numAccumNoPktAtNSC':           self.propagation.numAccumNoPktAtNSC,
            'numAccumPktAtNSC':             self.propagation.numAccumPktAtNSC,
            'numAccumSuccessAtNSC':         self.propagation.numAccumSuccessAtNSC,
            'numAccumNoPktAtSC':            self.propagation.numAccumNoPktAtSC,
            'numAccumPktAtSC':              self.propagation.numAccumPktAtSC,
            'numAccumSuccessAtSC':          self.propagation.numAccumSuccessAtSC,
            'numGeneratedPkts':             numGeneratedPkts,
            'numPacketsReached':            numPacketsReached,
            'numPacketsInQueue':            numPacketsInQueue,
            'numOverflow':                  numOverflow,
            'e2ePDR':                       e2ePDR,
            'avgLatency':                   avgLatency,
            'avgQueueDelay':                avgQueueDelay,
            'avgTimeBetweenOTFevents':      avgTimeBetweenOTFevents,
        })
        
        # reset statistics
        self.propagation.initStats()
        '''
        
        # schedule next statistics collection
        self.engine.scheduleAtAsn(
            asn         = self.engine.getAsn()+self.settings.slotframeLength,
            cb          = self._actionEndCycle,
            uniqueTag   = (None,'_actionEndCycle'),
        )
    
    def _actionEnd(self):
        '''Called once at end of the simulation.'''
        self._fileWriteTopology()
    
    #=== collecting statistics
    
    def _collectStats(self):
        
        totalDataGenerated   = sum([mote.getStats()['dataGenerated'] for mote in self.engine.motes])
        totalDataReceived    = sum([mote.getStats()['dataGenerated'] for mote in self.engine.motes])
        
        totalTxQueueLen      = sum([len(mote.txQueue)                for mote in self.engine.motes])
        totalDataQueueFull   = sum([mote.getStats()['dataQueueFull'] for mote in self.engine.motes])
        
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
    
    
    #=== writing to file
    
    def _fileWriteHeader(self):
        output          = []
        output         += ['## {0} = {1}'.format(k,v) for (k,v) in self.settings.__dict__.items() if not k.startswith('_')]
        output         += ['\n']
        output          = '\n'.join(output)
        
        with open(self.settings.getOutputFile(),'a') as f:
            f.write(output)
    
    def _fileWriteStats(self,elems):
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
                ' '.join(['{0}@({1:.5f},{2:.5f})@{3}'.format(mote.id,mote.x,mote.y,mote.rank) for mote in self.engine.motes])
            )
        ]
        links = {}
        for m in self.engine.motes:
            for n in self.engine.motes:
                if m==n:
                    continue
                if (n,m) in links:
                    continue
                try:
                    links[(m,n)] = m.getPDR(n)
                except KeyError:
                    pass
        output += [
            '#links runNum={0} {1}'.format(
                self.runNum,
                ' '.join(['{0}-{1}@{2:.0f}dBm'.format(moteA,moteB,rssi) for ((moteA,moteB),rssi) in links.items()])
            )
        ]
        output  = '\n'.join(output)
        
        with open(self.settings.getOutputFile(),'a') as f:
            f.write(output)