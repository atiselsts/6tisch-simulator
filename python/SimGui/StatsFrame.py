#!/usr/bin/python

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
        Tkinter.Label(self,text="ASN").grid(row=0,column=0)
        self.asn   = Tkinter.Label(self)
        self.asn.grid(row=0,column=1)
        
        Tkinter.Label(self,text="time").grid(row=1,column=0)
        self.time  = Tkinter.Label(self)
        self.time.grid(row=1,column=1)
        
        # schedule first update
        self.after(self.UPDATE_PERIOD,self._updateGui)
        
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _updateGui(self):
        
        self._redrawStats()
        
        self.after(self.UPDATE_PERIOD,self._updateGui)
    
    def _redrawStats(self):
        asn = self.engine.getAsn()
        self.asn.configure(text="{0:x}".format(asn))
        self.time.configure(text="{0}".format(asn*s().slotDuration))