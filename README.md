The 6TiSCH Simulator
====================

Brought to you by:

* Thomas Watteyne (watteyne@eecs.berkeley.edu)
* Kazushi Muraoka (k-muraoka@eecs.berkeley.edu)
* Nicola Accettura (nicola.accettura@eecs.berkeley.edu)
* Xavier Vilajosana (xvilajosana@eecs.berkeley.edu)

Goal and scope
--------------

6TiSCH is an active IETF standardization working group which defines mechanisms to build and maintain communication schedules in tomorrow's Internet of (Important) Things. This simulator allows you to measure the performance of those different mechanisms under different conditions.

What is simulated:

* IEEE802.15.4e-2012 TSCH (http://standards.ieee.org/getieee802/download/802.15.4e-2012.pdf)
* RPL (http://tools.ietf.org/html/rfc6550)
* 6top (http://tools.ietf.org/html/draft-wang-6tisch-6top-sublayer)
* On-The-Fly scheduling (http://tools.ietf.org/html/draft-dujovne-6tisch-on-the-fly)

What is *not* simulated:

* downstream traffic

Installation
------------

* Install Python 2.7
* Clone or download this repository
* To plot the graphs, you need Matplotlib and scipy. On Windows, Anaconda (http://continuum.io/downloads) is a good on-stop-shop.

Running
-------

* Run a simulation: `bin/simpleSim/runSim.py`
* Plot fancy graphs: `bin/simpleSim/plotStuff.py`

Use `bin/simpleSim/runSim.py --help` for a list of simulation parameters. In particular, use `--gui` for a graphical interface.

Example output
--------------

By default, the simulator output a timeline for each run, as well as some data about the topology.

|  |  |
|--|--|
| ![](examples/run_0_topology.png) | ![](examples/run_0_timelines.png) |

Code Organization
-----------------

* `bin/`: the script for you to run
* `SimEngine/`: the simulator
    * `Mote.py`: Models a 6TiSCH mote running the different standards listed above.
    * `Propagation.py`: Wireless propagation model.
    * `SimEngine.py`: Event-driven simulation engine at the core of this simulator.
    * `SimSettings.py`: Data store for all simulation settings.
    * `SimStats.py`: Periodically collects statistics and writes those to a file.
    * `Topology.py`: creates a topology of the motes in the network.
* `SimGui/`: the graphical user interface to the simulator

Issues and bugs
---------------

* Report at https://bitbucket.org/6tsch/simulator/issues
