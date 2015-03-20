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
from Acquisition import ImplicitAcquisitionWrapper

from Products.ZenModel.ZenModelRM import ZenModelRM
from Products.Zuul.catalog.interfaces import IGloballyIndexed
from Products.Zuul.catalog.interfaces import IIndexableWrapper

from .macs_catalog import InterfaceConnections


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


class DeviceConnectionsProvider(BaseConnectionsProvider):
    def get_status(self):
        return self.context.getStatus() == 0

    def get_connections(self):
        for interface in self.context.os.interfaces():
            ic = InterfaceConnections(interface)
            layers = ic.layers
            mac = ic.macaddress.strip()
            if not mac:
                continue
            yield Connection(self.context, (mac, ), layers)
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
