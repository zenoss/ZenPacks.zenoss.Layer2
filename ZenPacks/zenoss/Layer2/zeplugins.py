##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq, In
from zenoss.protocols.protobufs.zep_pb2 import STATUS_SUPPRESSED


class L2SuppressEventsPlugin(object):
    """
    Checks if event's device connected to off-line router
    and suppresses event if needed
    """

    @staticmethod
    def apply(evtproxy, dmd):
        """
        Apply the plugin to an event.
        """

        if not evtproxy.agent == "zenping": return
        if not evtproxy.summary.contains("DOWN"): return

        print "=" * 80
        from pprint import pprint
        print pprint(evtproxy)
        print "=" * 80

        dev_id = evtproxy.device()
        dev = dmd.Devices.findDevice()
        print "Our Device is", dev
        search = ICatalogTool(dev).search

        # Collect MACs of current device's interfaces
        macs = []
        for brain in search('Products.ZenModel.IpInterface.IpInterface'):
            macs.append(brain.getObject().macaddress)

        # Look up for upstream device(s)
        upstream_routers = {}
        cat = ICatalogTool(dmd.Devices)
        brains = cat.search(
            types=('Products.ZenModel.IpInterface.IpInterface'),
            #query=In('clientmacs', macs)
        )
        for brain in brains:
            obj = brain.getObject()
            if any(x in macs for x in obj.clientmacs):
                # up_dev = obj.device()
                # upstream_routers[up_dev.id] = up_dev
                if obj.device().getStatus() > 0:
                    # Upstream router is DOWN, let suppress event
                    print "Upstream router is", obj.device()
                    evtproxy._action = STATUS_SUPPRESSED
