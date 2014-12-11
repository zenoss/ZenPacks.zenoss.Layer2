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

from .macs_catalog import CatalogAPI, NetworkSegment

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
        n_id = n.titleOrId()
        if not n_id in nodenums:
            nodenums[n_id] = len(nodes)
            nodes.append(dict(
                name=n_id,
                image=n.getIconPath(),
                color=getColor(n),
                highlight=n_id == main_node,
            ))

    for a, b, l2 in edges:
        add_node(a)
        add_node(b)
        links.append(dict(
            source=nodenums[a.titleOrId()],
            target=nodenums[b.titleOrId()],
            color=L2_LINK_COLOR if l2 else COMMON_LINK_COLOR,
        ))

    return serialize(dict(
        links=links,
        nodes=nodes,
    ))

def get_edges(rootnode, depth=1, filter='/'):
    for nodea, nodeb in _get_connections(rootnode, int(depth), [], filter):
        yield (
            nodea, nodeb,
            isinstance(nodea, NetworkSegment) or isinstance(nodeb, NetworkSegment)
        )

def getColor(node):
    if isinstance(node, IpNetwork):
        return '0xffffff'

    summary = node.getEventSummary()
    colors = '0xff0000 0xff8c00 0xffd700 0x00ff00 0x00ff00'.split()
    color = '0x00ff00'
    for i in range(5):
        if summary[i][2]>0:
            color = colors[i]
            break
    return color

def _fromDeviceToNetworks(dev, filter='/'):
    for iface in dev.os.interfaces():
        for ip in iface.ipaddresses():
            net = ip.network()
            if net is None or net.netmask == 32:
                continue
            else:
                yield net

def _fromDeviceToNetworkSegments(dev, filter, cat):
    def segment_connnects_something(seg):
        if len(seg) < 2:
            return False  # only segments with two or more MACs connnect something
        for d in cat.get_if_client_devices(seg.macs):
            if _passes_filter(dev, filter) and dev.id != d.id:
                return True

    segments = set()
    for i in cat.get_device_interfaces(dev.id):
        seg = cat.get_network_segment(i)
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
        if path.startswith(filter) or path.startswith('/zport/dmd/Devices/Network/Router'):
            return True
    return False

def _fromNetworkToDevices(net, filter):
    for ip in net.ipaddresses():
        dev = ip.device()
        if _passes_filter(dev, filter):
            yield dev

def _get_related(node, filter, cat):
    if isinstance(node, IpNetwork):
        return _fromNetworkToDevices(node, filter)
    elif isinstance(node, Device):
        return chain(
            _fromDeviceToNetworks(node, filter),
            _fromDeviceToNetworkSegments(node, filter, cat)
        )
    elif isinstance(node, NetworkSegment):
        return _fromNetworkSegmentToDevices(node, filter, cat)
    else:
        raise NotImplementedError

def _get_connections(rootnode, depth=1, pairs=None, filter='/'):
    """ Depth-first search of the network tree emanating from
        rootnode, returning (network, device) edges.
    """
    if depth == 0: return
    if not pairs: pairs = set()
    cat = CatalogAPI(rootnode.zport)
    for node in _get_related(rootnode, filter, cat):
        pair = tuple(sorted(x.id for x in (rootnode, node)))
        if pair not in pairs:
            pairs.add(pair)
            yield (rootnode, node)

            for n in _get_connections(node, depth-1, pairs, filter):
                yield n
