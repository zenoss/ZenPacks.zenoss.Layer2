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
import cPickle as pickle
from collections import namedtuple

from zExceptions import NotFound
from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent

from .connections_provider import IConnection, IConnectionsProvider

log = logging.getLogger('zen.Layer2')


DEFAULT_REDIS_URLS = ['redis://localhost:6379/1', 'redis://localhost:16379/1']  # 5.x, 4.x
BACKWARD_PREFIX = 'b_'
DEFAULT_CATALOG_NAME = 'l2'
# TODO: To find optimal batch size value.
BATCH_SIZE = 400


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
    Brain = namedtuple('Brain', fields)
    # layers list key
    existing_layers_key = 'existing_layers'

    def __init__(self, name, redis_url=None):
        super(ConnectionsCatalog, self).__init__()
        self.name = name
        self.b_prefix = BACKWARD_PREFIX
        self.redis = self.get_redis(redis_url)

    def get_redis(self, redis_url=None):
        """
        Use Redis URL if specified, otherwise try to use
        default URLs for 5.x and 4.x.
        """
        if redis_url:
            redis_urls = [redis_url]
        else:
            redis_urls = DEFAULT_REDIS_URLS

        last_error = None
        for url in redis_urls:
            try:
                r = redis.StrictRedis.from_url(url)
                r.get(None)
                last_error = None
                break
            except redis.exceptions.ConnectionError as e:
                last_error = e

        if last_error:
            raise last_error

        return r

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
        # Prepare batch of commands to be executed
        pipe = self.redis.pipeline(transaction=False)

        # Store connection
        pipe.sadd(
            self.prepId(obj.entity_id),
            pickle.dumps({field: getattr(obj, field) for field in self.fields})
        )
        # Store backward connections as well, in the name of faster search
        # this used in get_reverse_connected()
        for path in obj.connected_to:
            pipe.sadd(
                self.prepId(self.b_prefix + path),
                pickle.dumps({
                    'entity_id': path,
                    'layers': obj.layers,
                    'connected_to': obj.entity_id
                })
            )
        # Store layers list in set for faster retrieval
        for layer in obj.layers:
            pipe.sadd(self.prepId(self.existing_layers_key), layer)

        # Finally execute batched redis commands
        pipe.execute()

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
        On large installation this should not be called often.
        """
        self.redis.flushdb()

    def search(self, **query):
        """
        Looks into Redis keys and mimics ZCatalog behaviour in same time.
        """
        connections = []
        pattern = self.prepId('*')
        keys = []

        # Direct connections lookup
        if 'entity_id' in query:
            entity_id = query['entity_id']
            if isinstance(entity_id, basestring):
                entity_id = (entity_id, )

            keys.extend(self.prepId(id) for id in entity_id)
        # Backward connections lookup
        if 'connected_to' in query:
            connected_to = query['connected_to']
            if isinstance(connected_to, basestring):
                connected_to = (connected_to, )

            keys.extend(self.prepId(self.b_prefix + id) for id in connected_to)

        if len(keys) > 1:
            for member in self.redis.sunion(keys):
                connections.append(self.Brain(**pickle.loads(member)))
        elif len(keys) == 1:
            for member in self.redis.smembers(keys[0]):
                connections.append(self.Brain(**pickle.loads(member)))
        else: # Not normally should be used at all, consider remove this clause
            log.warn('Redis KEYS command may be very slow on large dataset')
            # TODO: think of Redis SCAN / scan_iter
            # https://github.com/andymccurdy/redis-py/blob/master/redis/client.py#L1401
            for key in self.redis.keys(pattern=pattern):
                if key != self.prepId(self.existing_layers_key):
                    for member in self.redis.smembers(key):
                        connections.append(self.Brain(**pickle.loads(member)))

        # Gracefully filters by layers if asked
        if 'layers' in query and query['layers']:
            connections = [x for x in connections \
                if set(x.layers).intersection(set(query['layers']))]

        return connections

    def get_existing_layers(self):
        '''
        Returns list of registered layers in catalog
        '''
        return self.redis.smembers(self.prepId(self.existing_layers_key))


class BaseCatalogAPI(object):
    ''' Provides a methods to store and retrieve data in catalog '''

    zport = None
    name = None

    def __init__(self, zport, name=DEFAULT_CATALOG_NAME, redis_url=None):
        self.zport = zport
        self.name = name
        self.catalog = ConnectionsCatalog(self.name, redis_url)

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
            connection.connected_to,
            connection.layers,
            self.name
        )

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection)
        log.debug('%s removed from %s' % (connection, self.name))

    def is_changed(self, node):
        '''
        Check if node was modified from previous cataloging
        '''
        val = None
        attr = None
        if hasattr(node, 'getLastChangeString'):
            attr = 'getLastChangeString'
        elif hasattr(node, 'getModificationTimeString'):
            attr = 'getModificationTimeString'

        if attr:
            try:
                val = getattr(node, attr)()
            except AttributeError:
                val = None

        if val:
            rid = self.catalog.prepId(node._guid)
            if self.catalog.redis.get(rid) == val:
                return False
            self.catalog.redis.set(rid, val)
        return True

    def add_node(self, node, reindex=False):
        if self.is_changed(node):
            for connection in IConnectionsProvider(node).get_connections():
                self.add_connection(connection)

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
        q = dict(entity_id=entity_id, connected_to=entity_id)
        if layers:
            q['layers'] = layers
        for b in self.search(**q):
            if isinstance(b.connected_to, basestring):
                yield b.connected_to
            else:
                for c in b.connected_to:
                    yield c

    def get_connected(self, entity_id, method, layers=None, depth=None):
        ''' Return set of all connected nodes '''
        visited = set()

        def visit(nodes, depth):
            if depth is not None and depth < 0:
                return
            nodes_to_check = list(set(nodes).difference(visited))
            if not nodes_to_check:
                return
            visited.update(nodes_to_check)

            if depth is not None:
                depth -= 1

            for pos in xrange(0, len(nodes_to_check), BATCH_SIZE):
                nodes_to_visit = method(nodes_to_check[pos:pos + BATCH_SIZE], layers)
                visit(nodes_to_visit, depth)

        visit([entity_id], depth)

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
        try:
            return IConnectionsProvider(node).get_status()
        except TypeError:
            return True

    def check_working_path(self, from_entity, to_entity):
        visited = set([from_entity])

        nodes = self.search(entity_id=from_entity)
        layers = set()
        for node in nodes:
            for layer in node.layers:
                layers.add(layer)

        def visit(node):
            if node in visited:
                return
            if not self.get_status(node):
                return
            if node == to_entity:
                raise StopIteration
            visited.add(node)

            for next_node in self.get_directly_connected(node, layers):
                visit(next_node)

        try:
            for node in nodes:
                visit(from_entity)
        except StopIteration:
            return True

        return False

    def get_existing_layers(self):
        return self.catalog.get_existing_layers()

    def get_device_by_mac(self, mac):
        for brain in self.search(entity_id=mac):
            for c in brain.connected_to:
                if c.startswith('/zport/dmd/Devices/'):
                    return self.get_obj(c)
