# The 6TiSCH Simulator

Branch    | Build Status
--------- | -------------
`master`  | [![Build Status](https://openwsn-builder.paris.inria.fr/buildStatus/icon?job=6TiSCH%20Simulator/master)](https://openwsn-builder.paris.inria.fr/job/6TiSCH%20Simulator/job/master/)
`develop` | [![Build Status](https://openwsn-builder.paris.inria.fr/buildStatus/icon?job=6TiSCH%20Simulator/develop)](https://openwsn-builder.paris.inria.fr/job/6TiSCH%20Simulator/job/develop/)

Core Developers:

* Mališa Vučinić (malisa.vucinic@inria.fr)
* Yasuyuki Tanaka (yasuyuki.tanaka@inria.fr)
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

* connectivity models
    * Pister-hack
    * k7: trace-based connectivity
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

The simulator can be run on a cluster system. Here is an example for a cluster built with OAR and Conda:

1. Edit `config.py`
    * Set `numCPUs` with `-1` (use all the available CPUs/cores) or a specific number of CPUs to be used
    * Set `log_directory_name` with `"hostname"`
1. Create a shell script, `runSim.sh`, having the following lines:
    
        #!/bin/sh
        #OAR -l /nodes=1
        source activate py27
        python runSim.py
    
1. Make the shell script file executable:
   ```
   $ chmod +x runSim.sh
   ```
1. Submit a task for your simulation (in this case, 10 separate simulation jobs are submitted):
   ```
   $ oarsub --array 10  -S "./runSim.sh"
   ```
1. After all the jobs finish, you'll have 10 log directories under `simData`, each directory name of which is the host name where a job is executed
1. Merge the resulting log files into a single log directory:
   ```
   $ python mergeLogs.py
   ```

If you want to avoid using a specific host, use `-p` option with `oarsub`:
```
$ oarsub -p "not host like 'node063'" --array 10 -S "./runSim.sh"
```
In this case, `node063` won't be selected for submitted jobs.

The following commands could be useful to manage your jobs:

* `$ oarstat`: show all the current jobs
* `$ oarstat -u`: show *your* jobs
* `$ oarstat -u -f`: show details of your jobs 
* `$ oardel 87132`: delete a job whose job ID is 87132
* `$ oardel --array 87132`: delete all the jobs whose array ID is 87132

You can find your job IDs and array ID in `oarsub` outputs:

```
$ oarsub --array 4 -S "runSim.sh"
...
OAR_JOB_ID=87132
OAR_JOB_ID=87133
OAR_JOB_ID=87134
OAR_JOB_ID=87135
OAR_ARRAY_ID=87132
```

## Code Organization

* `SimEngine/`: the simulator
    * `Connectivity.py`: Simulates wireless connectivity.
    * `SimConfig.py`: The overall configuration of running a simulation campaign.
    * `SimEngine.py`: Event-driven simulation engine at the core of this simulator.
    * `SimLog.py`: Used to save the simulation logs.
    * `SimSettings.py`: The settings of a single simulation, part of a simulation campaign.    
    * `Mote/`: Models a 6TiSCH mote running the different standards listed above.    
* `bin/`: the scripts for you to run
* `examples/`: example plots, shown in the documentation    
* `tests/`: the unit tests, run using `pytest`
* `traces/`: example `k7` connectivity traces

## Configuration

`runSim.py` reads `config.json` in the current working directory.
You can specify a specific `config.json` location with `--config` option.

```
python runSim.py --config=example.json
```

The `config` parameter can contain:

* the name of the configuration file in the current directory, e.g. `example.json`
* a path to a configuration file on the computer running the simulation, e.g. `c:\simulator\example.json`
* a URL of a configuration file somewhere on the Internet, e.g. `https://www.example.com/example.json`

### base format of the configuration file

```
{
    "version":               0,
    "execution": {
        "numCPUs":           1,
        "numRuns":           100
    },
    "settings": {
        "combination": {
            ...
        },
        "regular": {
            ...
        }
    },
    "logging":               "all",
    "log_directory_name":    "startTime",
    "post": [
        "python compute_kpis.py",
        "python plot.py"
    ]
}
```

* the configuration file is a valid JSON file
* `version` is the version of the configuration file format; only 0 for now.
* `execution` specifies the simulator's execution
    * `numCPUs` is the number of CPUs (CPU cores) to be used; `-1` means "all available cores"
    * `numRuns` is the number of runs per simulation parameter combination
* `settings` contains all the settings for running the simulation.
    * `combination` specifies variations of parameters
    * `regular` specifies the set of simulator parameters commonly used in a series of simulations
* `logging` specifies what kinds of logs are recorded; `"all"` or a list of log types
* `log_directory_name` specifies how sub-directories for log data are named: `"startTime"` or `"hostname"`
* `post` lists the post-processing commands to run after the end of the simulation.

See `bin/config.json` to find  what parameters should be set and how they are configured.

### more on connectivity models

#### using a *k7* connectivity model

`k7` is a popular format for connectivity traces. 
You can run the simulator using connectivity traces in your K7 file instead of using the propagation model.

```
{
    ...
    "settings": {
        "conn_class": "K7"
        "conn_trace": "../traces/grenoble.k7.gz"
    },
    ...
}
```

* `conn_class` should be set with `"K7"`
* `conn_trace` should be set with your K7 file path

### more on applications

`AppPeriodic` and `AppBurst` are available.

### configuration file format validation

The format of the configuration file you pass is validated before starting the simulation. If your configuration file doesn't comply with the format, an `ConfigfileFormatException` is raised, containing a description of the format violation. The simulation is then not started.

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
