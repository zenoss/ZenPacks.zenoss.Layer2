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

from transaction import commit
from zExceptions import NotFound
from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent

from .connections_provider import IConnection, IConnectionsProvider
from .connections_provider import connection_hash
from .utils import BaseCatalogAPI

log = logging.getLogger('zen.Layer2')


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
        log.debug(
            'Connection from %s to %s on layers %s added to %s',
            connection.entity_id,
            ', '.join(connection.connected_to),
            ', '.join(connection.layers),
            self.name
        )

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection.hash)
        log.debug('%s removed from %s' % (connection, self.name))

    def add_node(self, node, reindex=False):
        map(self.add_connection, IConnectionsProvider(node).get_connections())

        if not reindex:
            return  # ok, we are already done

        commit()
        log.info('Triggering reindex for %s', node)
        notify(IndexingEvent(node))
        if hasattr(node, 'getDeviceComponent'):
            for component in node.getDeviceComponents():
                notify(IndexingEvent(component))

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
        return set(chain(
            self.get_directly_connected(entity_id, layers),
            self.get_reverse_connected(entity_id, layers)
        ))

    def get_connected(self, entity_id, method, layers=None, depth=None):
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
            for n in method(node, layers):
                visit(n, depth)

        visit(entity_id, depth)

        return visited

    def get_bfs_connected(self, entity_id, method, depth, layers=None):
        ''' Return only set of nodes connected on depht distance using BFS '''

        queue = [entity_id]
        distances = {
            entity_id: 0
        }
        while queue:
            next = queue.pop(0)
            distance = distances[next]
            if distance >= depth:
                break
            for n in method(next, layers):
                if n in distances:
                    if distances[n] > distance + 1:
                        distances[n] = distance + 1
                else:
                    queue.append(n)
                    distances[n] = distance + 1

        for k, v in distances.iteritems():
            if v == depth:
                yield k

    def get_obj(self, id):
        ''' Returns object from dmd for some node id or None '''
        try:
            return self.zport.dmd.getObjByPath(id)
        except (NotFound, KeyError) as e:
            return None

    def get_link(self, id):
        ''' Get link attached to node '''
        for brain in self.search(connected_to=id):
            eid = brain.entity_id
            if eid.startswith('!'):
                return self.get_obj(eid[1:])

    def get_node_by_link(self, link):
        ''' Get node by it's attached link '''
        for brain in self.search(entity_id='!' + link):
            return brain.connected_to[0]

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

    def get_device_by_mac(self, mac):
        for brain in self.search(entity_id=mac):
            for c in brain.connected_to:
                if c.startswith('/zport/dmd/Devices/'):
                    return self.get_obj(c)
