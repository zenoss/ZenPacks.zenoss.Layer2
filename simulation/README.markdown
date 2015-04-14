
## Installation 
Please refer to https://github.com/cluther/snmposter#installation, to install all the dependencies needed for this simulator to run.

### On CentOS 6.4:

    yum -y install python-devel gcc
    pip install virtualenv

When you are inside `simulation/` folder, run

    virtualenv env
    source env/bin/activate

to start virtual python environment. From there you will need to install two more packages:

    wget http://downloads.sourceforge.net/project/twistedsnmp/twistedsnmp/0.3.13/TwistedSNMP-0.3.13.tar.gz -O - | tar xzf -
    cd TwistedSNMP-0.3.13
    python setup.py install
    cd ..
    rm -r TwistedSNMP-0.3.13/

    wget http://downloads.sourceforge.net/project/twistedsnmp/pysnmp-se/3.5.2/pysnmp-se-3.5.2.tar.gz -O - | tar xzf -
    cd pysnmp-se-3.5.2/
    python setup.py install
    cd ..
    rm -r pysnmp-se-3.5.2/


## Usage

Use snmpwalk_parser.py to convert snmpwalk output to python dictionaries which could be fed into agent simulator.

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

Or use oids generators from bridge_oids. This is done in agents_simulator.py in function main.

