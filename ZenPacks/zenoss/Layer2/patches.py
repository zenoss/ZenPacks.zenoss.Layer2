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
from Products.ZenUtils.Utils import edgesToXML
from Products.ZenUtils.Utils import monkeypatch

from .macs_catalog import CatalogAPI
from .network_tree2 import get_edges

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


@monkeypatch('Products.ZenModel.Device.Device')
def index_object(self, idxs=None, noips=False):
    original(self, idxs, noips)

    log.info('Adding %s to catalog' % self)
    catapi = CatalogAPI(self.zport)
    catapi.add_device(self)

@monkeypatch('Products.ZenModel.Device.Device')
def unindex_object(self):
    original(self)

    log.info('Removing %s from catalog' % self)
    catapi = CatalogAPI(self.zport)
    catapi.remove_device(self)

@monkeypatch('Products.ZenModel.Device.Device')
def set_reindex_maps(self, value):
    self.index_object()

@monkeypatch('Products.ZenModel.Device.Device')
def get_reindex_maps(self):
    ''' Should return something distinct from value passed to
        set_reindex_maps for set_reindex_maps to run
    '''
    return False


def getXMLEdges(self, depth=3, filter="/", start=()):
    if not start: start=self.id
    edges = get_edges(self, depth, withIcons=True, filter=filter)
    return edgesToXML(edges, start)
