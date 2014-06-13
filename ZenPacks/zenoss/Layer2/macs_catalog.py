from zope.interface import implements
from zope.component import adapts

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
        return [i.macadress for i in self.device.os.interfaces()]

    @property
    def clientmacs(self):
        # return [x for x in i.clientmacs for i in self.device.os.interfaces()]
        return [x for i in self.device.os.interfaces() for x in i.clientmacs]


def initializeMACsCatalog(catalog):
    catalog.addIndex('id', makeCaseSensitiveFieldIndex('id'))
    catalog.addIndex('macaddresses', makeCaseSensitiveKeywordIndex('macaddresses'))
    catalog.addIndex('clientmacs', makeCaseSensitiveKeywordIndex('clientmacs'))

    catalog.addColumn('id')
    catalog.addColumn('macaddresses')
    catalog.addColumn('clientmacs')
