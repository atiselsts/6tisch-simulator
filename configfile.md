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