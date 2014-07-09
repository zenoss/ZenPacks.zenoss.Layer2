##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import urllib
import logging
log = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenModel.Device import Device
from Products.ZenUtils.Utils import unused
from Products.ZenUtils.Utils import edgesToXML
from Products.ZenUtils.Utils import monkeypatch
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.ZenModel.IpInterface import IpInterface
from Products.Zuul.interfaces.component import IIpInterfaceInfo
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.ZenRelations.RelSchema import ToOne, ToManyCont

from .macs_catalog import CatalogAPI, DeviceConnections
from .network_tree2 import get_edges, get_json

unused(Globals)


@monkeypatch('Products.ZenModel.Device.Device')
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
    links = {
        "Other": []
    }
    for mac in macs:
        brains = cat.get_if_client_devices([mac])
        if brains:
            for brain in brains:
                obj = brain.getObject()
                link = '<a href="{}">{}</a>'.format(
                    obj.getPrimaryUrlPath(), obj.titleOrId())
                if link in links:
                    links[link].append(mac)
                else:
                    links[link] = [mac]
        else:
            links["Other"].append(mac)

    return ' '.join(["<p><b>{}</b>: {}</p>".format(k, ', '.join(v)) \
        for k, v in links.iteritems()])


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
    return set(DeviceConnections(self).clientmacs)


Device._relations += (
    ('neighbour_switches', ToManyCont(
        ToOne,
        'ZenPacks.zenoss.Layer2.NeighbourSwitch.NeighbourSwitch',
        'switch')
    ),
)

@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getJSONEdges(self, root_id='', depth=2, filter='/'):
    ''' Get JSON representation of network nodes '''
    root_id = urllib.unquote(root_id)
    obj = self.Devices.findDevice(root_id)
    if not obj:
        raise Exception('Device %r not found' % root_id)
    return get_json(get_edges(
        obj, int(depth), withIcons=True, filter=filter
    ))

# -- IP Interfaces overrides --------------------------------------------------

# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmacs = []
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id':'clientmacs', 'type':'string', 'mode':'w'},
    {'id':'baseport', 'type':'int', 'mode':'w'},
)

IIpInterfaceInfo.clientmacs = schema.TextLine(
    title=u"Clients MAC Addresses", group="Details", order=13)
IIpInterfaceInfo.baseport = schema.TextLine(
    title=u"Physical Port", group="Details", order=14)

# -- UI overrides goes here --------------------------------------------------

IpInterfaceInfo.clientmacs = ProxyProperty('clientmacs')
IpInterfaceInfo.baseport = ProxyProperty('baseport')
IpInterfaceInfo.get_clients_links = property(get_clients_links)
