##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from itertools import chain

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
        links = set()
        # Upstream devices
        cat = CatalogAPI(self.device.zport)
        try:
            upstream = cat.get_upstream_devices(self.device.id)
        except IndexError: # device id was not found
            upstream = []
        try:
            client = cat.get_client_devices(self.device.id),
        except IndexError: # device id was not found
            client = []

        for brain in chain(upstream, client):
            obj = brain.getObject()
            if obj.getDeviceClassName().startswith('/Network'):
                links.add('Switch: <a href="{}">{}</a>'.format(
                    obj.getPrimaryUrlPath(), obj.titleOrId()
                ))
        return list(links)
