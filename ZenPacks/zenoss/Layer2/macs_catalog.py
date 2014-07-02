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

import zExceptions
from zope.interface import implements
from zope.component import adapts, getUtility

from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
from Products.ZenUtils.Search import makeCaseSensitiveKeywordIndex
from Products.Zuul.catalog.global_catalog import GlobalCatalog
from Products.Zuul.catalog.global_catalog import GlobalCatalogFactory
from Products.Zuul.catalog.global_catalog import IndexableWrapper
from Products.Zuul.catalog.interfaces import IGlobalCatalogFactory
from Products.Zuul.catalog.interfaces import IGloballyIndexed, IPathReporter, IIndexableWrapper

MACsCatalogId = 'macs_catalog'

class MACsCatalog(GlobalCatalog):
    id = MACsCatalogId

    def add_device(self, device):
        dc = DeviceConnections(device)
        self.catalog_object(dc)

    def remove_device(self, device):
        self.uncatalog_object('/'.join(device.getPhysicalPath()))

class IMACsCatalogFactory(IGlobalCatalogFactory):
    pass


class MACsCatalogFactory(GlobalCatalogFactory):
    implements(IMACsCatalogFactory)

    def create(self, portal):
        catalog = MACsCatalog()
        self.setupCatalog(portal, catalog)

    def setupCatalog(self, portal, catalog):
        initializeMACsCatalog(catalog)
        portal._setObject(MACsCatalogId, catalog)

    def remove(self, portal):
        portal._delObject(MACsCatalogId)


class DeviceConnections(object):
    implements(IIndexableWrapper)
    adapts(IGloballyIndexed)

    def __init__(self, device):
        self.device = device

    def getPhysicalPath(self):
        return self.device.getPhysicalPath()

    @property
    def id(self):
        return self.device.id

    @property
    def macaddresses(self):
        return [i.macaddress
            for i in self.device.os.interfaces()
            if getattr(i, 'macaddress')
        ]

    @property
    def clientmacs(self):
        return [x
            for i in self.device.os.interfaces()
            if getattr(i, 'clientmacs')
            for x in i.clientmacs
            if x
        ]


def initializeMACsCatalog(catalog):
    catalog.addIndex('id', makeCaseSensitiveFieldIndex('id'))
    catalog.addIndex('macaddresses', makeCaseSensitiveKeywordIndex('macaddresses'))
    catalog.addIndex('clientmacs', makeCaseSensitiveKeywordIndex('clientmacs'))

    catalog.addColumn('id')
    catalog.addColumn('macaddresses')
    catalog.addColumn('clientmacs')

def unique(l):
    return list(set(l))

class CatalogAPI(object):
    catalog = None
    def __init__(self, zport):
        self.zport = zport

    def get_catalog(self):
        ''' Find catalog in zport if exists, or create it from scratch'''
        if self.catalog:
            return self.catalog

        if not hasattr(self.zport, MACsCatalogId):
            factory = getUtility(IMACsCatalogFactory)
            factory.create(self.zport)
            log.info('Created %s' % MACsCatalogId)

        self.catalog = getattr(self.zport, MACsCatalogId)
        return self.catalog

    def reindex(self):
        ''' Reindex objects in dmd'''
        self.zport.dmd.Devices.reIndex()

    def add_device(self, device):
        self.get_catalog().add_device(device)
        log.info('%s added to %s' % (device, MACsCatalogId))

    def remove_device(self, device):
        self.get_catalog().remove_device(device)
        log.info('%s removed from %s' % (device, MACsCatalogId))

    def clear(self):
        for b in self.search():
            self.get_catalog().uncatalog_object(b.getPath())

    def search(self, query={}):
        return self.get_catalog().search(query)

    def show_all(self):
        for b in self.search():
            o = b.getObject()
            print o, type(o)

    def get_device_macadresses(self, device_id):
        ''' Return list of macadresses for device with given id '''
        res = self.search({'id': device_id})
        if res:
            return res[0].macaddresses
        else:
            raise IndexError('Device with id %r was not found' % device_id)

    def get_device_clientmacs(self, device_id):
        ''' Return list of clientmacs for device with given id '''
        res = self.get_catalog().search({
            'id': device_id
        })
        if res:
            return res[0].clientmacs
        else:
            raise IndexError('Device with id %r was not found' % device_id)

    def get_upstream_devices(self, device_id):
        '''
        Returns list of devices' brains where given device mac addresses
        found in client macs
        '''
        mac_addresses = self.get_device_macadresses(device_id)
        return self.get_if_upstream_devices(mac_addresses)

    def get_client_devices(self, device_id):
        '''
        Returns list of client devices, connected to device
        '''
        clientmacs = self.get_device_clientmacs(device_id)
        macs = list(set(clientmacs))

        res = []
        for brain in self.get_catalog().search({'macaddresses': macs}):
            if brain.id != device_id:
                res.append(brain)
        return res

    def get_if_upstream_devices(self, mac_addresses):
        '''
        Returns list of devices, connected to IpInterface by given MACs
        '''
        return list(self.search({'clientmacs': unique(mac_addresses)}))

    def get_if_client_devices(self, mac_addresses):
        '''
        Returns list of client devices, connected to IpInterface by given MACs
        '''
        return list(self.search({'macaddresses': unique(mac_addresses)}))
