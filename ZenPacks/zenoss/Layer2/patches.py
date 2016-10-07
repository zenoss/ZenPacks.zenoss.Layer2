##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import urllib
import logging
from collections import defaultdict

import Globals

from zope.i18n.negotiator import negotiator

from Products.ZenModel.Device import Device
from Products.ZenModel.IpInterface import IpInterface
from Products.ZenRelations.RelSchema import ToOne, ToManyCont
from Products.ZenUI3.navigation import getSelectedNames
from Products.ZenUI3.tooltips.tooltips import PageLevelHelp, TooltipCatalog
from Products.ZenUtils.Utils import edgesToXML
from Products.ZenUtils.Utils import monkeypatch
from Products.ZenUtils.Utils import unused
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.Zuul.interfaces.component import IIpInterfaceInfo


from .connections_catalog import CatalogAPI
from .network_tree import get_connections_json, serialize

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


def format_macs(macs, get_device_by_mac):
    """
    Gets list of macs in macs argument, and mapping from mac
    to containing device in function get_device_by_mac.

    Renders data to use in UI panel
    """
    if not macs:
        return ""

    links = defaultdict(lambda: defaultdict(dict))

    for mac in macs:
        device = get_device_by_mac(mac)

        if device:
            template = '<a href="{}">{}</a>'
            link = template.format(device.getPrimaryUrlPath(),
                                   device.titleOrId())
            links[link]['macs'].setdefault(mac[:8], []).append(mac)
            vs_instance = device.device()
            if vs_instance.meta_type == 'vSphereEndpoint':
                links[link]['vsphere'] =\
                    template.format(vs_instance.getPrimaryUrlPath(),
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


def get_clients_links(self):
    ''' Returns page of links to client devices '''
    return format_macs(
        self._object.clientmacs,
        CatalogAPI(self._object.zport).get_device_by_mac
    )


@monkeypatch('Products.ZenModel.Device.Device')
def setLastChange(self, value=None):
    original(self, value)

    try:
        cat = CatalogAPI(self.zport)
    except Exception as e:
        # On remote hub redis is not avaialable.
        # Do nothing and let zenmapper index this device.
        return

    try:
        if cat.is_changed(self):
            cat.add_node(self)
    except TypeError as e:
        log.error(e)


@monkeypatch('Products.ZenModel.Device.Device')
def get_reindex_maps(self):
    ''' Should return something distinct from value passed to
        set_reindex_maps for set_reindex_maps to run
    '''
    return set(
        x.upper()
        for i in self.os.interfaces()
        if getattr(i, 'clientmacs')
        for x in i.clientmacs
        if x
    )


@monkeypatch('Products.ZenModel.Device.Device')
def set_reindex_maps(self, value):
    self.index_object()
    if value == 'reindex please':
        self.macs_indexed = True


Device._relations += (
    ('neighbor_switches', ToManyCont(
        ToOne,
        'ZenPacks.zenoss.Layer2.NeighborSwitch.NeighborSwitch',
        'switch'
    )),
)


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getJSONEdges(self, root_id='', depth='2', layers=None, full_map='false'):
    ''' Get JSON representation of network nodes '''

    if not root_id:
        return serialize("Set the UID of device or component")
    root_id = urllib.unquote(root_id)

    full_map = (full_map == 'true')  # make it boolean
    try:
        if layers:
            layers = [l_name[len('layer_'):] for l_name in layers.split(',')]

        return get_connections_json(
            self, root_id, int(depth),
            layers=layers, full_map=full_map
        )
    except Exception as e:
        log.exception(e)
        return serialize(e)


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getNetworkLayers(self):
    ''' Return existing network layers on network map '''
    cat = CatalogAPI(self.zport)
    return cat.get_existing_layers()


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getNetworkLayersList(self):
    ''' Return existing network layers list for checkboxes options '''
    return serialize([
        dict(boxLabel=x, inputValue='layer_' + x, id='layer_' + x)
        for x in self.getNetworkLayers()
    ])

# -- IP Interfaces overrides --------------------------------------------------

# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmacs = []
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id': 'clientmacs', 'type': 'string', 'mode': 'w'},
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
