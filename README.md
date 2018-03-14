The 6TiSCH Simulator
====================

Core Developers:

* Mališa Vučinić (malisa.vucinic@inria.fr)
* Yasuyuki Tanaka (yasuyuki.tanaka@inria.fr) - Sensei
* Keoma Brun-Laguna (keoma.brun@inria.fr)

Contributers:

* Thomas Watteyne (thomas.watteyne@inria.fr)
* Kazushi Muraoka (k-muraoka@eecs.berkeley.edu)
* Nicola Accettura (nicola.accettura@eecs.berkeley.edu)
* Xavier Vilajosana (xvilajosana@eecs.berkeley.edu)
* Esteban Municio (esteban.municio@uantwerpen.be)
* Glenn Daneels (glenn.daneels@uantwerpen.be)

Scope
-----

6TiSCH is an active IETF standardization working group that defines mechanisms to build and maintain communication schedules in tomorrow's Internet of (Important) Things.
This simulator allows you to measure the performance of those different mechanisms under different conditions.

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

Getting Started
---------------

1. Download the code (in this case, cloning `develop` branch):
   ```
   $ git clone -b develop https://bitbucket.org/6tisch/simulator.git
   ```
2. Move down to `bin` directory:
   ```
   $ cd simulator/bin
   ```
3. Execute runSim.py:
   ```
   $ python runSim.py
   ```
    * You'll have raw output data under `bin/simData` directory.
    * You can specify configuration parameters such as slot length and application packet interval if you want. `$ python runSim.py --help` shows available options.
4. Execute plotStuff.py to see the results:
   ```
   $ python plotStuff.py
   ```
    * You’ll have charts derived from the data under `bin/simData` directory.
    * You need to define your simulation scenarios and identify necessary parameter sets in order to have meaningful results or charts.

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

Development Workflow and Coding Style
---------------

* We follow the standard Git branching workflow: https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows
* The code should follow the PEP8 coding style: https://www.python.org/dev/peps/pep-0008/

Running Simulation on Traces
---------------

## How to Run on Traces

`python runSim.py --trace tracefile.csv`

## Trace Format

We follow the CTR format, specified in: https://github.com/keomabrun/dense_connectivity_datasets
