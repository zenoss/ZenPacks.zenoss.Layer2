##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

''' This module defines interface for connections providers.

Connections providers must define two methods:
    get_status - returns True if adapted device (self.context) is up
    get_connections - should yield Connection instances

Connection (also defined below) instances are created like this:
    Connection(
        entity_id: string,
        connected_to: tuple of strings,
        layers: tuple of strings
    )

Also it contains BaseConnectionsProvider which implements this interface. Your
own connections provider should be inherited from it.

For example see DeviceConnectionsProvider and NetworkConnectionsProvider
also defined in this module.

All connection providers should be registered in configure.zcml.
For more details see README.mediawiki

'''
import logging

from zope.interface import Interface, implements, Attribute, invariant
from zope.component import adapts

from Products.ZenEvents import ZenEventClasses
from Products.Zuul import getFacade
from Products.Zuul.catalog.interfaces import IGloballyIndexed
from Products.Zuul.catalog.interfaces import IIndexableWrapper

from zenoss.protocols.protobufs.zep_pb2 import (
    STATUS_NEW, STATUS_ACKNOWLEDGED, STATUS_SUPPRESSED,
    SEVERITY_CRITICAL,
    )


log = logging.getLogger('zen.Layer2')


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
        macs = getattr(self.interface, 'clientmacs')
        if macs:
            return [x.upper() for x in macs if x]
        else:
            return []

    @property
    def layers(self):
        res = ['layer2']
        res.extend(get_vlans(self.interface))
        return res


def assert_str(obj, msg):
    assert isinstance(obj, basestring), msg


def check_connection(connection):
    assert_str(connection.entity_id, 'entity_id should be string')
    assert connection.entity_id, 'entity_id should be not empty'

    def tuple_of_str(v, name):
        assert isinstance(v, tuple), '%s should be tuple' % name
        assert v, '%s should be not empty' % name
        for e in v:
            assert_str(e, '%s should contain only strings' % name)

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
    if hasattr(obj, 'getPrimaryId'):
        return obj.getPrimaryId()
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

    def getPrimaryId(self):
        return "!" + self.context.getPrimaryId()


class DeviceConnectionsProvider(BaseConnectionsProvider):
    def get_status(self):
        device = self.context
        zep = getFacade('zep', device.getDmd())
        event_filter = zep.createEventFilter(
            tags=[device.getUUID()],
            element_sub_identifier=[""],
            event_class=[ZenEventClasses.Status_Ping],
            severity=[SEVERITY_CRITICAL],
            status=[STATUS_NEW, STATUS_ACKNOWLEDGED, STATUS_SUPPRESSED])

        result = zep.getEventSummaries(0, filter=event_filter, limit=0)
        return int(result['total']) == 0

    def get_connections(self):
        for interface in self.context.os.interfaces():
            ic = InterfaceConnections(interface)
            layers = ic.layers
            mac = ic.macaddress
            if not mac or mac == "00:00:00:00:00:00":
                continue
            yield Connection(self.context, (mac, ), layers)
            yield Connection(mac, (self.context, ), layers)
            yield Connection(MACObject(interface), (mac, ), layers)
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

                # Invalidation saves memory, but undoes uncommitted changes.
                if not ip._p_changed:
                    ip._p_invalidate()

            # Invalidation saves memory, but undoes uncommitted changes.
            if not interface._p_changed:
                interface._p_invalidate()


class NetworkConnectionsProvider(BaseConnectionsProvider):
    def get_connections(self):
        for ip in self.context.ipaddresses():
            dev = ip.device()
            if not dev:
                continue
            net = self.context
            yield Connection(net, (dev, ), ['layer3', ])
            yield Connection(dev, (net, ), ['layer3', ])

            # Invalidation saves memory, but undoes uncommitted changes.
            if not ip._p_changed:
                ip._p_invalidate()


def get_vlans(iface):
    if not hasattr(iface, 'vlans'):
        return []
    if callable(iface.vlans):
        vlans = []
        for vlan in iface.vlans():
            if hasattr(vlan, 'vlan_id'):
                vlan_id = vlan.vlan_id
            elif hasattr(vlan, 'ipVlanId'):
                # NetScaler VLANs have no `vlan_id` attribute.
                vlan_id = vlan.ipVlanId
            else:
                log.warning('VLAN component %s has no Id', vlan)
                continue

            vlans.append('vlan{}'.format(vlan_id))

        return vlans
    else:
        return iface.vlans
