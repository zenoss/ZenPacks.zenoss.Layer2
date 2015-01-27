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

        dev = dmd.Devices.findDeviceByIdExact(evtproxy.device)
        if not dev:
            log.debug("Device %s no found" % evtproxy.device)

        log.debug("Our Device is %s" % dev)

        # Look up for upstream device(s)
        cat = CatalogAPI(dmd.zport)
        if not cat.check_working_path(dmd.Devices.zZenossGateway, dev.getPrimaryUrlPath()):
                log.debug("No path from %s to zenoss. Suppressing event." % dev.titleOrId())
                evtproxy.eventState = STATUS_SUPPRESSED

        # for obj in cat.get_upstream_devices(dev.id):
        #     if obj.getStatus() > 0:
        #         # Upstream router is DOWN, let suppress event
        #         log.debug("Upstream router for %s is %s and it's DOWN. Suppressing event." % (
        #             dev.titleOrId(), obj.titleOrId()))
        #         evtproxy.eventState = STATUS_SUPPRESSED
