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

from .macs_catalog import CatalogAPI as MACsCatalogAPI
from .connections_catalog import CatalogAPI
from .network_tree import get_edges, get_json, serialize

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

    cat = MACsCatalogAPI(self._object.zport)
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
    catapi = MACsCatalogAPI(self.zport)
    catapi.add_device(self)


@monkeypatch('Products.ZenModel.Device.Device')
def unindex_object(self):
    original(self)

    catapi = MACsCatalogAPI(self.zport)
    catapi.remove_device(self)


@monkeypatch('Products.ZenModel.Device.Device')
def set_reindex_maps(self, value):
    self.index_object()
    if value == 'reindex please':
        self.macs_indexed = True


@monkeypatch('Products.ZenModel.Device.Device')
def get_reindex_maps(self):
    ''' Should return something distinct from value passed to
        set_reindex_maps for set_reindex_maps to run
    '''
    return set(
        x.upper()
        for i in self.os.interfaces()
        if getattr(i, 'clientmacs')
        for x in i.clientmacs
        if x
    )

Device._relations += (
    ('neighbor_switches', ToManyCont(
        ToOne,
        'ZenPacks.zenoss.Layer2.NeighborSwitch.NeighborSwitch',
        'switch'
    )),
)


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getJSONEdges(self, root_id='', depth='2', filter='/', layers=None):
    ''' Get JSON representation of network nodes '''
    if not root_id:
        return get_json(Exception("You should set a device name"))
    root_id = urllib.unquote(root_id)
    obj = self.Devices.findDevice(root_id)
    if not obj:
        return get_json(Exception('Device %r was not found' % root_id))

    if layers:
        layers = [l_name[len('layer_'):] for l_name in layers.split(',')]

    try:
        return get_json(get_edges(
            obj, int(depth), filter=filter, layers=layers
        ), obj.id)
    except Exception as e:
        log.exception(e)
        return get_json(e)

@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getNetworkLayers(self):
    ''' Return existing network layers on network map '''
    cat = CatalogAPI(self.zport)
    return cat.get_existing_layers()

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
