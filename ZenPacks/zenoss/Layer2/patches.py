##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import urllib
import logging
import types
from collections import defaultdict

import Globals

from Products.ZenModel.IpInterface import IpInterface
from Products.ZenModel.PerformanceConf import PerformanceConf
from Products.ZenUtils.Utils import monkeypatch
from Products.ZenUtils.Utils import unused
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.Zuul.interfaces.component import IIpInterfaceInfo

try:
    from ZenPacks.zenoss.vSphere.Endpoint import Endpoint as vSphereEndpoint
except ImportError:
    vSphereEndpoint = types.NoneType

from . import connections
from . import network_tree
from .utils import get_cz_url_path

unused(Globals)

log = logging.getLogger('zen.Layer2')


@monkeypatch('Products.ZenModel.Device.Device')
def get_ifinfo_for_layer2(self):
    '''
        Returns list with subset of IpInterface properties.
        This property of device is then used in modeler.
    '''
    res = {}
    if self.os:
        for interface in self.os.interfaces():
            res[interface.id] = {
                "ifindex": interface.ifindex,
                "clientmacs": [],
                "baseport": 0,
                "vlan_id": getattr(interface, 'vlan_id', None),
            }
    return res


def get_clients_links(self):
    ''' Returns page of links to client devices '''
    if not self._object.clientmacs:
        return ""

    dmd = self._object.dmd
    links = defaultdict(lambda: defaultdict(dict))

    for mac in self._object.clientmacs:
        device = connections.get_device_by_mac(dmd, mac)

        if device:
            template = '<a href="{}">{}</a>'
            link = template.format(get_cz_url_path(device), device.titleOrId())
            links[link]['macs'].setdefault(mac[:8], []).append(mac)
            vs_instance = device.device()
            if vs_instance.meta_type == 'vSphereEndpoint':
                links[link]['vsphere'] = template.format(
                    get_cz_url_path(vs_instance),
                    vs_instance.titleOrId())
        else:
            links["Other"]['macs'].setdefault(mac[:8], []).append(mac)
    # Formats result to use in ExtJS tree view
    result = []
    for group, columns in links.iteritems():
        children = (
            {'text': i, 'leaf': True}
            for k in columns['macs'].values() for i in k
        )
        res = {"text": group,
               "cls": "folder",
               "expanded": False,
               "children": sorted(children)}
        vsphere = columns.get('vsphere')
        if vsphere:
            vspheres = [i['text'] for i in result]
            if vsphere in vspheres:
                index = vspheres.index(vsphere)
                result[index]["children"].append(res)
            else:
                result.append({"text": vsphere,
                               "cls": "folder",
                               "expanded": True,
                               "children": [res]})
        else:
            result.append(res)
    return result


@monkeypatch('Products.ZenHub.services.ModelerService.ModelerService')
def remote_applyDataMaps(self, device, maps, *args, **kwargs):
    # NoQA: "original" injected by monkeypatch.
    changed = original(self, device, maps, *args, **kwargs)

    if changed:
        try:
            # If this impacts modeling performance too much we could remove
            # it, and let zenmapper handle it on its next cycle. All this
            # buys us is more immediate updating of Layer2 data after
            # devices are remodeled.
            device = self.getPerformanceMonitor().findDeviceByIdExact(device)
            if not device:
                return changed

            if isinstance(device, vSphereEndpoint):
                return changed

            if device.getZ("zL2UpdateOnModel", True):
                connections.update_node(device)

        except Exception:
            # MySQL might not be available. We'll just let zenmapper add
            # this node on its next cycle.
            pass

    return changed


@monkeypatch('Products.ZenModel.Device.Device')
def get_l2_gateways(self):
    """Return list of devices on the path to the device."""
    gateway_device_ids = set()

    try:
        gateway_device_ids.add(self.zZenossGateway)
    except Exception:
        pass

    try:
        gateway_device_ids.update(self.zL2Gateways)
    except Exception:
        pass

    # Only use collector gateways if device gateways aren't set.
    if not filter(None, gateway_device_ids):
        try:
            collector = self.getPerformanceServer()
            gateway_device_ids.update(collector.l2_gateways)
        except Exception:
            pass

    gateway_device_ids = filter(None, gateway_device_ids)
    if gateway_device_ids:
        devices = self.getDmdRoot("Devices")
        return filter(
            None,
            [devices.findDeviceByIdExact(x) for x in gateway_device_ids])

    return []


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getJSONEdges(self, root_id='', depth='3', layers=None, macs='', dangling=''):
    ''' Get JSON representation of network nodes '''

    if not root_id:
        return network_tree.serialize("Set the root device or component.")
    root_id = urllib.unquote(root_id)

    # Make these boolean.
    macs = (macs == 'true')
    dangling = (dangling == 'true')

    try:
        if layers:
            layers = [l_name[len('layer_'):] for l_name in layers.split(',')]

        return network_tree.get_connections_json(
            self, root_id, int(depth),
            layers=layers,
            macs=macs,
            dangling=dangling)
    except Exception as e:
        log.exception(e)
        return network_tree.serialize(e)


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getNetworkLayersList(self):
    ''' Return existing network layers list for checkboxes options '''
    return network_tree.serialize([
        dict(boxLabel=x, inputValue='layer_' + x, id='layer_' + x)
        for x in connections.get_layers()
    ])


# -- IP Interfaces overrides --------------------------------------------------

# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmacs = []
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id': 'clientmacs', 'type': 'lines', 'mode': 'w'},
    {'id': 'baseport', 'type': 'int', 'mode': 'w'},
)

IIpInterfaceInfo.clientmacs = schema.TextLine(
    title=u"Clients MAC Addresses", group="Details", order=13)
IIpInterfaceInfo.baseport = schema.TextLine(
    title=u"Physical Port", group="Details", order=14)

# -- UI overrides goes here --------------------------------------------------

IpInterfaceInfo.clientmacs = ProxyProperty('clientmacs')
IpInterfaceInfo.baseport = ProxyProperty('baseport')
IpInterfaceInfo.get_clients_links = property(get_clients_links)


# -- PerformanceConf Patches -------------------------------------------------

PerformanceConf.l2_gateways = None
PerformanceConf._properties = PerformanceConf._properties + (
    {'id': 'l2_gateways', 'type': 'lines', 'mode': 'w'},
    )


# ----------------------------------------------------------------------------

# Help popup similar to defined in
# Products/ZenUI3/tooltips/data/en/nav-help.xml
NETWORK_MAP_HELP = '''
<p>Network map drawing starts from root, id of which you should put into
Device ID field of form at the left sidebar. Depth defines size of the map
(maximal number of connections beetween each node on map and root).
</p>
<p>
You could also use Layers checkboxes to display only connections
which belong to some layer.
</p>

<p>When you click on some node you will navigate to the page
of the device that node represents.</p>

<p>Right click on node shows a context menu, from which you could
pin and unpin node, make the node a new root of map,
and show device info for the node.</p>

<p>You could zoom map using mouse wheel, pan it using mouse,
and also move nodes using mouse drag. Nodes that are moved become fixed.</p>

<p>
<a href="https://github.com/zenoss/ZenPacks.zenoss.Layer2#Network_map">
Also,see documentation.</a></p>
'''


@monkeypatch('Products.ZenUI3.tooltips.tooltips._TooltipCatalog')
def pagehelp(self, navitem, lang="en"):
    if navitem == 'Infrastructure-Network Map':
            return dict(
                title='Network Map',
                tip=NETWORK_MAP_HELP
            )
    else:
        return original(self, navitem, lang)
