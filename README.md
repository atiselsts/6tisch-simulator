# The 6TiSCH Simulator

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

6TiSCH is an active IETF standardization working group that defines mechanisms to build and maintain communication schedules in tomorrow's Internet of (Important) Things.
This simulator allows you to measure the performance of those different mechanisms under different conditions.

What is simulated:

* protocol stack
    * [RFC6550](https://tools.ietf.org/html/rfc6550) RPL, non-storing mode
    * Fragment Forwarding (draft-watteyne-6lo-minimal-fragment-01)
    * 6LoWPAN Fragmentation and Reassembly (RFC 4944)
    * Minimal Scheduling Function (https://tools.ietf.org/html/draft-chang-6tisch-msf-01)
    * [draft-ietf-6tisch-6top-protocol](https://tools.ietf.org/html/draft-ietf-6tisch-6top-protocol-09) 6top
    * IEEE802.15.4-2015 TSCH (https://ieeexplore.ieee.org/document/7460875/)
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

## Gallery

|  |  |  |
|--|--|--|
| ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_topology.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/run_0_timelines.png) | ![](https://bytebucket.org/6tisch/simulator/raw/master/examples/gui.png) |

## Installation

* Install Python 2.7
* Clone or download this repository
* To plot the graphs, you need Matplotlib and scipy. On Windows, Anaconda (http://continuum.io/downloads) is a good on-stop-shop.

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
    * You'll have raw output data under `bin/simData` directory.
    * You can specify configuration parameters such as slot length and application packet interval if you want. `$ python runSim.py --help` shows available options.
1. Execute plot.py to see the results:
   ```
   $ python plot.py
   ```
    * You’ll have charts derived from the data under `bin/simPlots` directory.
    * You need to define your simulation scenarios and identify necessary parameter sets in order to have meaningful results or charts.

## Code Organization

* `bin/`: the scripts for you to run
* `SimEngine/`: the simulator
    * `Mote.py`: Models a 6TiSCH mote running the different standards listed above.
    * `Propagation.py`: Wireless propagation model.
    * `SimEngine.py`: Event-driven simulation engine at the core of this simulator.
    * `SimSettings.py`: Data store for all simulation settings.
    * `SimStats.py`: Periodically collects statistics and writes those to a file.
    * `Topology.py`: creates a topology of the motes in the network.
* `SimGui/`: the graphical user interface to the simulator

## configuration file format

A simulation is run by calling

```
python runSim.py --config=example.json
```

The `config` parameter can contain:
* the name of the configuration file in the current directory, e.g. `example.json`
* a path to a configuration file on the computer running the simulation, e.g. `c:\simulator\example.json`
* a URL of a configuration file somewhere on the Internet, e.g. `https://www.example.com/example.json`

This section details the format of that configuration file.

### base format

```
{
    'version':  0,
    'settings': {
        'nummotes'     4,
        'moteapps':    ('Periodic', (1,)),
        'sf':          ('MSF', (param1, param2)),
        'propagation': ('PisterHack',()),
        'simtime':     300,
        'numruns':     100,
    },
    'logging': [
         'logtype1',
         ('logtype2',('mote1','mote2')),
    ],
    'post': [
         ('func1', (param1,param2)),
         ('func2', (param1,param2)),
    ],
}
```

* the configuration file is a valid JSON file
* `version` is the version of the configuration file format.
    * Only 0 for now.
* `settings` contains all the settings for running the simulation.
    * `nummotes` is the number of motes
    * `moteapps` specifies the application to run on the motes.
        * here, instantiates class `App_Periodic` passing arguments `(1,)` for each mote
    * `sf` is the scheduling function used by all motes.
        * here, instantiates class `SF_MSF` passing arguments `(param1, param2)` for each mote
    * `propagation` is the propagation model
        * here, instantiates class `Propagation_PisterHack`, passing no arguments
        * other options are:
            * `k7` to load a k7 tracefile, see below.
            * `linear`, a line of PDR=100% from the root outwards
            * `meshed`, a fully meshed topology, with PDR=100%
    * `simtime`, duration of the simulation, in seconds. Here, we simulate 5 min of network.
    * `numruns`, number of simulation runs.
* `post` lists the post-processing routines to call after the end of the simulation.
    * here calls `post_func1(param1,param2)` and `post_func2(param1,param2)`

### more on propagation models

#### using a `k7` propagation model

`k7` is a popular format for connectivity traces, see TODO. 

```
{
    ...
    'settings': {
        'propagation'  ('k7', ('sample.k7',)),
        'moteapps': {
            'mote1': ('Periodic', (1,)),
            'mote2': ('Periodic', (5,)),
            'mote3': ('Periodic', (7,)),
            'mote4': ('Burst',    (10,)),
        },
    },
    ...
}
```

* here, propagation model `Propagation_k7` is instantiated with parameter `sample.k7`
* the `nummotes` parameter MUST NOT be present
* the `moteapps` element must be:
     * either a tuple, if all nodes run the same application
     * _(shown below)_ an object with keys corresponding to the mote identifiers in the `k7` trace file, if all nodes run a different app

#### using the `pdrMatrix` propagation model

This propagation model allows you to directly specify the PDR matrix used internally by the propagation model.

```
{
    ...
    'settings': {
        'propagation'  ('pdrMatrix', [
             [   null, 'mote1', 'mote2', 'mote3', 'mote4' ],
             ['mote1',    null,       0,    0.55,       0 ],
             ['mote2',       0,    null,       0,       0 ],
             ['mote3',       0,       0,    null,    0.30 ],
             ['mote4',       1,       0,    0.35,    null ],
         ]),
    },
    ...
}
```

* the PDR matrix specified MUST be a matrix of side "number of motes plus 1"
* the top row and left-most column MUST contain the identifiers of all motes in the network
* the `nummotes` parameter MUST NOT be present
* the diagonal MUST contain the `null` value in all cells
* the PDR matrix is read as follows (reading line-by-line):
    * the left-most column specifies the transmitter, the top row the receiver    
    * when `mote1` transmits, only `mote3` receives with probability 55%
    * when `mote2` transmits, no mote receives
    * when `mote3` transmits, only `mote4` receives with probability 30%
    * when `mote4` transmits,
        `mote1` receives with probability 100% and
        `mote3` receives with probability  35% and
* note that this matrix structure allows assymetric links

### more on mote and Internet apps

Each mote can run an application, and there can be applications running on the Internet.

#### running a different app on each mote

In this case, the `moteapps` element is a list which MUST contain `nummotes`-1 elements, each element specifying the app for of the nodes. The DAGroot does not run any apps.

```
{
    ...
    'settings': {
        ...
        'moteapps':         [
            ('Periodic', (1,)),
            ('Periodic', (5,)),
            ('Periodic', (7,)),
            ('Burst',    (10,)),
        ],
        ...
    },
    ...
}
```

#### running no app on the motes

If the `moteapps` element is not present, no apps run on the motes during the simulation.

#### running Internet apps

Internet apps run outside the mesh and interact with the motes. If the `internetapps` element is present, it contains a list of Internet apps.

```
{
    ...
    'settings': {
        ...
        'internetapps':         [
            ('Poll',     ('mote1',1)),
            ('Poll',     ('mote2',5)),
        ],
        ...
    },
    ...
}
```

In the example above:
* one instance of `InternetApp_Poll` is initiated with parameters `('mote1',1)`
* one instance of `InternetApp_Poll` is initiated with parameters `('mote2',5)`

### configuration file format validation

The format of the configuration file you pass is validated before starting the simulation. If your configuration file doesn't comply with the format, an `ConfigfileFormatException` is raised, containing a description of the format violation. The simulation is then not started.