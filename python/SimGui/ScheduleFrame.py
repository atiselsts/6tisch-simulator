#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('ScheduleFrame')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import Tkinter

from SimEngine             import SimEngine
from SimEngine.SimSettings import SimSettings as s

class ScheduleFrame(Tkinter.Frame):
    
    UPDATE_PERIOD      = 1000
    HEIGHT             = 200
    WIDTH              = 1000
    
    COLOR_OK           = "blue"
    COLOR_ERROR        = "red"
    
    def __init__(self,guiParent):
        
        # store params
        self.guiParent       = guiParent
        self.engine          = SimEngine.SimEngine()
        
        # variables
        self.cells           = []
        self.step            = min((self.WIDTH-10)/s().timeslots,(self.HEIGHT-10)/s().channels)
        
        # initialize the parent class
        Tkinter.Frame.__init__(
            self,
            self.guiParent,
            relief      = Tkinter.RIDGE,
            borderwidth = 1,
        )
        
        # GUI layout
        self.schedule = Tkinter.Canvas(self, width=self.WIDTH, height=self.HEIGHT)
        self.schedule.grid(row=0,column=0)
        self.schedule.after(self.UPDATE_PERIOD,self._updateGui)
        
        for ts in range(s().timeslots):
            self.cells.append([])
            for ch in range(s().channels):
                self.cells[ts] += [self.schedule.create_rectangle(self._cellCoordinates(ts,ch))]
    
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _updateGui(self):
        
        self._redrawSchedule()
        
        self.schedule.after(self.UPDATE_PERIOD,self._updateGui)
    
    def _redrawSchedule(self):
        
        # clear all colors
        for ts in self.cells:
            for c in ts:
                self.schedule.itemconfig(c, fill="")
        
        # color according to usage
        for m in self.engine.motes:
            for (ts,ch) in m.getTxCells():
                color = self.schedule.itemcget(self.cells[ts][ch], "fill")
                if not color:
                    self.schedule.itemconfig(self.cells[ts][ch], fill=self.COLOR_OK)
                else:
                    self.schedule.itemconfig(self.cells[ts][ch], fill=self.COLOR_ERROR)
    
    def _cellCoordinates(self,ts,ch):
    
        return (
            5+ts*self.step,
            5+ch*self.step,
            5+(ts+1)*self.step,
            5+(ch+1)*self.step,
        )