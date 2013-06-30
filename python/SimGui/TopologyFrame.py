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
        self.guiParent  = guiParent
        self.engine     = SimEngine.SimEngine()
        
        # variables
        self.motes      = {}
        self.links      = {}
        
        # initialize the parent class
        Tkinter.Frame.__init__(
            self,
            self.guiParent,
            relief      = Tkinter.RIDGE,
            borderwidth = 1,
        )
        
        # GUI layout
        self.topology   = Tkinter.Canvas(self, width=self.WIDTH, height=self.HEIGHT)
        self.topology.grid(row=0,column=0)
        self.topology.after(self.UPDATE_PERIOD,self._updateGui)
    
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _updateGui(self):
        
        self._redrawTopology()
        
        self.topology.after(self.UPDATE_PERIOD,self._updateGui)
    
    def _redrawTopology(self):
        
        #===== draw links
        
        # mark all links to remove
        for link in self.links:
            self.topology.itemconfig(link,tags=("deleteMe",))
        
        # go over all links in the network
        for mote in self.engine.motes:
            for (ts,ch,neighbor) in mote.getTxCells():
                if (mote,neighbor) not in self.links:
                    # create
                    self.links[(mote,neighbor)] = self.topology.create_line(self._linkCoordinates(mote,neighbor))
                else:
                    # move
                    self.topology.dtag(self.links[(mote,neighbor)],"deleteMe")
                    # TODO:move
        
        # remove links still marked
        for mote in self.topology.find_withtag("deleteMe"):
            self.topology.delete(mote)
        
        #===== draw motes
        
        # mark all motes to remove
        for mote in self.motes:
            self.topology.itemconfig(mote,tags=("deleteMe",))
        
        # go over all motes in the network
        for m in self.engine.motes:
            if m not in self.motes:
                # create
                self.motes[m] = self.topology.create_oval(self._moteCoordinates(m),fill='blue')
            else:
                # move
                self.topology.dtag(self.motes[m],"deleteMe")
                # TODO: move
        
        # remove motes still marked
        for mote in self.topology.find_withtag("deleteMe"):
            self.topology.delete(mote)
    
    #======================== helpers =========================================
    
    def _moteCoordinates(self,m):
        (x,y) = m.getLocation()
        return (
            self.WIDTH*x-self.MOTE_SIZE/2,
            self.HEIGHT*y-self.MOTE_SIZE/2,
            self.WIDTH*x+self.MOTE_SIZE/2,
            self.HEIGHT*y+self.MOTE_SIZE/2,
        )
    
    def _linkCoordinates(self,fromMote,toMote):
        (fromX, fromY)  = fromMote.getLocation()
        (toX,   toY)    = toMote.getLocation()
        return (
            fromX*self.WIDTH,
            fromY*self.HEIGHT,
            toX*self.WIDTH,
            toY*self.HEIGHT,
        )
        