##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.Layer2')

from Products.Zuul.catalog.global_catalog import GlobalCatalog
from Products.Zuul.catalog.global_catalog import GlobalCatalogFactory
from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
from Products.ZenUtils.Search import makeCaseSensitiveKeywordIndex

from .connections_provider import IConnection

CONNECTIONS_CATALOG_ID = 'connections_catalog'

class CatalogAPI(object):
    ''' Provides a methods to store and retrieve data in catalog '''

    _catalog = None

    def __init__(self, zport):
        self.zport = zport

    @property
    def catalog(self):
        ''' Find catalog in zport if exists, or create it from scratch'''
        if self._catalog:
            return self._catalog

        if not hasattr(self.zport, CONNECTIONS_CATALOG_ID):
            factory = ConnectionsCatalogFactory()
            factory.create(self.zport)
            log.debug('Created catalog %s' % CONNECTIONS_CATALOG_ID)

        self._catalog = getattr(self.zport, CONNECTIONS_CATALOG_ID)
        return self._catalog

    @catalog.deleter
    def catalog(self):
        ''' Delete catalog from this object and zport '''
        factory = ConnectionsCatalogFactory()
        factory.remove(self.zport)
        del self._catalog

    @staticmethod
    def validate_connection(connection):
        connection = IConnection(connection)
        IConnection.validateInvariants(connection)
        return connection

    def add_connection(self, connection):
        ''' Add a connection to a catalog '''
        connection = self.validate_connection(connection)

        self.catalog.catalog_object(connection, uid=connection.hash)
        log.debug('%s added to %s' % (connection, CONNECTIONS_CATALOG_ID))

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection.hash)
        log.debug('%s removed from %s' % (connection, CONNECTIONS_CATALOG_ID))

    def search(self, **query):
        return self.catalog.search(query)

    def show_content(self, **query):
        ''' Used to watch content of catalog in zendmd '''
        try:
            from tabulate import tabulate 
        except ImportError:
            return 'Please, use "pip install tabulate" to install tabulate'

        print tabulate(
            ((
                b.entity_id,
                b.connected_to,
                b.layers
            ) for b in self.search(**query)),
            headers=('entity_id', 'connected_to', 'layers')
        )


class ConnectionsCatalogFactory(GlobalCatalogFactory):

    def create(self, portal):
        catalog = ConnectionsCatalog()

        catalog.addIndex('entity_id', makeCaseSensitiveFieldIndex('entity_id'))
        catalog.addIndex('connected_to', makeCaseSensitiveKeywordIndex('connected_to'))
        catalog.addIndex('layers', makeCaseSensitiveKeywordIndex('layers'))

        catalog.addColumn('entity_id')
        catalog.addColumn('connected_to')
        catalog.addColumn('layers')

        portal._setObject(CONNECTIONS_CATALOG_ID, catalog)

    def remove(self, portal):
        portal._delObject(CONNECTIONS_CATALOG_ID)


class ConnectionsCatalog(GlobalCatalog):
    id = CONNECTIONS_CATALOG_ID
