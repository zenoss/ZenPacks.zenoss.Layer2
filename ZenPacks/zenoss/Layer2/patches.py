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
    Returns list with subset of IpInterface properties
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
    Renders data to use in UI panel
    """
    if not macs:
        return ""

    links = defaultdict(lambda: defaultdict(list))

    for mac in macs:
        device = get_device_by_mac(mac)
        if device:
            link = '<a href="{}">{}</a>'.format(
                device.getPrimaryUrlPath(), device.titleOrId())
            links[link][mac[:8]].append(mac)
        else:
            links["Other"][mac[:8]].append(mac)

    # Formats result to use in ExtJS tree view
    result = []
    for group, columns in links.iteritems():
        children = (
            {'text': i, 'leaf': True}
            for k in columns.values() for i in k
        )
        result.append({"text": group,
                       "cls": "folder",
                       "expanded": False,
                       "children": sorted(children)})
    return result


def get_clients_links(self):
    ''' Returns page of links to client devices '''
    return format_macs(
        self._object.clientmacs,
        CatalogAPI(self._object.zport).get_device_by_mac
    )


@monkeypatch('Products.ZenModel.Device.Device')
def index_object(self, idxs=None, noips=False):
    original(self, idxs, noips)

    cat = CatalogAPI(self.zport)
    cat.add_node(self, reindex=True)


@monkeypatch('Products.ZenModel.Device.Device')
def unindex_object(self):
    original(self)

    cat = CatalogAPI(self.zport)
    cat.remove_node(self)


@monkeypatch('Products.ZenModel.Device.Device')
def set_reindex_maps(self, value):
    self.index_object()
    if value == 'reindex please':
        self.macs_indexed = True


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

Device._relations += (
    ('neighbor_switches', ToManyCont(
        ToOne,
        'ZenPacks.zenoss.Layer2.NeighborSwitch.NeighborSwitch',
        'switch'
    )),
)


@monkeypatch('Products.ZenModel.DataRoot.DataRoot')
def getJSONEdges(self, root_id='', depth='2', layers=None):
    ''' Get JSON representation of network nodes '''
    if not root_id:
        return serialize("You should set a device or component name")
    root_id = urllib.unquote(root_id)
    try:
        if layers:
            layers = [l_name[len('layer_'):] for l_name in layers.split(',')]

        return get_connections_json(self, root_id, int(depth), layers=layers)
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


class NetworkMapHelp(PageLevelHelp):
    def __init__(self, context, request):
        # we completely overriding this metod, so calling super
        # not for this class but for it's parent
        super(PageLevelHelp, self).__init__(context, request)
        primary, secondary = getSelectedNames(self)
        if (primary, secondary) == ('Infrastructure', 'Network Map'):
            self.tip = dict(
                title='Network Map',
                tip=NETWORK_MAP_HELP
            )
        else:
            lang = negotiator.getLanguage(TooltipCatalog.langs('nav-help'),
                                          self.request)
            self.tip = TooltipCatalog.pagehelp(primary, lang)
