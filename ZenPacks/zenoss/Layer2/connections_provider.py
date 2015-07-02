##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.interface import Interface, implements, Attribute, invariant
from zope.component import adapts

from Products.Zuul.catalog.interfaces import IGloballyIndexed
from Products.Zuul.catalog.interfaces import IIndexableWrapper


class InterfaceConnections(object):
    implements(IIndexableWrapper)
    adapts(IGloballyIndexed)

    def __init__(self, interface):
        self.interface = interface

    def getPhysicalPath(self):
        return self.interface.getPhysicalPath()

    @property
    def id(self):
        return self.interface.id

    @property
    def device(self):
        return self.interface.device().id

    @property
    def macaddress(self):
        return (
            getattr(self.interface, 'macaddress', '') or ''
        ).upper().strip()

    @property
    def clientmacs(self):
        return [
            x.upper()
            for x in getattr(self.interface, 'clientmacs', [])
            if x
        ]

    @property
    def layers(self):
        res = ['layer2']
        res.extend(get_vlans(self.interface))
        return res


def check_connection(connection):
    assert isinstance(connection.entity_id, str), 'entity_id should be string'
    assert connection.entity_id, 'entity_id should be not empty'

    def tuple_of_str(v, name):
        assert isinstance(v, tuple), '%s should be tuple' % name
        assert v, '%s should be not empty' % name
        for e in v:
            assert isinstance(e, str), '%s should contain only strings' % name

    tuple_of_str(connection.connected_to, 'connected_to')
    tuple_of_str(connection.layers, 'layers')


class IConnection(IIndexableWrapper):
    entity_id = Attribute(
        'Unique Id of entity for which connections are described'
    )
    connected_to = Attribute(
        'Ids of entities to which this entity is connected'
    )
    layers = Attribute('Names of layers for which this connections exists')

    invariant(check_connection)


def connection_hash(c):
    return str(hash(c.layers + c.connected_to + (c.entity_id, )))


def to_path(obj):
    ''' If object has path, replace it by that path, else do nothing '''
    if hasattr(obj, 'getPrimaryUrlPath'):
        return obj.getPrimaryUrlPath()
    else:
        return obj


class Connection(object):
    ''' See IConnection for detailed documentation '''
    implements(IConnection)
    adapts(IGloballyIndexed)

    def __init__(self, entity_id, connected_to, layers):
        self.entity_id = to_path(entity_id)
        self.connected_to = tuple(to_path(x) for x in connected_to)
        if isinstance(layers, str):
            self.layers = (layers, )  # put string into one-element tuple
        else:
            self.layers = tuple(layers)

    @property
    def hash(self):
        return connection_hash(self)

    def __str__(self):
        return '<Connection for: %s>' % self.entity_id

    def tsv(self):
        return '%s\t%s\t%s' % (self.entity_id, self.connected_to, self.layers)


class IConnectionsProvider(Interface):

    def __init__(context):
        '''
            Wraps a device or component and
            provides API to retrieve its connections
        '''

    def get_status():
        ''' Returns True if device is up. '''

    def get_connections():
        ''' Yields connection objects '''

    def get_layers():
        ''' Return layers of device '''


class BaseConnectionsProvider(object):
    implements(IConnectionsProvider)

    def __init__(self, context):
        self.context = context

    def get_status(self):
        ''' Let all the nodes be up by default '''
        return True

    def __str__(self):
        return '<ConnectionsProvider for: %s>' % self.context


class MACObject(object):
    def __init__(self, context):
        self.context = context

    def getPrimaryUrlPath(self):
        return "!" + self.context.getPrimaryUrlPath()


class DeviceConnectionsProvider(BaseConnectionsProvider):
    def get_status(self):
        return self.context.getStatus() == 0

    def get_connections(self):
        for interface in self.context.os.interfaces():
            ic = InterfaceConnections(interface)
            layers = ic.layers
            mac = ic.macaddress
            if not mac or mac == "00:00:00:00:00:00":
                continue
            yield Connection(self.context, (mac, ), layers)
            yield Connection(MACObject(interface), (mac, ), layers)
            yield Connection(mac, (self.context, ), layers)
            for cl in ic.clientmacs:
                if cl.strip():
                    yield Connection(mac, (cl, ), layers)

            # Layer 3 connections
            for ip in interface.ipaddresses():
                net = ip.network()
                if net is None or net.netmask == 32:
                    continue
                yield Connection(self.context, (net, ), ['layer3', ])
                yield Connection(net, (self.context, ), ['layer3', ])


class NetworkConnectionsProvider(BaseConnectionsProvider):
    def get_connections(self):
        for ip in self.context.ipaddresses():
            dev = ip.device()
            if not dev:
                continue
            yield Connection(self.context, (dev, ), ['layer3', ])
            yield Connection(dev, (self.context, ), ['layer3', ])


def get_vlans(iface):
    if not hasattr(iface, 'vlans'):
        return []
    if callable(iface.vlans):
        return ['vlan{}'.format(vlan.vlan_id) for vlan in iface.vlans()]
    else:
        return iface.vlans
