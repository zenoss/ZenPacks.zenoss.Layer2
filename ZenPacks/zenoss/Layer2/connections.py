##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Glue between Zenoss and more abstract graph, networkx, and redis modules."""

# stdlib imports
import functools

# zenoss imports
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

# third-party imports
import networkx
import redis

# zenpack imports
from . import graph
from .connections_provider import IConnectionsProvider

# logging
import logging
LOG = logging.getLogger("zen.Layer2")

# constants
GRAPH_NAMESPACE = "g"
LAYER2_LAYER = "layer2"
LAYER2_NEIGHBOR_DEVICE_DEPTH = 3
DEVICES_PREFIX = "/zport/dmd/Devices/"
DEVICES_NETWORK_PREFIX = "/zport/dmd/Devices/Network/"


def log_redis_errors(default=None):
    """Log RedisError in decorated function and return default."""
    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except redis.RedisError as e:
                LOG.exception("Redis Error: %s", e)

                # Avoid problems with mutable default value.
                if isinstance(default, set):
                    return set()
                elif isinstance(default, list):
                    return []
                elif isinstance(default, networkx.Graph):
                    return networkx.Graph()
                else:
                    return default

        return wrapper

    return wrap


@log_redis_errors(default=set())
def get_layers():
    """Return set of all known layers."""
    g = graph.Graph(GRAPH_NAMESPACE)
    return g.get_layers()


@log_redis_errors(default=networkx.Graph())
def networkx_graph(root, layers, depth=None):
    """Return NetworkX graph of layers at depth starting from root."""
    g = graph.Graph(GRAPH_NAMESPACE)
    return g.networkx_graph(root, layers, depth=depth)


@log_redis_errors(default=[])
def get_neighbors(node, layers):
    """Return list of all of nodes neighbors."""
    g = graph.Graph(GRAPH_NAMESPACE)
    return [target for _, target, _ in g.get_edges(node, layers)]


@log_redis_errors(default=None)
def get_device_by_mac(dmd, macaddress):
    """Return first neighbor of macaddress that's a device."""
    nxg = networkx_graph(macaddress, [LAYER2_LAYER], depth=1)
    for node in nxg.nodes():
        if node.startswith(DEVICES_PREFIX):
            try:
                return dmd.getObjByPath(str(node))
            except Exception:
                continue


@log_redis_errors(default=[])
def get_layer2_neighbor_devices(device):
    """Generate devices that are layer2 neighbors of device."""
    device_uid = device.getPrimaryId()
    nxg = networkx_graph(
        device_uid,
        [LAYER2_LAYER],
        depth=LAYER2_NEIGHBOR_DEVICE_DEPTH)

    for node in nxg.nodes():
        if node == device_uid:
            # The device can't be its own neighbor.
            continue

        try:
            yield device.getObjByPath(str(node))
        except Exception:
            continue


@log_redis_errors(default=None)
def add_node(node, force=False):
    """Add node and all of its connections to the graph."""
    guid = IGlobalIdentifier(node).getGUID()
    origin = graph.Origin(GRAPH_NAMESPACE, guid)
    last_changed = get_last_changed(node)

    if not force and last_changed == origin.get_checksum:
        # No need to do anything if we're up-to-date for this node.
        return

    edges = []
    for connection in IConnectionsProvider(node).get_connections():
        for connected_to in connection.connected_to:
            edges.append((
                connection.entity_id,
                connected_to,
                connection.layers))

    origin.clear()
    origin.add_edges(edges, last_changed)


def is_switch(device):
    """Return True if device is "switchy", and False if "hosty"."""
    return device.getDeviceClassName().startswith("/Network/")


def get_last_changed(node):
    """Return string indicating last time node was changed.

    The string doesn't have to necessarily have to represent time. It
    just needs to be a high precision value that can be used to know
    that if the value returned is different from a value returned at a
    point in history, then the node has changed since then.

    """
    try:
        # Prefer this because it should be available on devices, and is
        # an "application" value that can even be updated within a
        # transaction.
        return node.getLastChange().micros()
    except Exception:
        pass

    try:
        # Fall back to this because all ZenModelRM objects (at least)
        # have it. It's not as good because it's probably only the last
        # time the object was committed. So if we call it twice within
        # the same transaction before and after useful changes have
        # occurred, we'll think that no useful changes have occurred.
        return node.bobobase_modification_time().micros()
    except Exception:
        pass


def get_status(dmd, node):
    """Return False if node is "down". Otherwise return True."""
    try:
        obj = dmd.getObjByPath(node)
    except Exception:
        return True

    try:
        return IConnectionsProvider(obj).get_status()
    except Exception:
        return True


@log_redis_errors(default=None)
def clear():
    """Clear all data for all origins."""
    g = graph.Graph(GRAPH_NAMESPACE)
    g.clear()


@log_redis_errors(default=None)
def compact(guids):
    """Clear data from origins not listed in guids."""
    g = graph.Graph(GRAPH_NAMESPACE)
    g.compact(guids)
