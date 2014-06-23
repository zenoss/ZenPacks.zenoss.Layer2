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


def get_ifinfo_for_layer2(self):
    '''
    Returns list with subset of IpInterface properties
    '''
    res = {}
    if self.os:
        for interface in self.os.interfaces():
            res[interface.id] = {
                "ifindex": interface.ifindex,
                "clientmacs": [],
                "baseport": 0
            }
    return res


def get_clients_links(self):
    '''
    Returns list of links to client devices
    '''
    macs = self._object.clientmacs
    if not macs:
        return ""

    cat = CatalogAPI(self._object.zport)
    links = []
    for mac in macs:
        brains = cat.get_if_client_devices([mac])
        if brains:
            for brain in brains:
                links.append('<a href="{}">{}</a>'.format(
                    brain.getObject().getPrimaryUrlPath(), mac)
                )
        else:
            links.append(mac)

    return ', '.join(links)
