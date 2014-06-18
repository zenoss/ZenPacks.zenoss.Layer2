##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
"""
Custom ZenPack initialization code. All code defined in this module will be
executed at startup time in all Zope clients.
"""

import logging
log = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenUtils.Utils import unused
from Products.ZenUtils.Utils import monkeypatch
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.ZenModel.Device import Device
from Products.ZenModel.IpInterface import IpInterface
from Products.Zuul.interfaces.component import IIpInterfaceInfo
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq

from .macs_catalog import CatalogAPI

unused(Globals)


# -- IP Interfaces overrides --------------------------------------------------

# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmacs = []
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id':'clientmacs', 'type':'string', 'mode':'w'},
    {'id':'baseport', 'type':'int', 'mode':'w'},
)

def get_ifinfo_for_layer2(self):
    res = {}
    if self.os:
        for interface in self.os.interfaces():
            res[interface.id] = {
                "ifindex": interface.ifindex,
                "clientmacs": [],
                "baseport": 0
            }
    return res

Device.get_ifinfo_for_layer2 = get_ifinfo_for_layer2


IIpInterfaceInfo.clientmacs = schema.TextLine(
    title=u"Clients MAC Addresses", group="Details", order=13)
IIpInterfaceInfo.baseport = schema.TextLine(
    title=u"Physical Port", group="Details", order=14)

# -- UI overrides goes here --------------------------------------------------

IpInterfaceInfo.clientmacs = ProxyProperty('clientmacs')
IpInterfaceInfo.baseport = ProxyProperty('baseport')

def getClientsLinks(self):
    # Temporary returns raw MACs without links for debugging
    return self._object.clientmacs
    # TODO: need catalog to speed up linking to client devices:
    macs = self._object.clientmacs
    if not macs:
        return ""

    links = []
    for mac in macs:
        if not mac: continue
        is_found = False

        cat = ICatalogTool(self._object.dmd)
        brains = cat.search("Products.ZenModel.IpInterface.IpInterface")
        for brain in brains:
            obj = brain.getObject()
            if obj.macaddress == mac:
                links.append('<a href="{}">{}</a>'.format(
                    obj.getPrimaryUrlPath(), mac))
                is_found = True
                break

        if not is_found:
            links.append(mac)

    return ', '.join(links)

IpInterfaceInfo.getClientsLinks = getClientsLinks

@monkeypatch('Products.ZenModel.Device.Device')
def index_object(self, idxs=None, noips=False):
    original(self, idxs, noips)

    log.info('Adding %s to catalog' % self)
    catapi = CatalogAPI(self.zport)
    catapi.add_device_to_catalog(self)

@monkeypatch('Products.ZenModel.Device.Device')
def set_reindex_maps(self, value):
    print '!' * 100
    with open('/home/zenoss/out', 'a') as f:
        f.write('Yes!\n')
    self.index_object()

@monkeypatch('Products.ZenModel.Device.Device')
def get_reindex_maps(self):
    ''' Should return something distinct from value passed to
        set_reindex_maps for set_reindex_maps to run
    '''
    return False

