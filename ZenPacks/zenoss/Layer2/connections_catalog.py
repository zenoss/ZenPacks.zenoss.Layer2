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

from ZenPacks.zenoss.Layer2.utils import BaseCatalogAPI

from .connections_provider import IConnection, IConnectionsProvider, connection_hash


class CatalogAPI(BaseCatalogAPI):
    name = 'connections_catalog'
    fields = dict(
        entity_id='str',
        connected_to='list',
        layers='list'
    )

    @staticmethod
    def validate_connection(connection):
        connection = IConnection(connection)
        IConnection.validateInvariants(connection)
        return connection

    def add_connection(self, connection):
        ''' Add a connection to a catalog '''
        connection = self.validate_connection(connection)

        self.catalog.catalog_object(connection, uid=connection.hash)
        log.debug('%s added to %s' % (connection, self.name))

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection.hash)
        log.debug('%s removed from %s' % (connection, self.name))

    def add_node(self, node):
        map(self.add_connection, IConnectionsProvider(node).get_connections())

    def remove_node(self, node):
        map(self.remove_connection, IConnectionsProvider(node).get_connections())

    def get_connected(self, entity_id, layers=None):
        q = dict(entity_id=entity_id)
        if layers:
            q['layers'] = layers
        for b in self.search(**q):
            for c in b.connected_to:
                yield c

    def get_existing_layers(self):
        return set(layer for i in self.search() for layer in i.layers)

    def clear(self):
        map(self.catalog.uncatalog_object, map(connection_hash, self.search()))
