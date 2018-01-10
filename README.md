The 6TiSCH Simulator
====================

Brought to you by:

* Thomas Watteyne (watteyne@eecs.berkeley.edu)
* Kazushi Muraoka (k-muraoka@eecs.berkeley.edu)
* Nicola Accettura (nicola.accettura@eecs.berkeley.edu)
* Xavier Vilajosana (xvilajosana@eecs.berkeley.edu)
* Mališa Vučinić (malisa.vucinic@inria.fr)
* Esteban Municio (esteban.municio@uantwerpen.be)
* Glenn Daneels (glenn.daneels@uantwerpen.be)

You are on the development branch, containing latest and hottest updates to the simulator, following the work in the 6TiSCH standardization group.
This comes at a price that it may not be most thoroughly tested, and bugs are to be expected.
If you encounter some, please report them with a detailed bug report containing the parameters you used to run the simulation, through the Bitbucket issue tracker.

If you are looking for a more stable, but outdated version, please check out the master branch.

Scope
-----

6TiSCH is an active IETF standardization working group which defines mechanisms to build and maintain communication schedules in tomorrow's Internet of (Important) Things. This simulator allows you to measure the performance of those different mechanisms under different conditions.

What is simulated:

* protocols
    * IEEE802.15.4e-2012 TSCH (http://standards.ieee.org/getieee802/download/802.15.4e-2012.pdf)
    * RPL (https://tools.ietf.org/html/rfc6550) with downstream traffic using source routing
    * 6top (https://tools.ietf.org/html/draft-ietf-6tisch-6top-protocol-09)
    * Minimal Scheduling Function (https://tools.ietf.org/html/draft-chang-6tisch-msf-00)
* join process with initial synchronization to the first received Enhanced Beacon.
* the "Pister-hack" propagation model with collisions
* the energy consumption model taken from
    * [A Realistic Energy Consumption Model for TSCH Networks](http://ieeexplore.ieee.org/xpl/login.jsp?tp=&arnumber=6627960&url=http%3A%2F%2Fieeexplore.ieee.org%2Fiel7%2F7361%2F4427201%2F06627960.pdf%3Farnumber%3D6627960). Xavier Vilajosana, Qin Wang, Fabien Chraim, Thomas Watteyne, Tengfei Chang, Kris Pister. IEEE Sensors, Vol. 14, No. 2, February 2014.


More about 6TiSCH:

| what             | where                                                               |
|------------------|---------------------------------------------------------------------|
| charter          | http://tools.ietf.org/wg/6tisch/charters                            |
| data tracker     | http://tools.ietf.org/wg/6tisch/                                    |
| mailing list     | http://www.ietf.org/mail-archive/web/6tisch/current/maillist.html   |
| source           | https://bitbucket.org/6tisch/                                       |

Gallery
-------

|  |  |  |
|--|--|--|
| ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_topology.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_timelines.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/gui.png) |

Installation
------------

* Install Python 2.7
* Clone or download this repository
* To plot the graphs, you need Matplotlib and scipy. On Windows, Anaconda (http://continuum.io/downloads) is a good on-stop-shop.

Running
-------

Change directory to `bin`.
Use `python runSimOneCPU.py --help` for a list of simulation parameters. In particular, use `--gui` for a graphical interface.

* Run a simulation: `python runSimOneCPU.py`
* Use one of the helper plot\*.py scripts to generate fancy graphs. 

Code Organization
-----------------

* `bin/`: the scripts for you to run
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
