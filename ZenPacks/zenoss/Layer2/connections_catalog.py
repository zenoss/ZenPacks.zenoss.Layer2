##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from itertools import chain
import logging
log = logging.getLogger('zen.Layer2')


from ZenPacks.zenoss.Layer2.utils import BaseCatalogAPI

from zExceptions import NotFound
from .connections_provider import IConnection, IConnectionsProvider
from .connections_provider import connection_hash


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
        map(
            self.remove_connection,
            IConnectionsProvider(node).get_connections()
        )

    def get_directly_connected(self, entity_id, layers=None):
        q = dict(entity_id=entity_id)
        if layers:
            q['layers'] = layers
        for b in self.search(**q):
            for c in b.connected_to:
                yield c

    def get_reverse_connected(self, entity_id, layers=None):
        q = dict(connected_to=entity_id)
        if layers:
            q['layers'] = layers
        for b in self.search(**q):
            yield b.entity_id

    def get_two_way_connected(self, entity_id, layers=None):
        for c in chain(
            self.get_directly_connected(entity_id, layers),
            self.get_reverse_connected(entity_id, layers)
        ):
            yield c

    def get_connected(self, entity_id, layers=None, depth=None):
        ''' Return set of all connected nodes '''
        visited = set()

        def visit(node, depth):
            if depth is not None and depth < 0:
                return
            if node in visited:
                return
            visited.add(node)

            if depth is not None:
                depth -= 1
            for n in self.get_two_way_connected(node, layers):
                visit(n, depth)

        visit(entity_id, depth)

        return visited

    def get_obj(self, id):
        ''' Returns object from dmd for some node id or None '''
        try:
            node = self.zport.dmd.getObjByPath(node)
        except (NotFound, KeyError) as e:
            return None

    def get_status(self, node):
        node = self.get_obj(node)
        if node is None:
            return True
        return IConnectionsProvider(node).get_status()

    def check_working_path(self, from_entity, to_entity):
        layers = []
        for c in self.search(entity_id=from_entity):
            layers.extend(c.layers)

        # check if any of the layers has working path to the device
        for layer in layers:
            visited = set()

            def visit(node):
                if node in visited:
                    return
                if not self.get_status(node):
                    return
                if node == to_entity:
                    raise StopIteration

                visited.add(node)
                for n in self.get_directly_connected(node, [layer]):
                    visit(n)
            try:
                visit(from_entity)
            except StopIteration:
                return True

        return False

    def get_existing_layers(self):
        return set(layer for i in self.search() for layer in i.layers)

    def clear(self):
        map(self.catalog.uncatalog_object, map(connection_hash, self.search()))
