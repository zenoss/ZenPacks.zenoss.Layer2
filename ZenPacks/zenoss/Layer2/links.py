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

import Globals
from Products.ZenUtils.Utils import unused

from .connections_catalog import CatalogAPI

unused(Globals)


MAX_LINKS = 100


log = logging.getLogger('zen.Layer2')


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
        this_id = self.device.getPrimaryUrlPath()
        suffix = []
        for id in cat.get_connected(
            entity_id=this_id,
            layers=['layer2'],
            method=cat.get_two_way_connected,
            depth=3,
        ):
            if id.startswith('/zport/dmd/Devices/Network/') and id != this_id:
                # The list of links might be huge, limit the output.
                if len(links) > MAX_LINKS:
                    suffix = ['(list of switches was truncated to '
                              '%s items)' % MAX_LINKS]
                    break

                links.add('Switch: <a href="{}">{}</a>'.format(
                    id, id.split('/')[-1]
                ))

        return ['<br />'] + list(links) + suffix
