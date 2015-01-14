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

def serialize(*args, **kwargs):
    ''' 
        If the only positional argument is Exception - serialize it, else
        serialize dictionary of passed keyword arguments
    '''
    if args:
        if isinstance(args[0], Exception):
            msg = args[0].message
        else:
            msg = args[0]
        return serialize(error=msg)
    return json.dumps(kwargs, indent=2)


def get_connections_json(rootnode, depth=1, filter='/', layers=None):
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
            color=n.getColor(),
            highlight=n.id == rootnode.id,
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

        add_node(a)

        for node in _get_related(a):
            b = adapt_node(node)
            add_node(b)
            add_link(a, b, 'gray')
            get_connections(node, depth - 1)

    def _get_related(node):
        return cat.get_connected(node.get_path(), layers)
        # TODO: make filter work

    
    try:
        add_node(adapt_node(rootnode))
        get_connections(rootnode, depth)
    except Exception as e:
        log.exception(e)
        return serialize(e)


    return serialize(
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
        if hasattr(self.node, 'id'):
            return self.node.id
        else:
            return self.node

    def get_path(self):
        if hasattr(self.node, 'getPhysicalPath'):
            return '/'.join(self.node.getPhysicalPath())
        else:
            return self.node

    def titleOrId(self):
        if hasattr(self.node, 'titleOrId'):
            return self.node.titleOrId()
        else:
            return self.id

    def getIconPath(self):
        if hasattr(self.node, 'getIconPath'):
            return self.node.getIconPath()
        else:
            return '/++resource++ZenPacks_zenoss_Layer2/img/link.png'

    def getColor(self):
        if isinstance(self.node, IpNetwork):
            return '#ffffff'
        summary = self.getEventSummary()
        colors = '#ff0000 #ff8c00 #ffd700 #00ff00 #00ff00'.split()
        color = '#00af00'
        if summary is None:
            return color
        for i in range(5):
            if summary[i][2] > 0:
                color = colors[i]
                break
        return color

    def getEventSummary(self):
        if hasattr(self.node, 'getEventSummary'):
            return self.node.getEventSummary()
