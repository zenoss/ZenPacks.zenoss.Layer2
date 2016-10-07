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
import os
import redis
import cPickle as pickle
from collections import namedtuple

from zExceptions import NotFound
from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent
from Products.Zuul.decorators import memoize
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from Products.ZenUtils.Utils import zenPath
from Products.ZenModel.IpNetwork import IpNetwork

from .connections_provider import IConnection, IConnectionsProvider

log = logging.getLogger('zen.Layer2')


BACKWARD_PREFIX = 'b_'
DEFAULT_CATALOG_NAME = 'l2'
# TODO: To find optimal batch size value.
BATCH_SIZE = 400


@memoize
def discover_redis_url():
    """Return the correct redis URL or None if unavailable.

    Zenoss 5 will have the CONTROLPLANE environment variable set to 1,
    and will have redis on it's standard 6379 port.

    Zenoss 4 will write the port into $ZENHOME/var/redis.conf, but only
    on the host running zredis. Remote hubs won't be able automatically
    discovery their redis URL. So we'll attempt to load it from a
    REDIS_URL environment variable.

    """
    if os.environ.get("CONTROLPLANE"):
        return "redis://localhost:6379/1"

    env_redis_url = os.environ.get("REDIS_URL")
    if env_redis_url:
        return env_redis_url

    try:
        with open(zenPath("var", "redis.conf"), "r") as redis_conf:
            for line in redis_conf:
                if line.startswith("port"):
                    try:
                        port = line.strip().split()[1]
                    except Exception:
                        continue
                    else:
                        return "redis://localhost:{}/1".format(port)
    except Exception:
        return


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
    # indexed nodes GUIDs
    existing_nodes_key = 'existing_nodes'

    def __init__(self, name, redis_url=None):
        super(ConnectionsCatalog, self).__init__()
        self.name = name
        self.b_prefix = BACKWARD_PREFIX
        self.redis = self.get_redis(redis_url)

    def get_redis(self, redis_url=None):
        """Return StrictRedis instance given redis_url.

        The correct redis_url will be discovered from the environment
        if it isn't specified.

        """
        if not redis_url:
            redis_url = discover_redis_url()
            if not redis_url:
                raise Exception("Unable to discover redis URL.")

        r = redis.StrictRedis.from_url(redis_url)
        r.get(None)

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
        keys = [self.prepId(obj.entity_id)]
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
            key = self.prepId(self.b_prefix + path)
            keys.append(key)
            pipe.sadd(
                key,
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

        # Returned keys list to get all connection indexes for a node
        return keys

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
                try:
                    for member in self.redis.smembers(key):
                        connections.append(self.Brain(**pickle.loads(member)))
                except Exception:
                    pass

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

        log.debug(
            'Connection from %s to %s on layers %s added to %s',
            connection.entity_id,
            connection.connected_to,
            connection.layers,
            self.name
        )

        return self.catalog.catalog_object(connection)

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection)
        log.debug('%s removed from %s' % (connection, self.name))

    def compact_catalog(self, guids):
        """
        Removes obsolete nodes
        """
        cat = self.catalog
        key = cat.prepId(cat.existing_nodes_key)
        nodes = cat.redis.smembers(key)
        obsolete_guids = set(nodes) - set(guids)

        pipe = cat.redis.pipeline(transaction=False)
        for guid in obsolete_guids:
            self.remove_node(guid)
        pipe.srem(key, obsolete_guids)
        pipe.execute()

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
            cat = self.catalog
            rid = cat.prepId(IGlobalIdentifier(node).getGUID())
            if cat.redis.get(rid) == val:
                return False
            cat.redis.set(rid, val)
        return True

    def _add_node(self, node, keys):
        """
        Adds node GUID to list of all indexed nodes
        and list of associated connections' keys
        """
        guid = IGlobalIdentifier(node).getGUID()
        cat = self.catalog
        keys_key = cat.prepId(cat.b_prefix + guid)

        pipe = cat.redis.pipeline(transaction=False)
        pipe.sadd(cat.prepId(cat.existing_nodes_key), guid)
        for key in set(keys):
            pipe.sadd(keys_key, key)
        pipe.execute()

    def add_node(self, node, reindex=False, force=False):
        """
        Adds node connections to index
        """
        if force or self.is_changed(node):
            self.remove_node(node, update=True)
            keys = []
            for connection in IConnectionsProvider(node).get_connections():
                keys.extend(self.add_connection(connection))
            self._add_node(node, keys)

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

    def remove_node(self, node, update=False):
        """
        Removes node connections and other associated records
        """
        if update and isinstance(node, IpNetwork):
            return
        if isinstance(node, basestring):
            guid = node
        else:
            guid = IGlobalIdentifier(node).getGUID()
        cat = self.catalog
        keys_key = cat.prepId(cat.b_prefix + guid)
        pipe = cat.redis.pipeline(transaction=False)

        keys = cat.redis.smembers(keys_key)
        if keys:
            for key in keys:
                pipe.delete(key)

        pipe.srem(cat.prepId(cat.existing_nodes_key), guid)
        pipe.delete(keys_key)
        if not update:
            pipe.delete(cat.prepId(guid))
        pipe.execute()

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
            for node in nodes_to_check:
                yield node
            visited.update(nodes_to_check)

            if depth is not None:
                depth -= 1

            for pos in xrange(0, len(nodes_to_check), BATCH_SIZE):
                nodes_to_visit = method(nodes_to_check[pos:pos + BATCH_SIZE],
                                        layers)
                for node in visit(nodes_to_visit, depth):
                    yield node

        for node in visit([entity_id], depth):
            yield node

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
