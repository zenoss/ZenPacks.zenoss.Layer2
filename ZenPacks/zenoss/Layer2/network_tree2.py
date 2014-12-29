##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import json

from functools import partial
from itertools import chain

from Products.ZenModel.Link import ILink
from Products.ZenModel.IpNetwork import IpNetwork
from Products.ZenModel.Device import Device
from Products.Zuul.catalog.global_catalog import IIndexableWrapper

from .connections_catalog import CatalogAPI

COMMON_LINK_COLOR = '#ccc'
L2_LINK_COLOR = '#4682B4'

serialize = partial(json.dumps, indent=2)


def get_json(edges, main_node=None):
    '''
        Return JSON dump of network graph passed as edges.
        edges is iterable of pairs of tuples with node data or exception
        main_node is id of root node to highlight
    '''

    # In case of exception - return json with error message
    if isinstance(edges, Exception):
        return serialize(dict(
            error=edges.message,
        ))

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
            color=getColor(n),
            highlight=n.id == main_node,
        ))

    for a, b, l2 in edges:
        add_node(a)
        add_node(b)
        links.append(dict(
            source=nodenums[a.id],
            target=nodenums[b.id],
            color=L2_LINK_COLOR if l2 else COMMON_LINK_COLOR,
        ))

    return serialize(dict(
        links=links,
        nodes=nodes,
    ))


def get_edges(rootnode, depth=1, filter='/', layers=None):
    for nodea, nodeb in _get_connections(
        rootnode, int(depth), [], filter, layers
    ):
        yield (
            nodea, nodeb,
            False
            # isinstance(nodea, NetworkSegment) or isinstance(
            #     nodeb, NetworkSegment
            # )
        )


def getColor(node):
    if isinstance(node, IpNetwork):
        return '#ffffff'
    summary = node.getEventSummary()
    colors = '#ff0000 #ff8c00 #ffd700 #00ff00 #00ff00'.split()
    color = '#00ff00'
    for i in range(5):
        if summary[i][2] > 0:
            color = colors[i]
            break
    return color


'''
def _fromDeviceToNetworks(dev, filter='/'):
    for iface in dev.os.interfaces():
        for ip in iface.ipaddresses():
            net = ip.network()
            if net is None or net.netmask == 32:
                continue
            else:
                yield net


def _fromDeviceToNetworkSegments(dev, filter, cat, layers=None):
    try:
        interfaces = cat.get_device_interfaces(dev.id, layers)
    except IndexError:
        return

    def segment_connnects_something(seg):
        if len(seg) < 2:
            return False  # only segments with two or more MACs connnect something
        for d in cat.get_if_client_devices(seg.macs):
            if _passes_filter(dev, filter) and dev.id != d.id:
                return True

    segments = set()
    for i in interfaces:
        seg = cat.get_network_segment(i, layers)
        if seg.id not in segments:
            segments.add(seg.id)
            if segment_connnects_something(seg):
                yield seg


def _fromNetworkSegmentToDevices(seg, filter, cat):
    for dev in cat.get_if_client_devices(seg.macs):
        if _passes_filter(dev, filter):
            yield dev


def _passes_filter(dev, filter):
    if dev is None:
        return False
    paths = map('/'.join, IIndexableWrapper(dev).path())
    for path in paths:
        if path.startswith(filter) or path.startswith(
            '/zport/dmd/Devices/Network/Router'
        ):
            return True
    return False


def _fromNetworkToDevices(net, filter):
    for ip in net.ipaddresses():
        dev = ip.device()
        if _passes_filter(dev, filter):
            yield dev
'''


class NodeAdapter(object):
    def __init__(self, node):
        self.node = node

    @property
    def id(self):
        if hasattr(self.node, 'id'):
            return self.node.id
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

    def getEventSummary(self):
        if hasattr(self.node, 'getEventSummary'):
            return self.node.getEventSummary()
        else:
            return [
                ['zenevents_5_noack noack', 0, 0],
                ['zenevents_4_noack noack', 0, 0],
                ['zenevents_3_noack noack', 0, 0],
                ['zenevents_2_noack noack', 0, 0],
                ['zenevents_1_noack noack', 0, 0]
            ]


def _get_related(node, filter, cat, layers=None):
    return map(NodeAdapter, cat.get_connected(node.id, layers))
    # TODO: make filter work

def _get_connections(rootnode, depth=1, pairs=None, filter='/', layers=None, cat=None):
    """ Depth-first search of the network tree emanating from
        rootnode, returning (network, device) edges.
    """
    if depth == 0:
        return
    if not pairs:
        pairs = set()
    if cat is None:
        cat = CatalogAPI(rootnode.zport)
    for node in _get_related(rootnode, filter, cat, layers):
        pair = tuple(sorted(x.id for x in (rootnode, node)))
        if pair not in pairs:
            pairs.add(pair)
            yield (rootnode, node)

            for n in _get_connections(node, depth - 1, pairs, filter, layers, cat):
                yield n
