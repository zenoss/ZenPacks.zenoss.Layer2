##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2007, 2014, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################

import json

from Products.ZenModel.Link import ILink
from Products.ZenModel.IpNetwork import IpNetwork
from Products.ZenModel.Device import Device

from .macs_catalog import CatalogAPI

def get_json(edges):
    nodes = []
    links = []

    nodenums = {}

    def add_node(n):
        n_id, n_img, n_col = n
        if not n_id in nodenums:
            nodenums[n_id] = len(nodes)
            nodes.append(dict(
                name=n_id,
                image=n_img,
                color=n_col
            ))

    for a, b, l2 in edges:
        add_node(a)
        add_node(b)
        links.append(dict(
            source=nodenums[a[0]],
            target=nodenums[b[0]],
            color='steelblue' if l2 else 'gray',
        ))

    return json.dumps(dict(
        links=links,
        nodes=nodes,
    ))

def get_edges(rootnode, depth=1, filter='/'):
    for nodea, nodeb in _get_connections(rootnode, int(depth), [], filter):
        yield (
            (nodea.titleOrId(), nodea.getIconPath(), getColor(nodea)),
            (nodeb.titleOrId(), nodeb.getIconPath(), getColor(nodeb)),
            getattr(nodeb, 'is_l2_connected', False)
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


def _fromDeviceToNetworks(dev):
    for iface in dev.os.interfaces():
        for ip in iface.ipaddresses():
            net = ip.network()
            if net is None or net.netmask == 32:
                continue
            else:
                yield net

    # and for L2 devices:
    cat = CatalogAPI(dev.zport)
    for b in cat.get_client_devices(dev.id):
        d = b.getObject()
        d.is_l2_connected = True
        yield d

def _fromNetworkToDevices(net, organizer):
    from Products.Zuul.catalog.global_catalog import IIndexableWrapper
    for ip in net.ipaddresses():
        dev = ip.device()
        if dev is None:
            continue
        paths = map('/'.join, IIndexableWrapper(dev).path())
        for path in paths:
            if path.startswith(organizer) or path.startswith('/zport/dmd/Devices/Network/Router'):
                yield dev
                break

def _get_related(node, filter='/'):
    if isinstance(node, IpNetwork):
        return _fromNetworkToDevices(node, filter)
    elif isinstance(node, Device):
        return _fromDeviceToNetworks(node)
    else:
        raise NotImplementedError

def _get_connections(rootnode, depth=1, pairs=None, filter='/'):
    """ Depth-first search of the network tree emanating from
        rootnode, returning (network, device) edges.
    """
    if depth == 0: return
    if not pairs: pairs = []
    for node in _get_related(rootnode, filter):
        pair = sorted(x.id for x in (rootnode, node))
        if pair not in pairs:
            pairs.append(pair)
            yield (rootnode, node)

            for n in _get_connections(node, depth-1, pairs, filter):
                yield n
