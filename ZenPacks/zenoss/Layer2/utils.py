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

from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
from Products.ZenUtils.Search import makeCaseSensitiveKeywordIndex
from Products.Zuul.catalog.global_catalog import GlobalCatalog


def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)


def asip(val):
    """Convert a byte string to an IP address string.  """
    return '.'.join(str(ord(c)) for c in val)


CATALOG_INDEX_TYPES = {
    'str': makeCaseSensitiveFieldIndex,
    'list': makeCaseSensitiveKeywordIndex
}


class ConnectionsCatalog(GlobalCatalog):
    def __init__(self, name):
        super(ConnectionsCatalog, self).__init__()
        self.id = name


class BaseCatalogAPI(object):
    ''' Provides a methods to store and retrieve data in catalog '''

    _catalog = None
    name = None
    fields = {}

    def __init__(self, zport):
        self.zport = zport

    @property
    def catalog(self):
        ''' Find catalog in zport if exists, or create it from scratch'''
        if self._catalog:
            return self._catalog

        if not hasattr(self.zport, self.name):
            catalog = ConnectionsCatalog(self.name)
            for key, value in self.fields.iteritems():
                catalog.addIndex(key, CATALOG_INDEX_TYPES[value](key))
                catalog.addColumn(key)

            self.zport._setObject(self.name, catalog)

            log.debug('Created catalog %s' % self.name)

        self._catalog = getattr(self.zport, self.name)
        return self._catalog

    @catalog.deleter
    def catalog(self):
        ''' Delete catalog from this object and zport '''
        self.zport._delObject(self.name)
        del self._catalog

    def clear(self):
        self.catalog._catalog.clear()

    def search(self, **query):
        return self.catalog.search(query)

    def show_content(self, **query):
        ''' Used to watch content of catalog in zendmd '''
        try:
            from tabulate import tabulate
        except ImportError:
            return 'Please, use "pip install tabulate" to install tabulate'

        print tabulate(
            (self.braintuple(b)
                for b in self.search(**query)),
            headers=self.fields.keys()
        )

    def braintuple(self, brain):
        return tuple(getattr(brain, f) for f in self.fields.keys())
