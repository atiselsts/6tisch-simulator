    _________    _____  _____ _    _    
   / /__   __|_ / ____|/ ____| |  | |   
  / /_  | |  (_) (___ | |    | |__| |
 | '_ \ | |  | |\___ \| |    |  __  |
 | (_) || |  | |____) | |____| |  | |
  \___/ |_|  |_|_____/ \_____|_|  |_|

The 6TiSCH simulator.

Authors
-------

* Thomas Watteyne <watteyne@eecs.berkeley.edu>
* Kazushi Muraoka <k-muraoka@eecs.berkeley.edu>
* Nicola Accettura <nicola.accettura@eecs.berkeley.edu>
* Xavier Vilajosana <xvilajosana@eecs.berkeley.edu>

Event driven simulator for TSCH schedules developed under IETF 6TSCH working group.

Requirements
------------

* Python 2.7 - http://www.python.org/download/releases/2.7/
* Git client (e.g TortoiseGit for Windows or SmartGit for linux)

Installation
------------

* Install python
* Clone simulator code.

Running
-------

Execute: `bin/simpleSim/simpleSim.py`

Contribute
----------

* You can edit the code with any code editor, including vi, nano, emacs, sublime, notepad, eclipse+pydev, etc...
* The simulator code is well documented and contributions are welcome. The core of the simulator is structured as follows and can be found in the `SimEngine` directory.
    * `Propagation` defines the propagation behaviour, Node transmissions and nodes waiting for a packet are queued. It matches collisions and handles transmission to nodes.
    * `Topology` Used to setup the network, the relation (links) between components. Also implements a propagation model based on the Friis equation and the Pister hack model. The later is used to setup PDR at each link.
    * `SimEngine` the event driven engine used to take action at each timeslot.
    * `Mote` The represetation of the state of a mote.
    * `SimSettings` settings component used to configure some parameters. Also simpleSim component contains some default configurations.

Issues and wishlist
-------------------

* See https://bitbucket.org/6tsch/simulator/issues