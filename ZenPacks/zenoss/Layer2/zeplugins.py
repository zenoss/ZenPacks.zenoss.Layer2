##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
This file contains L2SuppressEventsPlugin which is registered as utility
for interface Products.ZenEvents.interfaces.IPostEventPlugin,
so it is called from zeneventd daemon, and is able to change events.

In our case it changes event state to 'suppressed' when there is no working
path to device that was source of event.
'''

from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq, In
from zenoss.protocols.protobufs.zep_pb2 import STATUS_SUPPRESSED

from .connections_catalog import CatalogAPI

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
        if not evtproxy.agent == "zenping":
            return
        if "DOWN" not in evtproxy.summary:
            return

        dev = get_device(dmd, evtproxy.device)
        if not dev:
            return

        zdev = get_device(dmd, dmd.Devices.zZenossGateway)
        if not zdev:
            return

        if dev == zdev:
            return

        cat = CatalogAPI(dmd.zport)
        if not cat.check_working_path(
            zdev.getPrimaryUrlPath(),
            dev.getPrimaryUrlPath()
        ):
            log.debug(
                "No path from %s to zenoss. Suppressing event.",
                dev.titleOrId()
            )
            evtproxy.eventState = STATUS_SUPPRESSED


def get_device(dmd, id):
    dev = dmd.Devices.findDeviceByIdExact(id)
    if dev:
        log.debug("Our Device is %s" % dev)
    else:
        log.debug("Device %s no found" % id)
    return dev
