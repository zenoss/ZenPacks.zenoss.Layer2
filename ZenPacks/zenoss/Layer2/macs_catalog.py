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

from zope.interface import implements
from zope.component import adapts, getUtility

from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
from Products.ZenUtils.Search import makeCaseSensitiveKeywordIndex
from Products.Zuul.catalog.global_catalog import GlobalCatalog
from Products.Zuul.catalog.global_catalog import GlobalCatalogFactory
from Products.Zuul.catalog.interfaces import IGlobalCatalogFactory
from Products.Zuul.catalog.interfaces import IGloballyIndexed
from Products.Zuul.catalog.interfaces import IIndexableWrapper
from Products.ZCatalog.interfaces import ICatalogBrain

from ZenPacks.zenoss.Layer2.utils import BaseCatalogAPI


class InterfaceConnections(object):
    implements(IIndexableWrapper)
    adapts(IGloballyIndexed)

    def __init__(self, interface):
        self.interface = interface

    def getPhysicalPath(self):
        return self.interface.getPhysicalPath()

    @property
    def id(self):
        return self.interface.id

    @property
    def device(self):
        return self.interface.device().id

    @property
    def macaddress(self):
        return getattr(self.interface, 'macaddress', '').upper()

    @property
    def clientmacs(self):
        return [
            x.upper()
            for x in getattr(self.interface, 'clientmacs', [])
            if x
        ]

    @property
    def layers(self):
        res = ['layer2']
        res.extend(get_vlans(self.interface))
        return res


class CatalogAPI(BaseCatalogAPI):

    name = 'interfaces_catalog'
    fields = dict(
        id='str',
        device='str',
        macaddress='str',
        clientmacs='list',
        layers='list'
    )

    def add_device(self, device):
        for interface in device.os.interfaces():
            ic = InterfaceConnections(interface)
            self.catalog.catalog_object(ic)
        log.debug('%s added to %s' % (device, self.name))

    def remove_device(self, device):
        for interface in device.os.interfaces():
            self.catalog.uncatalog_object(
                '/'.join(interface.getPhysicalPath())
            )
        log.debug('%s removed from %s' % (device, self.name))

    def clear(self):
        for b in self.search():
            p = b.getPath()
            self.catalog.uncatalog_object(p)

    def get_device_interfaces(self, device_id, layers=None):
        query = dict(device=device_id)
        if layers:
            query['layers'] = layers
        res = self.search(**query)
        if res:
            return res
        else:
            raise IndexError(
                'Interfaces with device id %r was not found' % device_id
            )

    def get_device_macadresses(self, device_id):
        ''' Return list of macadresses for device with given id '''
        return [
            getattr(item, 'macaddress', '')
            for item in self.get_device_interfaces(device_id)
        ]

    def get_device_clientmacs(self, device_id):
        ''' Return list of clientmacs for device with given id '''
        return [
            clmac for interface in self.get_device_interfaces(device_id)
            for clmac in interface.clientmacs
        ]

    def get_upstream_devices(self, device_id):
        '''
        Returns list of devices brains where given device MAC addresses
        found in client MACs
        '''
        mac_addresses = self.get_device_macadresses(device_id)
        return self.get_if_upstream_devices(mac_addresses)

    def get_client_devices(self, device_id):
        '''
        Returns list of client devices, connected to device
        '''
        clientmacs = self.get_device_clientmacs(device_id)
        return [
            device for device in self.get_if_client_devices(clientmacs)
            if device.id != device_id
        ]

    def get_only_client_devices(self, device_id):
        return [
            brain
            for brain in self.get_client_devices(device_id)
            if not brain.clientmacs
        ]

    def get_upstream_devices_only_for_client(self, device_id):
        if not self.get_device_clientmacs(device_id):
            return self.get_upstream_devices(device_id)
        else:
            return []

    def get_if_upstream_devices(self, mac_addresses):
        '''
        Returns list of devices, connected to IpInterface by given MACs
        '''
        return [
            self.get_device_obj(brain.device)
            for brain in self.search(clientmacs=unique(mac_addresses))
        ]

    def get_if_client_devices(self, mac_addresses):
        '''
        Returns list of client devices, connected to IpInterface by given MACs
        '''
        res = []
        for i in self.search(macaddress=unique(mac_addresses)):
            res.append(self.get_device_obj(i.device))
        return res

    def get_device_by_mac(self, mac_address):
        brains = list(self.search(macaddress=[mac_address]))
        if brains:
            return self.get_device_obj(brains[0].device)

    def get_connected_to(self, iface):
        '''
            Return dictionary of interfaces
            which are directly connected to given
        '''
        res = {iface.id: iface}
        for a in iface.clientmacs:
            for i in self.search(macaddress=a):
                res[i.id] = i
        return res

    def get_network_segment(self, iface, layers=None):
        ''' Return NetworkSegment of interface '''

        visited = NetworkSegment()
        visited.zport = self.zport  # needed for network tree

        def visit(iface):
            visited.layers.update(get_vlans(iface))
            if iface.id in visited:
                return
            visited[iface.id] = iface
            map(visit, self.get_connected_to(iface).values())

        visit(iface)

        return visited

    def get_existing_layers(self):
        return set(layer for i in self.search() for layer in i.layers)

    def get_device_obj(self, device_id):
        return self.zport.dmd.Devices.findDeviceByIdExact(device_id)


class NetworkSegment(dict):
    def __init__(self):
        super(NetworkSegment, self).__init__()
        self.layers = set(['layer2'])

    @property
    def id(self):
        return ', '.join(sorted(self.keys()))

    def titleOrId(self):
        return self.id

    def getIconPath(self):
        return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'

    def getEventSummary(self):
        return [
            ['zenevents_5_noack noack', 0, 0],
            ['zenevents_4_noack noack', 0, 0],
            ['zenevents_3_noack noack', 0, 0],
            ['zenevents_2_noack noack', 0, 0],
            ['zenevents_1_noack noack', 0, 0]
        ]

    @property
    def macs(self):
        return set(i.macaddress for i in self.values())

    def show_content2(self):
        for b in self.search():
            print b.id
            print '\tUpstream: ', csl(self.get_upstream_devices(b.id))
            print '\tClient:   ', csl(self.get_client_devices(b.id))
            print '\tOnly client:     ', csl(
                self.get_only_client_devices(b.id)
            )
            print '\tOnly upstream:   ', csl(
                self.get_upstream_devices_only_for_client(b.id)
            )


def csl(sequence):
    ''' Return string with comma-separated list '''
    return ', '.join(str(i) for i in sequence)


def unique(l):
    return list(set(i for i in l if isinstance(i, basestring)))


def get_vlans(iface):
    if not hasattr(iface, 'vlans'):
        return []
    if callable(iface.vlans):
        return map(str, (vlan.vlan_id for vlan in iface.vlans()))
    else:
        return iface.vlans
