
## Installation 
Please refer to https://github.com/cluther/snmposter#installation, to install all the dependencies needed for this simulator to run.

## Usage

Use snmpwalk_parser.py to convert snmpwalk output to python dictionaries which could be fed to agent simulator.

To simulate a number of agents you should do:

    from agents_simulator import simulate
    simulate(
        agents={
            '127.0.0.1': {
                '.1.3.6.1.2.1.1.1.0': 'Host 1', # sysDescr
            },
            '127.0.0.2': {
                '.1.3.6.1.2.1.1.1.0': 'Host 2', # sysDescr
            },
        },
        port=1611
    )
