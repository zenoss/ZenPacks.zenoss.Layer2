##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, 2014-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Contains function get_connections_json, which returns JSON string with
links and nodes of network map, for d3.js to render.
'''

import collections
import itertools
import json
import logging
import re

from zExceptions import NotFound

from Products.Zuul import getFacade
from zenoss.protocols.services.zep import ZepConnectionError

import networkx

from . import connections

log = logging.getLogger('zen.Layer2')

# TODO: To find optimal batch size values.
ZEP_BATCH_SIZE = 400

MAX_NODES_COUNT = 2000


def get_connections_json(
            data_root, root_id, depth=1, layers=None,
            macs=False, dangling=False):
    '''
        Main function which is used from device to get responce text with
        connections data for graph.
    '''

    obj = data_root.Devices.findDevice(root_id)
    try:
        obj = obj or data_root.dmd.getObjByPath(root_id)
    except KeyError:
        obj = None
    if not obj:
        return serialize('Node %r was not found' % root_id)

    return serialize(get_connections(obj, depth, layers, macs, dangling))


def serialize(*args, **kwargs):
    '''
        If there is at least one positional argument
            and it is is Exception - serialize it's message
            else serialize that first argument.
        If there is only keyword arguments - serialize them as dict.
    '''
    if args:
        if isinstance(args[0], Exception):
            msg = args[0].message
        elif isinstance(args[0], basestring):
            msg = args[0]
        else:
            return json.dumps(args[0], indent=2)
        return serialize(error=msg)
    else:
        return serialize(kwargs)


def get_connections(rootnode, depth=1, layers=None, macs=False, dangling=False):
    # Include layer2 if any VLANs are selected.
    layers = set(layers) or connections.get_default_layers()
    if "layer2" not in layers and any((l.startswith("vlan") for l in layers)):
        layers.add(u"layer2")

    g = connections.networkx_graph(
        root=rootnode.getPrimaryId(),
        layers=layers,
        depth=depth)

    # Remove nodes that should have objects, but don't.
    remove_missing_object_nodes(g, rootnode.dmd)

    # This makes clicking MAC nodes navigate to their associated interface.
    add_path_to_macs(g)

    if not macs:
        # Users may not want to see nodes for individual MAC addresses. So
        # we collapse all subgraphs of contiguous MAC address nodes into a
        # single L2 cloud node that corresponds roughly to a bridge domain.
        collapse_mac_clouds(g)

    # Some nodes such as MAC addresses and L3 networks (IpNetwork) are only
    # shown on the map to connect important nodes. We want to remove any of
    # these connector nodes if they don't connect anything.
    if not dangling:
        remove_dangling_connectors(g)

    nodes = []
    node_indexes = {}
    links = []
    reduced = False

    for i, node in enumerate(g.nodes()):
        if i > MAX_NODES_COUNT:
            reduced = True
            break

        node_indexes[node] = i
        adapter = NodeAdapter(
            node=str(node),
            data=g.node[node],
            dmd=rootnode.dmd)

        nodes.append({
            "name": adapter.name,
            "image": adapter.image,
            "path": adapter.path,
            "uuid": adapter.uuid,
            "color": "severity_none",
            "highlight": adapter.id == rootnode.id,
        })

    for source, target, data in g.edges(data=True):
        if source not in node_indexes or target not in node_indexes:
            # This edge is missing one of its terminating nodes, and is
            # therefore invalid. This could happen if we limited the
            # nodes due to MAX_NODES_COUNT.
            continue

        links.append({
            "source": node_indexes[source],
            "target": node_indexes[target],
            "color": list(data.get("layers", []))
        })

    # Add severity color to nodes.
    color_nodes(nodes)

    return {
        "nodes": nodes,
        "links": links,
        "reduced": reduced,
    }


def remove_missing_object_nodes(g, dmd):
    """Remove nodes from g with a uid, but no object exists for the uid.

    This is required because the Redis database backing the network map is
    not consistent with ZODB. Specifically, devices and component entries in
    the Redis database don't immediately get cleaned up when the devices and
    components are deleted from ZODB.

    The zenmapper service ultimately cleans these up on its next run, but we
    have to work around stale entries regularly.

    """
    nodes_to_remove = []

    for node in g.nodes():
        if node.startswith("/zport/"):
            try:
                dmd.getObjByPath(node)
            except (NotFound, KeyError):
                nodes_to_remove.append(node)

    if nodes_to_remove:
        g.remove_nodes_from(nodes_to_remove)



def add_path_to_macs(g):
    """Add "path" data to MAC address nodes in g.

    Also removes component nodes from g.

    """
    mac_match = re.compile(r'(:?[0-9A-F]:?){12}', re.IGNORECASE).match
    component_nodes = {x for x in g.nodes() if x.startswith("!")}
    mac_nodes = {x for x in g.nodes() if mac_match(x)}

    for component_node in component_nodes:
        for potential_mac in g.edge[component_node]:
            if potential_mac in mac_nodes:
                g.node[potential_mac]["path"] = component_node[1:]
                break

    # Remove component nodes from graph
    g.remove_nodes_from(component_nodes)


def collapse_mac_clouds(g):
    """Collapse subgraphs of MAC address nodes.

    Removes all MAC address nodes from (g: networkx.Graph) and replaces
    them with a "l2-cloud-#" cloud that terminates all of the edges that
    previously terminated in a contiguous subgraph of one or more MAC
    address nodes. In the case that the L2 cloud node would have only
    had two neighbors, no L2 cloud node will be created. An edge will be
    created directly between those two neighbors.

    """
    def collapse_from_mac(mac):
        to_remove = set([mac])
        to_connect = set()
        combined_layers = set()

        visited = set([mac])
        queue = collections.deque([g.edge[mac].items()])
        while queue:
            targets = queue.popleft()
            for target, data in targets:
                if target in visited:
                    continue

                visited.add(target)
                combined_layers.update(data["layers"])

                if target.startswith("/"):
                    to_connect.add(target)
                else:
                    to_remove.add(target)
                    queue.append(g.edge[target].items())

        return to_remove, to_connect, combined_layers

    l2_cloud_index = 0

    queue = collections.deque(x for x in g.nodes() if not x.startswith("/"))
    while queue:
        starting_mac = queue.popleft()
        remove, connect, layers = collapse_from_mac(starting_mac)

        # Remove the MAC address nodes in starting_mac's cluster.
        g.remove_nodes_from(remove)
        for node in remove:
            if node != starting_mac:
                queue.remove(node)

        # Create a direct link when connecting exactly 2 nodes.
        if len(connect) == 2:
            g.add_edge(*connect, layers=layers)

        # Create a cloud when connecting 3 or more nodes.
        elif len(connect) >= 3:
            l2_cloud = "l2-cloud-{}".format(l2_cloud_index)
            l2_cloud_index += 1

            for connect_node in connect:
                g.add_edge(l2_cloud, connect_node, layers=layers)


def remove_dangling_connectors(g):
    """Remove connector nodes from g that don't connect anything important."""
    def is_connector(n):
        """Return True if n (node) is a connector."""
        return (
            not n.startswith("/")
            or n.startswith("/zport/dmd/Networks/")
            or n.startswith("/zport/dmd/IPv6Networks/"))

    def is_dangling(n):
        """Return True if n (node) is dangling (has 1 or less edges.)"""
        return len(g.edge[n]) < 2

    all_connectors = {x for x in g.nodes() if is_connector(x)}
    dangling_connectors = {x for x in all_connectors if is_dangling(x)}
    connecting_connectors = all_connectors.difference(dangling_connectors)

    # Remove connector nodes from graph if they don't connect anything.
    g.remove_nodes_from(dangling_connectors)

    # Useful nodes are nodes on a shortest path from an important node
    # to another important node.
    useful_nodes = itertools.chain.from_iterable(
        td
        for s, sd in networkx.all_pairs_shortest_path(g).iteritems()
        for t, td in sd.iteritems()
        if not (is_connector(s) or is_connector(t)))

    # Redundant connectors are connector nodes not in useful_nodes.
    redundant_connectors = connecting_connectors.difference(useful_nodes)

    # Remove connector nodes from graph if they're redundant.
    g.remove_nodes_from(redundant_connectors)


def color_nodes(nodes):
    """Add "color" property to each NodeAdapter in nodes."""
    zep = getFacade("zep")
    nodes_by_uuid = {x["uuid"]: x for x in nodes if x["uuid"]}
    try:
        for uuids_chunk in chunks(nodes_by_uuid.keys(), ZEP_BATCH_SIZE):
            severities_by_uuid = zep.getWorstSeverity(uuids_chunk)
            for uuid, severity in severities_by_uuid.iteritems():
                if uuid in nodes_by_uuid:
                    nodes_by_uuid[uuid]["color"] = {
                        1: 'severity_debug',
                        2: 'severity_info',
                        3: 'severity_warning',
                        4: 'severity_error',
                        5: 'severity_critical',
                        }.get(severity, 'severity_none')

    except ZepConnectionError as e:
        log.warning("Couldn't connect to ZEP: %s", e)


def chunks(s, n):
    """Generate lists of size n from iterable s."""
    for chunk in (s[i:i + n] for i in range(0, len(s), n)):
        yield chunk


class NodeAdapter(object):
    def __init__(self, node, data, dmd):
        if isinstance(node, str):
            try:
                self.node = dmd.getObjByPath(node)
            except (NotFound, KeyError) as e:
                self.node = node
        else:
            self.node = node

        self.data = data

    @property
    def id(self):
        if hasattr(self.node, 'macaddress'):
            return self.node.id
        elif hasattr(self.node, 'getNetworkName'):
            return self.node.getNetworkName()
        elif hasattr(self.node, 'id'):
            return self.node.id
        else:
            return self.node

    @property
    def path(self):
        if "path" in self.data:
            return self.data["path"]
        elif hasattr(self.node, 'getPrimaryUrlPath'):
            return self.node.getPrimaryUrlPath()
        else:
            return self.node

    @property
    def name(self):
        if hasattr(self.node, 'macaddress'):
            return self.node.macaddress
        elif hasattr(self.node, 'getNetworkName'):
            network_name = self.node.getNetworkName()
            if '...' in network_name:
                return re.sub(
                    '::+', '::',
                    network_name.replace('.', ':')
                )
            return network_name

        elif hasattr(self.node, 'titleOrId'):
            return self.node.titleOrId()
        else:
            if self.id.startswith('l2-cloud-'):
                return ""

            title = self.id
            if title.startswith('/zport/dmd/'):
                title = title.split('/')[-1]
            return title

    @property
    def image(self):
        if hasattr(self.node, 'macaddress'):
            return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'
        elif hasattr(self.node, 'getIconPath'):
            return self.node.getIconPath()
        else:
            return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'

    @property
    def uuid(self):
        if hasattr(self.node, 'getUUID'):
            return self.node.getUUID()

        return None
