##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq, In
from zenoss.protocols.protobufs.zep_pb2 import STATUS_SUPPRESSED

from .connections_catalog import CatalogAPI

import logging

log = logging.getLogger("zen.eventd")


def get_device(dmd, id):
    dev = dmd.Devices.findDeviceByIdExact(id)
    if dev:
        log.debug("Our Device is %s" % dev)
    else:
        log.debug("Device %s no found" % id)
    return dev


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
        if not evtproxy.agent == "zenping":
            return
        if not "DOWN" in evtproxy.summary:
            return

        dev = get_device(dmd, evtproxy.device)
        if not dev:
            return

        zdev = get_device(dmd, dmd.Devices.zZenossGateway)
        if not zdev:
            return

        cat = CatalogAPI(dmd.zport)
        if not cat.check_working_path(
            zdev.getPrimaryUrlPath(),
            dev.getPrimaryUrlPath()
        ):
                log.debug(
                    "No path from % to zenoss. Suppressing event.",
                    dev.titleOrId()
                )
                evtproxy.eventState = STATUS_SUPPRESSED
