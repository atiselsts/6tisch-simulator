    _________ _____  _____ _    _ 
   / /__   __/ ____|/ ____| |  | |
  / /_  | | | (___ | |    | |__| |
 | '_ \ | |  \___ \| |    |  __  |
 | (_) || |  ____) | |____| |  | |
  \___/ |_| |_____/ \_____|_|  |_|
                                  
                                  
June 2013.

This work has been carried out by:
    Thomas Watteyne (watteyne@eecs.berkeley.edu)
	Xavier Vilajosana (xvilajosana@eecs.berkeley.edu,
	                   xvilajosana@uoc.edu) 

Brief:
    Event driven simulator for TSCH schedules developed under IETF 6TSCH working group.

Requirements
    *Python 2.7 - http://www.python.org/download/releases/2.7/
	*Git client (e.g TortoiseGit for Windows or SmartGit for linux)

Install:
    *Install python
	*Clone simulator code. 
	    Find url here: https://bitbucket.org/6tsch/simulator

Run it:
    *Execute:
	   PATH_TO_SIMULATOR/simulator/python/bin/simpleSim/simpleSim.py

Contribute:
    *You can edit the code with any code editor, including vi, nano, emacs, sublime, notepad, eclipse+pydev, etc...
	*The simulator code is well documented and contributions are welcome. The core of the simulator  is structured as follows and can be found at SimEngine folder.
	   *Propagation: defines the propagation behaviour, Node transmissions and nodes waiting for a packet are queued. It matches collisions and handles transmission to nodes.
	   *Topology: Used to setup the network, the relation (links) between components. Also implements a propagation model based on the Friis equation and the Pister hack model. The later is used to setup PDR at each link.
	   *SimEngine: the event driven engine used to take action at each timeslot.
	   *Mote: The represetation of the state of a mote.
	   *SimSettings: settings component used to configure some parameters. Also simpleSim component contains some default configurations.
	   
V0.0 changeset:
       *Supported topologies: Tree,Random,Full mesh,min_distance,radius_based.
	   *Propagation: Friis model + Pister hack model
	   *Reallocation of cells when PDR drops
	   
	   
Issues and future contributions.
       *Add spanning tree topology (dijkstra)
	   *Add network trend and overall information using charts.
    https://bitbucket.org/6tsch/simulator/issues