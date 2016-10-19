# Simple Agent Pro

This directory contains files for use with the Simple Agent Pro (SAPro) SNMP simulator.

# Q-BRIDGE MIB

Currently the only files here are used to simulate a pair of switches which implement Q-BRIDGE MIB instead of BRIDGE-MIB. Each switch is connected in a redundant manner to a pair of hosts.

You can use a command such as the following to load these files into the SAPro server.

	rsync -av . root@perf-target-1:/opt/sapro/projects/l2

You can then use the SAPro GUI to load the q-bridge.map file, and start it.

Now you can load these devices into Zenoss with the accompanying zenbatchload file.

	zenbatchload q-bridge.zenbatchload
