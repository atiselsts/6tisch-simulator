#!/usr/bin/python

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('ActionFrame')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import Tkinter

class ActionFrame(Tkinter.Frame):
    pass