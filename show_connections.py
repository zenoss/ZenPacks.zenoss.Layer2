from ZenPacks.zenoss.Layer2.connections_provider import IConnectionsProvider


for d in dmd.Devices.getSubDevices():
    print IConnectionsProvider(d.aq_base)

import bpython; bpython.embed(locals())
