# The 6TiSCH Simulator - [![Build Status](https://openwsn-builder.paris.inria.fr/buildStatus/icon?job=6TiSCH%20Simulator/develop)](https://openwsn-builder.paris.inria.fr/job/6TiSCH%20Simulator/job/develop/)

Core Developers:

* Mališa Vučinić (malisa.vucinic@inria.fr)
* Yasuyuki Tanaka (yasuyuki.tanaka@inria.fr) - Sensei
* Keoma Brun-Laguna (keoma.brun@inria.fr)
* Thomas Watteyne (thomas.watteyne@inria.fr)

Contributers:

* Kazushi Muraoka (k-muraoka@eecs.berkeley.edu)
* Nicola Accettura (nicola.accettura@eecs.berkeley.edu)
* Xavier Vilajosana (xvilajosana@eecs.berkeley.edu)
* Esteban Municio (esteban.municio@uantwerpen.be)
* Glenn Daneels (glenn.daneels@uantwerpen.be)

## Scope

6TiSCH is an IETF standardization working group that defines a complete protocol stack for ultra reliable ultra low-power wireless mesh networks.
This simulator implements the 6TiSCH protocol stack, exactly as it is standardized.
It allows you to measure the performance of a 6TiSCH network under different conditions.

Simulated protocol stack

|                                                                                                              |                                          |
|--------------------------------------------------------------------------------------------------------------|------------------------------------------|
| [RFC6550](https://tools.ietf.org/html/rfc6550)                                                               | RPL, non-storing mode                    |
| [draft-watteyne-6lo-minimal-fragment-01](https://tools.ietf.org/html/draft-watteyne-6lo-minimal-fragment-01) | 6LoWPAN Fragment Forwarding              |
| [RFC6282](https://tools.ietf.org/html/rfc6282), [RFC4944](https://tools.ietf.org/html/rfc4944)               | 6LoWPAN                                  |
| [draft-chang-6tisch-msf-01](https://tools.ietf.org/html/draft-chang-6tisch-msf-01)                           | 6TiSCH Minimal Scheduling Function (MSF) |
| [draft-ietf-6tisch-minimal-security-05](https://tools.ietf.org/html/draft-ietf-6tisch-minimal-security-05)   | 6TiSCH Minimal Security (join process)   |
| [draft-ietf-6tisch-6top-protocol-11](https://tools.ietf.org/html/draft-ietf-6tisch-6top-protocol-11)         | 6TiSCH 6top Protocol (6P)                |
| [IEEE802.15.4-2015](https://ieeexplore.ieee.org/document/7460875/)                                           | IEEE802.15.4 TSCH                        |

* propagation models
    * Pister-hack
    * k7: trace-based propagation
* miscellaneous
    * Energy Consumption model taken from
        * [A Realistic Energy Consumption Model for TSCH Networks](http://ieeexplore.ieee.org/xpl/login.jsp?tp=&arnumber=6627960&url=http%3A%2F%2Fieeexplore.ieee.org%2Fiel7%2F7361%2F4427201%2F06627960.pdf%3Farnumber%3D6627960). Xavier Vilajosana, Qin Wang, Fabien Chraim, Thomas Watteyne, Tengfei Chang, Kris Pister. IEEE Sensors, Vol. 14, No. 2, February 2014.

## Installation

* Install Python 2.7
* Clone or download this repository
* To plot the graphs, you need Matplotlib and scipy. On Windows, Anaconda (http://continuum.io/downloads) is a good one-stop-shop.

## Getting Started

1. Download the code:
   ```
   $ git clone https://bitbucket.org/6tisch/simulator.git
   ```
1. Install the Python dependencies:
   `cd simulator` and `pip install -r requirements.txt`
1. Move down to `bin` directory:
   ```
   $ cd bin
   ```
1. Execute runSim.py:
   ```
   $ python runSim.py
   ```
    * raw output data is in `bin/simData/`.
    * raw charts are in `bin/simPlots/`.
1. Take a look at `bin/config.json` to see the configuration of the simulations you just ran.

## Code Organization

* `bin/`: the scripts for you to run
* `example/`: example plots, shown in the documentation
* `SimEngine/`: the simulator
    * `Mote.py`: Models a 6TiSCH mote running the different standards listed above.
    * `Propagation.py`: Wireless propagation model.
    * `sf.py`: The scheduling function.
    * `SimConfig.py`: The overall configuration of running a simulation campaign.
    * `SimEngine.py`: Event-driven simulation engine at the core of this simulator.
    * `SimSettings.py`: The settings of a single simulation, part of a simulation campaign.
    * `SimStats.py`: Periodically collects statistics and writes those to a file.
    * `Topology.py`: creates a topology of the motes in the network.
* `SimGui/`: the graphical user interface to the simulator
* `tests/`: the unit tests, run using `pytest`
* `traces/`: example `k7` connectivity traces


## About 6TiSCH

| what         | where                                                                                                                                  |
|--------------|----------------------------------------------------------------------------------------------------------------------------------------|
| charter      | [http://tools.ietf.org/wg/6tisch/charters](http://tools.ietf.org/wg/6tisch/charters)                                                   |
| data tracker | [http://tools.ietf.org/wg/6tisch/](http://tools.ietf.org/wg/6tisch/)                                                                   |
| mailing list | [http://www.ietf.org/mail-archive/web/6tisch/current/maillist.html](http://www.ietf.org/mail-archive/web/6tisch/current/maillist.html) |
| source       | [https://bitbucket.org/6tisch/](https://bitbucket.org/6tisch/)                                                                         |

## Gallery

|  |  |  |
|--|--|--|
| ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_topology.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_timelines.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/gui.png) |
