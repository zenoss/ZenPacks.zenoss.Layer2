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

import logging

log = logging.getLogger("zen.eventd")


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
        # if not evtproxy.agent == "zenping": return
        if not "DOWN" in evtproxy.summary: return

        dev = dmd.Devices.findDevice(evtproxy.device)
        if not dev:
            log.error("Device %s no found" % evtproxy.device)

        log.debug("Our Device is %s" % dev)
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
                    log.debug("Upstream router is %s" % obj.device())
                    evtproxy.eventState = STATUS_SUPPRESSED
