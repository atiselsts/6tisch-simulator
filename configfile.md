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
* `version` is the version of the configuration file format.
    * Only 0 for now.
* `execution` specifies the simulator's execution
    * `numCPUs` is the number of CPUs (CPU cores) to be used; `-1` means "all available cores"
    * `numRuns` is the number of runs per simulation parameter combination
* `settings` contains all the settings for running the simulation.
    * `combination` specifies variations of parameters
    * `regular` specifies the set of simulator parameters commonly used in a series of simulations
* `logging` specifies what kinds of logs are recorded; 'all' or a list of log types
* `log_directory_name` specifies how sub-directories for log data are named: 'startTime' or 'hostname'
* `post` lists the post-processing commands to run after the end of the simulation.

See `bin/config.json` to find  what parameters should be set and how they are configured.

### more on connectivity models

#### using a `k7` connectivity model

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
