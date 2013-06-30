#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('TopologyFrame')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import Tkinter

from SimEngine import SimEngine

class TopologyFrame(Tkinter.Frame):
    
    UPDATE_PERIOD      = 1000
    MOTE_SIZE          = 10
    HEIGHT             = 300
    WIDTH              = 1000
    
    def __init__(self,guiParent):
        
        # store params
        self.guiParent       = guiParent
        self.engine          = SimEngine.SimEngine()
        
        # variables
        self.motes           = {}
        
        # initialize the parent class
        Tkinter.Frame.__init__(
            self,
            self.guiParent,
            relief      = Tkinter.RIDGE,
            borderwidth = 1,
        )
        
        # GUI layout
        self.topology = Tkinter.Canvas(self, width=self.WIDTH, height=self.HEIGHT)
        self.topology.grid(row=0,column=0)
        self.topology.after(self.UPDATE_PERIOD,self._updateGui)
    
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _updateGui(self):
        
        self._redrawTopology()
        
        self.topology.after(self.UPDATE_PERIOD,self._updateGui)
    
    def _redrawTopology(self):
        for m in self.engine.motes:
            if m not in self.motes:
                # create
                self.motes[m] = self.topology.create_oval(self._moteCoordinates(m),fill='blue')
            else:
                # move
                pass
    
    def _moteCoordinates(self,m):
        (x,y) = m.getLocation()
        return (
            self.WIDTH*x-self.MOTE_SIZE/2,
            self.HEIGHT*y-self.MOTE_SIZE/2,
            self.WIDTH*x+self.MOTE_SIZE/2,
            self.HEIGHT*y+self.MOTE_SIZE/2,
        )