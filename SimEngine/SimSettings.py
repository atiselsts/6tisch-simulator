#!/usr/bin/python
"""
\brief Container for the settings of a simulation run.

\author Thomas Watteyne <thomas.watteyne@inria.fr>
\author Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
\author Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
\author Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>
"""

# =========================== imports =========================================

import os

# =========================== defines =========================================

# =========================== body ============================================

class SimSettings(object):

    # ==== start singleton
    _instance      = None
    _init          = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SimSettings, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    # ==== end singleton

    def __init__(self, cpuID=None, run_id=None, failIfNotInit=False, **kwargs):

        if failIfNotInit and not self._init:
            raise EnvironmentError('SimSettings singleton not initialized.')

        # ==== start singleton
        cls = type(self)
        if cls._init:
            return
        cls._init = True
        # ==== end singleton

        # store params
        self.cpuID                          = cpuID
        self.run_id                         = run_id

        self.__dict__.update(kwargs)

    def setStartTime(self, startTime):
        self.startTime       = startTime

    def setCombinationKeys(self, combinationKeys):
        self.combinationKeys = combinationKeys

    def getOutputFile(self):
        # directory
        dirname   = os.path.join(
            'simData',
            self.startTime,
            '_'.join(['{0}_{1}'.format(k, getattr(self, k)) for k in self.combinationKeys]),
        )
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except OSError, e:
                if e.errno == os.errno.EEXIST:
                    # FIXME: handle this race condition properly
                    # Another core/CPU has already made this directory
                    pass
                else:
                    raise

        # file
        if self.cpuID is None:
            tempname         = 'output.dat'
        else:
            tempname         = 'output_cpu{0}.dat'.format(self.cpuID)
        datafilename         = os.path.join(dirname, tempname)

        return datafilename

    def destroy(self):
        cls = type(self)
        cls._instance       = None
        cls._init           = False
