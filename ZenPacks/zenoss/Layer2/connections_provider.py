from zope.interface import Interface, implements, Attribute, invariant
from zope.component import adapts
from Acquisition import ImplicitAcquisitionWrapper

from Products.ZenModel.ZenModelRM import ZenModelRM
from Products.Zuul.catalog.interfaces import IGloballyIndexed, IIndexableWrapper

from .macs_catalog import CatalogAPI, get_vlans

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
    entity_id = Attribute('Unique Id of entity for which connections are described')
    connected_to = Attribute('Ids of entities to which this entity is connected')
    layers = Attribute('Names of layers for which this connections exists')

    invariant(check_connection)


class Connection(object):
    ''' See IConnection for detailed documentation '''
    implements(IConnection)
    adapts(IGloballyIndexed)

    def __init__(self, entity_id, connected_to, layers):
        self.entity_id = entity_id
        self.connected_to = tuple(connected_to)
        self.layers = tuple(layers)

    @property
    def hash(self):
        return str(hash(self.layers + (self.entity_id, )))

    def __str__(self):
        return '<Connection for: %s>' % self.entity_id

    def tsv(self):
        return '%s\t%s\t%s' % (self.entity_id, self.connected_to, self.layers)


class IConnectionsProvider(Interface):

    def __init__(context):
        ''' Wraps a device or component and provides API to retrieve its connections '''

    def get_status():
        ''' Returns true if device is up. '''

    def get_connections():
        ''' Yields connection objects '''

    def get_layers():
        ''' Return layers of device '''


class BaseConnectionsProvider(object):
    implements(IConnectionsProvider)

    def __init__(self, context):
        self.context = context
        self.setup()

    def setup(self):
        ''' Allow to set some shortcuts on class '''

    def get_status(self):
        ''' Let all the nodes be up by default '''
        return True

    def __str__(self):
        return '<ConnectionsProvider for: %s>' % self.context

from macs_catalog import InterfaceConnections

class Layer2ConnectionsProvider(BaseConnectionsProvider):
    def setup(self):
        self.cat = CatalogAPI(self.context.dmd.zport)

    def get_status(self):
        return self.context.getStatus()

    def get_connections(self):
        for interface in self.context.os.interfaces():
            ic = InterfaceConnections(interface)
            id = self.context.id
            layers = ic.layers
            mac = ic.macaddress.strip()
            if not mac:
                continue
            yield Connection(id, (mac, ), layers)
            yield Connection(mac, (id, ), layers)
            for cl in ic.clientmacs:
                if cl.strip():
                    yield Connection(mac, (cl, ), layers)
