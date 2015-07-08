##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import json
from functools import partial
from itertools import chain

import logging
log = logging.getLogger('zen.Layer2')

from zExceptions import NotFound

from Products.ZenModel.Link import ILink
from Products.ZenModel.IpNetwork import IpNetwork
from Products.ZenModel.Device import Device
from Products.Zuul.catalog.global_catalog import IIndexableWrapper

from .connections_catalog import CatalogAPI
from .edge_contraction import contract_edges


def get_connections_json(data_root, root_id, depth=1, layers=None):
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
    return serialize(
        contract_edges(
            **get_connections(obj, depth, layers)
        )
    )


def serialize(*args, **kwargs):
    '''
        If the only positional argument is Exception - serialize it, else
        serialize dictionary of passed keyword arguments
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
    links = []
    nodenums = {}

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

    def add_link(a, b, color):
        s = nodenums[a.id]
        t = nodenums[b.id]

        key = tuple(sorted([s, t]))
        if key in added_links:
            return
        added_links.add(key)

        links.append(dict(
            source=s,
            target=t,
            color=color,
        ))

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
        related = list(get_related(a))

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

            # need to check for uid in leafs before adding node to graph
            # as next time it will be skipped due to optimization
            for node_b in get_related(b):
                if this_is_link(node_b):
                    b.link = node_b[1:]
                    break

            add_node(b)
            add_link(a, b, 'gray')
            get_connections(node, depth - 1)

    def get_related(node):
        return cat.get_two_way_connected(node.get_path(), layers)

    def this_is_link(node):
        if isinstance(node, str) and node[0] == "!":
            return node[1:]

    add_node(adapt_node(rootnode))
    get_connections(rootnode, depth)

    return dict(
        links=links,
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
        if hasattr(self.node, 'getNetworkName'):
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
            return self.node.getNetworkName()
        elif hasattr(self.node, 'titleOrId'):
            return self.node.titleOrId()
        else:
            title = self.id
            if title.startswith('/zport/dmd/'):
                title = title.split('/')[-1]
            return title

    def getIconPath(self):
        if hasattr(self.node, 'getIconPath'):
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
            hasattr(self.node, 'aq_base')
            and isinstance(self.node.aq_base, IpNetwork)
        ):
            return False
        return True
