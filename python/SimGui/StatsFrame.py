#!/usr/bin/python

'''
 @authors:
       Thomas Watteyne    <watteyne@eecs.berkeley.edu>    
'''

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('StatsFrame')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import Tkinter

from SimEngine             import SimEngine
from SimEngine.SimSettings import SimSettings as s

class StatsFrame(Tkinter.Frame):
    
    UPDATE_PERIOD = 1000
    
    def __init__(self,guiParent):
        
        # store params
        self.guiParent       = guiParent
        self.engine          = SimEngine.SimEngine()
        
        # initialize the parent class
        Tkinter.Frame.__init__(
            self,
            self.guiParent,
            relief      = Tkinter.RIDGE,
            borderwidth = 1,
        )
        
        # GUI layout
        self.info   = Tkinter.Label(self,justify=Tkinter.LEFT)
        self.info.grid(row=0,column=0)
        
        self.cell  = Tkinter.Label(self,justify=Tkinter.LEFT)
        self.cell.grid(row=0,column=1)
        
        self.mote  = Tkinter.Label(self,justify=Tkinter.LEFT)
        self.mote.grid(row=0,column=2)
        
        self.link  = Tkinter.Label(self,justify=Tkinter.LEFT)
        self.link.grid(row=0,column=3)
        
        # schedule first update
        self.after(self.UPDATE_PERIOD,self._updateGui)
        
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _updateGui(self):
        
        self._redrawInfo()
        self._redrawCell()
        self._redrawMote()
        self._redrawLink()
        
        self.after(self.UPDATE_PERIOD,self._updateGui)
    
    def _redrawInfo(self):
        
        asn = self.engine.getAsn()
        output  = []
        output += ["info:"]
        output += ["ASN: {0}".format(asn)]
        output += ["time: {0}".format(asn*s().slotDuration)]
        output  = '\n'.join(output)
        self.info.configure(text=output)
    
    def _redrawCell(self):
        
        cell = self.guiParent.selectedCell
        output  = []
        output += ["Cell:"]
        if cell:
            ts = cell[0]
            ch = cell[1]
            output += ["ts={0} ch={1}".format(ts,ch)]
            for mote in self.engine.motes:
                cellStats = mote.getCellStats(ts,ch)
                if cellStats:
                    output += ["mote {0}:".format(mote.id)]
                    for (k,v) in cellStats.items():
                        output += ["- {0}: {1}".format(k,v)]
        else:
            output += ["No cell selected."]
        output  = '\n'.join(output)
        self.cell.configure(text=output)
    
    def _redrawMote(self):
        
        mote = self.guiParent.selectedMote
        output  = []
        output += ["Mote:"]
        if mote:
            output += ["id={0}".format(mote.id)]
            stats   = mote.getStats()
            for (k,v) in stats.items():
                output += ["- {0}: {1}".format(k,v)]
        else:
            output += ["No mote selected."]
        output  = '\n'.join(output)
        self.mote.configure(text=output)
        
    def _redrawLink(self):
        
        link = self.guiParent.selectedLink
        output  = []
        output += ["Link:"]
        if link:
            fromMote = link[0]
            toMote   = link[1]
            output += ["{0}->{1}".format(fromMote.id,toMote.id)]
        else:
            output += ["No link selected."]
        output  = '\n'.join(output)
        self.link.configure(text=output)
        