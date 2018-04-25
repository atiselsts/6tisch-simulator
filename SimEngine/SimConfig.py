#!/usr/bin/python
"""
\brief Holds the overall configuration of a simulation.

Configuration is read from a configuration file, and accessible in dotted
notation:

   simconfig.execution.numCores

This configuration contains the different steps of a simulation, including
what gets called after the simulation is done.
A single configuration turns into multiple SimSettings, for each combination
of settings.

\author Thomas Watteyne <thomas.watteyne@inria.fr>
"""

# =========================== imports =========================================

import json

# =========================== defines =========================================

# =========================== body ============================================

class DotableDict(dict):

    __getattr__= dict.__getitem__

    def __init__(self, d):
        self.update(**dict((k, self.parse(v))
                           for k, v in d.iteritems()))

    @classmethod
    def parse(cls, v):
        if isinstance(v, dict):
            return cls(v)
        elif isinstance(v, list):
            return [cls.parse(i) for i in v]
        else:
            return v

class SimConfig(dict):

    def __init__(self, configfile=None):

        # store params
        self.configfile = configfile

        # read config file
        with open(self.configfile, 'r') as file:
            self.config = DotableDict(json.loads(file.read()))

    def __getattr__(self, name):
        return getattr(self.config, name)
