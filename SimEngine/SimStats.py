#!/usr/bin/python
'''
\brief Collects and logs statistics about the ongoing simulation.

\author Thomas Watteyne <watteyne@eecs.berkeley.edu>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
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
import Propagation

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
        self.propagation                    = Propagation.Propagation()
        
        # stats
        self.stats                          = {}
        self.columnNames                    = []
        
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
        
        # write statistics to output file
        self._fileWriteStats(
            dict(
                {
                    'runNum':              self.runNum,
                    'cycle':               cycle,
                }.items() +
                self._collectSumMoteStats().items()  +
                self._collectScheduleStats().items()
            )
        )
        
        #'numAccumScheduledCells':       self.numAccumScheduledCells,
        #'numAccumScheduledCollisions':  self.numAccumScheduledCollisions,
        #'numAccumNoPktAtNSC':           self.propagation.numAccumNoPktAtNSC,
        #'numAccumPktAtNSC':             self.propagation.numAccumPktAtNSC,
        #'numAccumSuccessAtNSC':         self.propagation.numAccumSuccessAtNSC,
        #'numAccumNoPktAtSC':            self.propagation.numAccumNoPktAtSC,
        #'numAccumPktAtSC':              self.propagation.numAccumPktAtSC,
        #'numAccumSuccessAtSC':          self.propagation.numAccumSuccessAtSC,
        #'numPacketsReached':            numPacketsReached,
        #'numOverflow':                  numOverflow,
        #'e2ePDR':                       e2ePDR,
        #'avgLatency':                   avgLatency,
        #'avgTimeBetweenOTFevents':      avgTimeBetweenOTFevents,
        
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
    
    def _collectSumMoteStats(self):
        returnVal = {}
        
        for mote in self.engine.motes:
            moteStats        = mote.getMoteStats()
            if not returnVal:
                returnVal    = moteStats
            else:
                for k in returnVal.keys():
                    returnVal[k] += moteStats[k]
        
        return returnVal
    
    def _collectScheduleStats(self):
        
        # compute the number of schedule collisions
        
        # Note that this cannot count past schedule collisions which have been relocated by 6top
        # as this is called at the end of cycle   
        scheduleCollisions = 0
        txCells = []
        for mote in self.engine.motes:
            for (ts,cell) in mote.schedule.items():
                (ts,ch) = (ts,cell['ch'])
                if cell['dir']==mote.DIR_TX:
                    if (ts,ch) in txCells:
                        scheduleCollisions += 1
                    else:
                        txCells += [(ts,ch)]
        
        return {'scheduleCollisions':scheduleCollisions}
    
    #=== writing to file
    
    def _fileWriteHeader(self):
        output          = []
        output         += ['## {0} = {1}'.format(k,v) for (k,v) in self.settings.__dict__.items() if not k.startswith('_')]
        output         += ['\n']
        output          = '\n'.join(output)
        
        with open(self.settings.getOutputFile(),'w') as f:
            f.write(output)
    
    def _fileWriteStats(self,stats):
        output          = []
        
        # columnNames
        if not self.columnNames:
            self.columnNames = sorted(stats.keys())
            output     += ['\n# '+' '.join(self.columnNames)]
        
        # dataline
        formatString    = ' '.join(['{{{0}:>{1}}}'.format(i,len(k)) for (i,k) in enumerate(self.columnNames)])
        formatString   += '\n'
        output         += ['  '+formatString.format(*[stats[k] for k in self.columnNames])]
        
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
                    links[(m,n)] = (m.getRSSI(n),m.getPDR(n))
                except KeyError:
                    pass
        output += [
            '#links runNum={0} {1}'.format(
                self.runNum,
                ' '.join(['{0}-{1}@{2:.0f}dBm@{3:.3f}'.format(moteA.id,moteB.id,rssi,pdr) for ((moteA,moteB),(rssi,pdr)) in links.items()])
            )
        ]
        output  = '\n'.join(output)
        
        with open(self.settings.getOutputFile(),'a') as f:
            f.write(output)