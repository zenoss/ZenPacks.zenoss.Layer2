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

from .connections_catalog import CatalogAPI

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
        for id in cat.get_connected(
            entity_id=self.device.getPrimaryUrlPath(),
            layers=['layer2'],
            depth=3
        ):
            if id.startswith('/zport/dmd/Devices/Network/'):
                links.add('Switch: <a href="{}">{}</a>'.format(
                    id, id.split('/')[-1]
                ))
        return ['<br />'] + list(links)
