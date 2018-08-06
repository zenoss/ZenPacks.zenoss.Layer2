##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Glue between Zenoss and more abstract graph, and networkx modules."""

# stdlib imports
import functools

# zenoss imports
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

# third-party imports
import networkx

# zenpack imports
from .graph import get_graph, get_provider
from .connections_provider import IConnectionsProvider

# logging
import logging
LOG = logging.getLogger("zen.Layer2")

# constants
LAYER2_LAYER = "layer2"
LAYER2_NEIGHBOR_DEVICE_DEPTH = 3
DEVICES_PREFIX = "/zport/dmd/Devices/"
DEVICES_NETWORK_PREFIX = "/zport/dmd/Devices/Network/"


def log_mysql_errors(default=None):
    """Log MySQL exceptions in decorated function and return default."""
    from Products.ZenUtils.mysql import MySQLdb

    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except MySQLdb.Error as e:
                LOG.warning("MySQL Error: %s", e)

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


@log_mysql_errors(default=set())
def get_layers():
    """Return set of all known layers."""
    return get_graph().get_layers()


def get_default_layers():
    """Return set of layers to use by default."""
    return {
        x for x in get_layers()
        if not (x.startswith("vlan") or x.startswith("vxlan"))}


@log_mysql_errors(default=networkx.Graph())
def networkx_graph(root, layers, depth=None):
    """Return NetworkX graph of layers at depth starting from root."""
    return get_graph().networkx_graph(root, layers, depth=depth)


@log_mysql_errors(default=[])
def get_neighbors(node, layers, components=False):
    """Return list of all of nodes neighbors."""
    return [
        target for _, target, _ in get_graph().get_edges(node, layers)
        if not (components or target.startswith("!"))]


@log_mysql_errors(default=None)
def get_device_by_mac(dmd, macaddress):
    """Return first neighbor of macaddress that's a device."""
    if not macaddress:
        return

    nxg = networkx_graph(macaddress.upper(), [LAYER2_LAYER], depth=1)
    for node in nxg.nodes():
        if node.startswith(DEVICES_PREFIX):
            try:
                return dmd.getObjByPath(str(node))
            except Exception:
                continue


@log_mysql_errors(default=[])
def get_layer2_neighbor_devices(device):
    """Generate devices that are layer2 neighbors of device."""
    device_uid = device.getPrimaryId()
    nxg = networkx_graph(
        device_uid,
        [LAYER2_LAYER],
        depth=LAYER2_NEIGHBOR_DEVICE_DEPTH)

    for node in nxg.nodes():
        if node.startswith("!"):
            # Component nodes aren't devices.
            continue

        if node == device_uid:
            # The device can't be its own neighbor.
            continue

        try:
            yield device.getObjByPath(str(node))
        except Exception:
            continue


@log_mysql_errors(default=None)
def update_node(node, force=False):
    """Update node and all of its connections in the graph.

    Returns True if the node's connections were updated. Returns False if the
    node's connections were already up to date.

    Always updates the node's connections and returns True if force is True.

    """
    provider = get_provider(IGlobalIdentifier(node).getGUID())
    last_changed = get_last_changed(node)

    if not force and last_changed == provider.lastChange:
        # No need to do anything if we're up-to-date for this node.
        return False

    edges = []
    for connection in IConnectionsProvider(node).get_connections():
        for connected_to in connection.connected_to:
            edges.append((
                connection.entity_id,
                connected_to,
                connection.layers))

    provider.update_edges(edges, last_changed)

    return True


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


@log_mysql_errors(default=None)
def clear():
    """Clear all data."""
    return get_graph().clear()


@log_mysql_errors(default=None)
def should_optimize():
    """Return True if data should be optimized."""
    return get_graph().should_optimize()


@log_mysql_errors(default=None)
def optimize():
    """Optimize all data."""
    return get_graph().optimize()


@log_mysql_errors(default=None)
def compact(providerUUIDs):
    """Clear data from providers not listed in providerUUIDs."""
    return get_graph().compact(providerUUIDs)
