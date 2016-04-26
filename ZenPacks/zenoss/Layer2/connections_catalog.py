##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Contains CatalogAPI class that is used for connections catalog access.

Usage:
    from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
    cat = CatalogAPI(dmd.zport)

    cat.search(**query) # to get brains
    cat.show_content(**query) # to show content in stdout
    # query could be empty
'''

from itertools import chain
import logging
import redis
import pickle
from collections import namedtuple

from zExceptions import NotFound
from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent

from .connections_provider import IConnection, IConnectionsProvider

log = logging.getLogger('zen.Layer2')


# TODO: add to zenmapper an options to run on remote server.
# This may be useful for big Zenoss installations
REDIS_HOST = 'localhost'
REDIS_PORT = 16379
REDIS_DB = 0
BACKWARD_PREFIX = 'b_'
DEFAULT_CATALOG_NAME = 'l2'


class ConnectionsCatalog(object):
    ''' This is actual storage of Layer2 connections '''

    name = None # name is prefix for all keys stored in redis
    b_prefix = None # backward connection prefix
    redis = None

    # fields to store for entity (pickled)
    fields = [
        'entity_id',
        'connected_to',
        'layers'
    ]

    def __init__(self, name):
        super(ConnectionsCatalog, self).__init__()
        self.name = name
        self.b_prefix = BACKWARD_PREFIX
        self.redis = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT,
            db=REDIS_DB)

    def prepId(self, oid):
        """
        Use self name as a prefix to store and retrieve keys
        to not clash with other who may store daya in same Redis DB
        """
        return self.name + '_' + oid

    def catalog_object(self, obj, uid=None):
        """
        Saves connection and backward connection in Redis database.
        uid - leaved for backward compatibility with 1.1.x
        """
        # Store connection
        self.redis.sadd(
            self.prepId(obj.entity_id),
            pickle.dumps({field: getattr(obj, field) for field in self.fields})
        )
        # Store backward connections as well, in the name of faster search
        # this used in get_reverse_connected()
        for path in obj.connected_to:
            self.redis.sadd(
                self.prepId(self.b_prefix + path),
                pickle.dumps({
                    'entity_id': path,
                    'layers': obj.layers,
                    'connected_to': obj.entity_id
                })
            )

    def uncatalog_object(self, connection=None):
        """
        Removes connection from Redis database
        """
        if not connection:
            return
        self.redis.delete(self.prepId(connection.entity_id))
        for path in connection.connected_to:
            self.redis.delete(self.prepId(self.b_prefix + path))

    def clear(self):
        """
        Removes ALL connections records.
        """
        # TODO: Zenoss 5.x may have newer version of redis library
        # with iterator for keys. This may help in performance.
        for k in self.redis.keys(pattern=self.prepId('*')):
            self.redis.delete(k)
        for k in self.redis.keys(pattern=self.prepId(self.b_prefix + '*')):
            self.redis.delete(k)

    def search(self, **query):
        """
        Looks into Redis keys and mimics ZCatalog behaviour in same time.
        """
        Brain = namedtuple('Brain', ', '.join(self.fields))
        connections = []
        pattern = self.prepId('*')

        # Direct connections lookup
        if 'entity_id' in query:
            pattern = self.prepId(query['entity_id'])
        # Backward connections lookup
        if 'connected_to' in query:
            pattern = self.prepId(self.b_prefix + query['connected_to'])

        # TODO: think of Redis batch job to reduce HTTP handshakes
        for key in self.redis.keys(pattern=pattern):
            for member in self.redis.smembers(key):
                connections.append(Brain(**pickle.loads(member)))

        # Gracefully filters by layers if asked
        if 'layers' in query and query['layers']:
            connections = [x for x in connections \
                if set(x.layers).intersection(set(query['layers']))]

        return connections


class BaseCatalogAPI(object):
    ''' Provides a methods to store and retrieve data in catalog '''

    zport = None
    name = None

    def __init__(self, zport, name=DEFAULT_CATALOG_NAME):
        self.zport = zport
        self.name = name
        self.catalog = ConnectionsCatalog(name=self.name)

    def clear(self):
        self.catalog.clear()

    def search(self, **query):
        return self.catalog.search(**query)

    def show_content(self, **query):
        ''' Used to watch content of catalog '''
        for b in self.search(**query):
            print b


class CatalogAPI(BaseCatalogAPI):

    @staticmethod
    def validate_connection(connection):
        connection = IConnection(connection)
        IConnection.validateInvariants(connection)
        return connection

    def add_connection(self, connection):
        ''' Add a connection to a catalog '''
        connection = self.validate_connection(connection)

        self.catalog.catalog_object(connection)
        log.debug(
            'Connection from %s to %s on layers %s added to %s',
            connection.entity_id,
            ', '.join(connection.connected_to),
            ', '.join(connection.layers),
            self.name
        )

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection)
        log.debug('%s removed from %s' % (connection, self.name))

    def add_node(self, node, reindex=False):
        map(self.add_connection, IConnectionsProvider(node).get_connections())

        if not reindex:
            return  # ok, we are already done

        # TODO: make sure for what reason this was done previously
        # and remove it if not needed anymore
        # Assumption is: it may be needed for patches/index_object
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
            yield b.connected_to

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
        ''' Return only set of nodes connected on depth distance using BFS '''

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
