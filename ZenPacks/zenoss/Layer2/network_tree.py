##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Contains function get_connections_json, which returns JSON string with
links and nodes of network map, for d3.js to render.
'''

import copy
import json
from functools import partial
import re

import logging

from zExceptions import NotFound

from Products.Zuul import getFacade
from zenoss.protocols.services.zep import ZepConnectionError

from .connections_catalog import CatalogAPI
from .edge_contraction import contract_edges

log = logging.getLogger('zen.Layer2')

# TODO: To find optimal batch size values.
ZEP_BATCH_SIZE = 400
CATALOG_BATCH_SIZE = 400

MAX_NODES_COUNT = 2000


class StopTraversing(Exception):

    """Raised when max nodes count is reached to stop network map generation."""

    pass


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


SEVERITY_TO_COLOR = {
    1: 'severity_debug',
    2: 'severity_info',
    3: 'severity_warning',
    4: 'severity_error',
    5: 'severity_critical'}


def _convert_severity_to_color(severity):
    return SEVERITY_TO_COLOR.get(severity, 'severity_none')


def get_connections(rootnode, depth=1, layers=None):
    zport = rootnode.zport
    cat = CatalogAPI(zport)

    nodes = []
    links = {}
    colors = {}  # mapping from pair of nodes to their layers
    nodenums = {}
    uuids = []

    # VLAN -> VLAN, Layer2 (search by vlan,
    # but include also vlan unaware sections of network)
    # Layer2 -> Layer2      (no search by vlans)
    # VLAN, Layer2 -> Layer2 (no search by vlans)
    if layers:
        # copy so we not mutate function argument
        layers = map(str, layers)  # and also coerce to str (unicode happens)
        if 'layer2' in layers:
            layers = [l for l in layers if not l.startswith('vlan')]
        else:
            if any((l.startswith('vlan') for l in layers)):
                layers.append('layer2')

    def add_node(n):
        if len(nodes) >= MAX_NODES_COUNT:
            raise StopTraversing()

        if n.id in nodenums:
            return

        nodenums[n.id] = len(nodes)
        record = dict(
            name=n.titleOrId(),
            image=n.getIconPath(),
            path=n.get_link(),
            color='severity_none',
            highlight=n.id == rootnode.id,
            important=n.important,
        )
        nodes.append(record)

        uuid = n.getUUID()
        if n.important and uuid:
            uuids.append((uuid, record))

    def add_link(a, b):
        color = colors[(a.get_path(), b.get_path())]
        s = nodenums[a.id]
        t = nodenums[b.id]

        key = tuple(sorted([s, t]))
        if key in links:
            if s == links[key]['source']:
                return  # already added
            else:
                links[key]['directed'] = False
                return

        links[key] = dict(
            source=s,
            target=t,
            directed=True,
            color=color,
        )

    adapt_node = partial(NodeAdapter, dmd=zport.dmd)

    visited = set()

    def get_connections(nodes, depth):
        """ Depth-first search of the network tree emanating from nodes """
        if depth == 0:
            return set()

        adapted_nodes = {}
        for node in nodes:
            adapted_node = adapt_node(node)
            if adapted_node.id in visited:
                continue
            visited.add(adapted_node.id)
            adapted_nodes[adapted_node.get_path()] = adapted_node

        # leafs of current node in graph
        impacted = get_impacted(adapted_nodes.keys())
        impactors = get_impactors(adapted_nodes.keys())

        related = copy.deepcopy(impacted)
        for node_path, links in impactors.iteritems():
            related[node_path] = set(related.get(node_path, [])) | set(links)

        # some of leaf may contain a component (usualy IpInterface) uid
        # prefixed with asterix (!)
        for node_path, links in related.iteritems():
            adapted_node = adapted_nodes[node_path]
            for link_node in links:
                if this_is_link(link_node):
                    adapted_node.link = link_node[1:]
                    break

        for node in adapted_nodes.itervalues():
            add_node(node)

        nodes_to_check = set()
        for node_path, links in related.iteritems():
            adapted_node = adapted_nodes[node_path]

            interesting_links = [link_node for link_node in links
                                 if not this_is_link(link_node)]

            reverse_connections = get_reverse_connected(interesting_links)

            for link_node in interesting_links:
                link_adapted_node = adapt_node(link_node)
                # need to check for uid in leafs before adding node to graph
                # as next time it will be skipped due to optimization
                for node_b in reverse_connections.get(link_node, []):
                    if this_is_link(node_b):
                        link_adapted_node.link = node_b[1:]
                        break

                add_node(link_adapted_node)
                if link_node in impacted.get(node_path, []):
                    add_link(adapted_node, link_adapted_node)
                if link_node in impactors.get(node_path, []):
                    add_link(link_adapted_node, adapted_node)

                nodes_to_check.add(link_node)

        return nodes_to_check

    def get_reverse_connected(nodes):
        q = dict(connected_to=nodes)
        if layers:
            q['layers'] = layers

        result = {}
        for b in cat.search(**q):
            result.setdefault(b.entity_id, []).append(b.connected_to)

        return result

    def connection_not_in_this_vlans(edge, filter_layers):
        return (
            # check that we filter by vlans at all
            any((l.startswith('vlan') for l in filter_layers))
            # and check that this edge is vlan-aware (has some vlans)
            and any((l.startswith('vlan') for l in edge.layers))
            # all of the vlans of edge are not vlans we are interested in
            and all((
                l not in filter_layers
                for l in edge.layers
                if l.startswith('vlan')
            ))
        )

    def get_impacted(nodes):
        q = dict(entity_id=nodes)
        if layers:
            q['layers'] = layers

        result = {}
        for b in cat.search(**q):
            if connection_not_in_this_vlans(b, layers):
                continue
            for c in b.connected_to:
                colors[(b.entity_id, c)] = b.layers
                result.setdefault(b.entity_id, []).append(c)

        return result

    def get_impactors(nodes):
        q = dict(connected_to=nodes)
        if layers:
            q['layers'] = layers
        result = {}
        for b in cat.search(**q):
            if connection_not_in_this_vlans(b, layers):
                continue
            colors[(b.connected_to, b.entity_id)] = b.layers
            result.setdefault(b.entity_id, []).append(b.connected_to)

        return result

    def this_is_link(node):
        if isinstance(node, str) and node[0] == "!":
            return node[1:]

    nodes_queue = [rootnode]
    iteration_depth = depth
    reduced_result = False
    try:
        while nodes_queue:
            nodes_to_check = set()
            for pos in xrange(0, len(nodes_queue), CATALOG_BATCH_SIZE):
                nodes_to_check.update(
                    get_connections(nodes_queue[pos:pos + CATALOG_BATCH_SIZE],
                                    iteration_depth))

            nodes_queue = list(nodes_to_check)
            iteration_depth -= 1
    except StopTraversing:
        reduced_result = True

    zep = getFacade('zep', zport)

    try:
        for pos in xrange(0, len(uuids), ZEP_BATCH_SIZE):
            sevs = zep.getWorstSeverity(
                [uuid for uuid, _ in uuids[pos:pos + ZEP_BATCH_SIZE]])

            for uuid, record in uuids[pos:pos + ZEP_BATCH_SIZE]:
                if uuid in sevs:
                    record['color'] = _convert_severity_to_color(sevs[uuid])
    except ZepConnectionError as err:
        log.warning('Could not connect to ZEP: %s', err)

    return dict(
        links=links.values(),
        nodes=nodes,
        reduced=reduced_result
    )


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

    def get_path(self):
        if hasattr(self.node, 'macaddress'):
            return self.node.macaddress
        elif hasattr(self.node, 'getPrimaryUrlPath'):
            return self.node.getPrimaryUrlPath()
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

    def getColor(self):
        summary = self.getEventSummary()
        if summary is None:
            return 'severity_none'
        colors = 'critical error warning info debug'.split()
        color = 'debug'
        for i in range(5):
            if summary[i][2] > 0:
                color = colors[i]
                break
        return 'severity_%s' % color

    def getEventSummary(self):
        if not self.important:
            return None
        if hasattr(self.node, 'getEventSummary'):
            return self.node.getEventSummary()

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
