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

import json
import logging
import re

from zExceptions import NotFound

from Products.Zuul import getFacade
from zenoss.protocols.services.zep import ZepConnectionError

from . import connections
from .edge_contraction import contract_edges

log = logging.getLogger('zen.Layer2')

# TODO: To find optimal batch size values.
ZEP_BATCH_SIZE = 400

MAX_NODES_COUNT = 2000


def get_connections_json(
    data_root, root_id, depth=1, layers=None, full_map=False
):
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

    connections = get_connections(obj, depth, layers)
    if not full_map:
        connections = contract_edges(**connections)

    return serialize(connections)


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


def get_connections(rootnode, depth=1, layers=None):
    # Include layer2 if any VLANs are selected.
    layers = set(layers) or connections.get_layers()
    if "layer2" not in layers and any((l.startswith("vlan") for l in layers)):
        layers.add(u"layer2")

    g = connections.networkx_graph(
        root=rootnode.getPrimaryId(),
        layers=layers,
        depth=depth)

    nodes = []
    node_indexes = {}
    links = []
    reduced = False

    for i, node in enumerate(g.nodes()):
        if i > MAX_NODES_COUNT:
            reduced = True
            break

        node_indexes[node] = i
        adapter = NodeAdapter(node=str(node), dmd=rootnode.dmd)
        nodes.append({
            "name": adapter.titleOrId(),
            "image": adapter.getIconPath(),
            "path": adapter.get_link(),
            "color": "severity_none",
            "highlight": adapter.id == rootnode.id,
            "important": adapter.important,
            "uuid": adapter.getUUID(),
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


def color_nodes(nodes):
    """Add "color" property to each NodeAdapter in nodes."""
    zep = getFacade("zep")
    nodes_by_uuid = {x["uuid"]: x for x in nodes if x["important"]}
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
    def __init__(self, node, dmd):
        if isinstance(node, str):
            try:
                self.node = dmd.getObjByPath(node)
            except (NotFound, KeyError) as e:
                self.node = node
        else:
            self.node = node

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

    def get_link(self):
        if hasattr(self.node, 'getPrimaryUrlPath'):
            return self.node.getPrimaryUrlPath()
        elif hasattr(self, 'link'):
            return self.link
        else:
            return self.node

    def titleOrId(self):
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
            title = self.id
            if title.startswith('/zport/dmd/'):
                title = title.split('/')[-1]
            return title

    def getIconPath(self):
        if hasattr(self.node, 'macaddress'):
            return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'
        elif hasattr(self.node, 'getIconPath'):
            return self.node.getIconPath()
        else:
            return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'

    def getUUID(self):
        if hasattr(self.node, 'getUUID'):
            return self.node.getUUID()

        return None

    @property
    def important(self):
        if isinstance(self.node, str):
            return False
        from Products.ZenModel.IpNetwork import IpNetwork
        if (
            hasattr(self.node, 'aq_base') and
            isinstance(self.node.aq_base, IpNetwork)
        ):
            return False
        return True
