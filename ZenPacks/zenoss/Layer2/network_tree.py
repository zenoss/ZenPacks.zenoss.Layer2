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

import json
from functools import partial
from itertools import chain
import re

import logging

from zExceptions import NotFound

from Products.ZenModel.Link import ILink
from Products.ZenModel.IpNetwork import IpNetwork
from Products.ZenModel.Device import Device
from Products.Zuul.catalog.global_catalog import IIndexableWrapper

from .connections_catalog import CatalogAPI
from .edge_contraction import contract_edges

log = logging.getLogger('zen.Layer2')


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
    zport = rootnode.zport
    cat = CatalogAPI(zport)

    nodes = []
    links = {}
    colors = {}  # mapping from pair of nodes to their layers
    nodenums = {}

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
        if n.id in nodenums:
            return

        nodenums[n.id] = len(nodes)
        nodes.append(dict(
            name=n.titleOrId(),
            image=n.getIconPath(),
            path=n.get_link(),
            color=n.getColor(),
            highlight=n.id == rootnode.id,
            important=n.important,
        ))

    added_links = set()

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

    def get_connections(rootnode, depth):
        """ Depth-first search of the network tree emanating from rootnode """
        if depth == 0:
            return

        a = adapt_node(rootnode)

        if a.id in visited:
            return
        visited.add(a.id)

        # leafs of current node in graph
        impacted = set(get_impacted(a))
        impactors = set(get_impactors(a))
        related = impacted | impactors

        # some of leaf may contain a component (usualy IpInterface) uid
        # prefixed with asterix (!)
        for node in related:
            if this_is_link(node):
                a.link = node[1:]
                break

        add_node(a)

        for node in related:
            if this_is_link(node):
                continue

            b = adapt_node(node)

            add_node(b)
            if node in impacted:
                add_link(a, b)
            if node in impactors:
                add_link(b, a)
            get_connections(node, depth - 1)

    def get_related(node):
        return cat.get_two_way_connected(node.get_path(), layers)

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

    def get_impacted(node):
        node_id = node.get_path()
        q = dict(entity_id=node_id)
        if layers:
            q['layers'] = layers
        for b in cat.search(**q):
            if connection_not_in_this_vlans(b, layers):
                continue
            for c in b.connected_to:
                colors[(node_id, c)] = b.layers
                yield c

    def get_impactors(node):
        node_id = node.get_path()
        q = dict(connected_to=node_id)
        if layers:
            q['layers'] = layers
        for b in cat.search(**q):
            if connection_not_in_this_vlans(b, layers):
                continue
            colors[(b.entity_id, node_id)] = b.layers
            yield b.entity_id

    def this_is_link(node):
        if isinstance(node, str) and node[0] == "!":
            return node[1:]

    get_connections(rootnode, depth)

    return dict(
        links=links.values(),
        nodes=nodes,
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
