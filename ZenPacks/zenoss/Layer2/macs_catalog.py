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
from Products.Zuul.catalog.interfaces import IGloballyIndexed, IIndexableWrapper

from Products.ZCatalog.interfaces import ICatalogBrain

InterfacesCatalogId = 'interfaces_catalog'


class InterfacesCatalog(GlobalCatalog):
    id = InterfacesCatalogId

    def add_interfaces(self, device):
        for interface in device.os.interfaces():
            ic = InterfaceConnections(interface)
            self.catalog_object(ic)

    def remove_interfaces(self, device):
        for interface in device.os.interfaces():
            self.uncatalog_object('/'.join(interface.getPhysicalPath()))


class IInterfacesCatalogFactory(IGlobalCatalogFactory):
    pass


class InterfacesCatalogFactory(GlobalCatalogFactory):
    implements(IInterfacesCatalogFactory)

    def create(self, portal):
        catalog = InterfacesCatalog()
        self.setupCatalog(portal, catalog)

    def setupCatalog(self, portal, catalog):
        initializeInterfacesCatalog(catalog)
        portal._setObject(InterfacesCatalogId, catalog)

    def remove(self, portal):
        portal._delObject(InterfacesCatalogId)

def initializeInterfacesCatalog(catalog):
    catalog.addIndex('id', makeCaseSensitiveFieldIndex('id'))
    catalog.addIndex('device', makeCaseSensitiveFieldIndex('device'))
    catalog.addIndex('macaddress', makeCaseSensitiveFieldIndex('macaddress'))
    catalog.addIndex('clientmacs', makeCaseSensitiveKeywordIndex('clientmacs'))

    catalog.addColumn('id')
    catalog.addColumn('device')
    catalog.addColumn('macaddress')
    catalog.addColumn('clientmacs')


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


class CatalogAPI(object):
    '''
        Usage from zendmd:

from ZenPacks.zenoss.Layer2 import macs_catalog
cat = macs_catalog.CatalogAPI(zport)
cat.show_content()
    '''
    _catalog = None

    def __init__(self, zport):
        self.zport = zport

    @property
    def catalog(self):
        ''' Find catalog in zport if exists, or create it from scratch'''
        if self._catalog:
            return self._catalog

        if not hasattr(self.zport, InterfacesCatalogId):
            factory = InterfacesCatalogFactory()
            factory.create(self.zport)
            log.debug('Created catalog %s' % InterfacesCatalogId)

        self._catalog = getattr(self.zport, InterfacesCatalogId)
        return self._catalog

    def remove_catalog(self):
        factory = InterfacesCatalogFactory()
        factory.remove(self.zport)

    def add_device(self, device):
        self.catalog.add_interfaces(device)
        log.debug('%s added to %s' % (device, InterfacesCatalogId))

    def remove_device(self, device):
        self.catalog.remove_interfaces(device)
        log.debug('%s removed from %s' % (device, InterfacesCatalogId))

    def clear(self):
        for b in self.search():
            p = b.getPath()
            self.catalog.uncatalog_object(p)

    def search(self, query={}):
        # print 'search:', query
        return self.catalog.search(query)

    def get_device_interfaces(self, device_id):
        res = self.search({'device': device_id})
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

    def get_if_upstream_devices(self, mac_addresses):
        '''
        Returns list of devices, connected to IpInterface by given MACs
        '''
        return [
            self.get_device_obj(brain.device)
            for brain in self.search({'clientmacs': unique(mac_addresses)})
        ]

    def get_if_client_devices(self, mac_addresses):
        '''
        Returns list of client devices, connected to IpInterface by given MACs
        '''
        res = []
        for i in self.search({'macaddress': unique(mac_addresses)}):
            res.append(self.get_device_obj(i.device))
        return res

    def get_connected_to(self, macaddress):
        ''' Return set of MAC addresses which are directly connected to given '''
        res = set()
        for i in self.search({'macaddress': macaddress}):
            for a in i.clientmacs:
                res.add(a)
        for i in self.search({'clientmacs': macaddress}):
            res.add(i.macaddress)
        return res

    def get_network_segment(self, mac_address):
        ''' Return set of MAC addresses which belong to the same network segment '''

        visited = NetworkSegment()
        visited.zport = self.zport # needed for network tree
        def visit(adr):
            if adr in visited:
                return
            visited.add(adr)
            for a in self.get_connected_to(adr):
                visit(a)

        visit(mac_address)

        return visited

    def show_content(self):
        try:
            from tabulate import tabulate 
        except ImportError:
            return 'Please, use "pip install tabulate" to install tabulate'

        print tabulate(
            ((b.id, b.device, b.macaddress,
            ', '.join(b.clientmacs[:5]) + (' ...' if len(b.clientmacs) > 5 else ''))
            for b in self.search()),
            headers=('ID', 'Device', 'MAC', 'Client MACs')
        )

    def get_device_obj(self, device_id):
        return self.zport.dmd.Devices.findDeviceByIdExact(device_id)


class NetworkSegment(set):
    @property
    def id(self):
        return ', '.join(sorted(self)[:3]) + (' ...' if len(self) > 3 else '')

    def titleOrId(self):
        return self.id

    def getIconPath(self):
        return "/zport/dmd/img/icons/network.png"

    def getEventSummary(self):
        return [
            ['zenevents_5_noack noack', 0, 0],
            ['zenevents_4_noack noack', 0, 0],
            ['zenevents_3_noack noack', 0, 0],
            ['zenevents_2_noack noack', 0, 0],
            ['zenevents_1_noack noack', 0, 0]
        ]

def unique(l):
    return list(set(l))
