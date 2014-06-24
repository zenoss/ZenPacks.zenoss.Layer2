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

from .macs_catalog import CatalogAPI

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
        if not evtproxy.agent == "zenping": return
        if not "DOWN" in evtproxy.summary: return

        dev = dmd.Devices.findDevice(evtproxy.device)
        log.debug("Our Device is %s" % dev)

        # Look up for upstream device(s)
        cat = CatalogAPI(dmd.zport)
        for brain in cat.get_upstream_devices(dev.id):
            obj = brain.getObject()
            if obj.getStatus() > 0:
                # Upstream router is DOWN, let suppress event
                log.debug("Upstream router is %s" % obj)
                evtproxy.eventState = STATUS_SUPPRESSED
