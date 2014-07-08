##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenUtils.Utils import unused

from .macs_catalog import CatalogAPI

unused(Globals)


class DeviceLinkProvider(object):
    '''
    Provides a links to the client devices connected to this device
    '''
    def __init__(self, device):
        self.device = device

    def getExpandedLinks(self):
        links = []

        # Upstream devices
        cat = CatalogAPI(self.device.zport)
        for brain in cat.get_upstream_devices(self.device.id):
            obj = brain.getObject()
            links.append('Upstream switch: <a href="{}">{}</a>'.format(
                obj.getPrimaryUrlPath(), obj.titleOrId())
            )

        # Client devices
        for brain in cat.get_client_devices(self.device.id):
            obj = brain.getObject()
            links.append('Client device: <a href="{}">{}</a>'.format(
                obj.getPrimaryUrlPath(), obj.titleOrId())
            )

        return links
