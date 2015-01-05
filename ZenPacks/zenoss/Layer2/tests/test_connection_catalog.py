##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import MagicMock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI

from ZenPacks.zenoss.Layer2.connections_provider import Connection,\
    BaseConnectionsProvider


def fake_connection(con_id):
    connected_to = ('connected_to1', 'connected_to2')
    layers = ('layer1', 'layer2', 'layer1')
    c = Connection(con_id, connected_to, layers)
    return c


def fake_connections_provider(dmd, id='connection_id'):
    cp = BaseConnectionsProvider(sentinel.context)
    cp.get_status = MagicMock()
    cp.get_connections = MagicMock(return_value=[fake_connection(id)])
    cp.get_layers = MagicMock()
    return cp


class TestCatalogAPI(BaseTestCase):
    def afterSetUp(self):
        super(TestCatalogAPI, self).afterSetUp()
        self.cat = CatalogAPI(self.app.zport)
        self.cat.name = 'test_catalog_name'
        self.connction = fake_connection('test_id')

    def test_catalog_is_empty(self):
        self.assertEqual(len(self.cat.search()), 0)

    def test_connection_is_added_to_catalog(self):
        self.cat.add_connection(self.connction)
        brains = self.cat.search()

        self.assertEqual(len(brains), 1)
        self.assertEqual(brains[0].entity_id, 'test_id')
        self.assertEqual(
            brains[0].connected_to, ('connected_to1', 'connected_to2')
        )
        self.assertEqual(brains[0].layers, ('layer1', 'layer2', 'layer1'))

    def test_remove_connection(self):
        self.cat.add_connection(self.connction)
        self.cat.remove_connection(self.connction)
        brains = self.cat.search()

        self.assertEqual(len(brains), 0)

    def test_validate_connection(self):
        self.assertEqual(
            self.cat.validate_connection(self.connction), self.connction
        )

    def test_serch(self):
        self.cat.add_connection(self.connction)
        self.assertEqual(len(self.cat.search(entity_id='test_id')), 1)
        self.assertEqual(len(self.cat.search(entity_id='incorrect_id')), 0)

    def test_catalog(self):
        self.assertEqual(self.cat.catalog.id, 'test_catalog_name')

    def test_add_remove_node(self):
        cp = fake_connections_provider(self.dmd)
        self.assertEqual(len(self.cat.search()), 0)
        self.cat.add_node(cp)
        self.assertEqual(len(self.cat.search()), 1)
        self.cat.remove_node(cp)
        self.assertEqual(len(self.cat.search()), 0)

    def test_get_connected(self):
        self.cat.add_node(fake_connections_provider(self.dmd))
        self.assertTrue(
            [x for x in self.cat.get_connected('connection_id')] ==
            ['connected_to1', 'connected_to2']
        )

    def test_get_existing_layers(self):
        self.cat.add_node(fake_connections_provider(self.dmd))
        self.assertEqual(len(self.cat.get_existing_layers()), 2)

    def test_clear(self):
        self.cat.add_node(fake_connections_provider(self.dmd, 'con_id1'))
        self.cat.add_node(fake_connections_provider(self.dmd, 'con_id2'))
        self.cat.add_node(fake_connections_provider(self.dmd, 'con_id3'))
        self.cat.add_node(fake_connections_provider(self.dmd, 'con_id4'))
        self.cat.add_node(fake_connections_provider(self.dmd, 'con_id5'))
        self.assertEqual(len(self.cat.search()), 5)
        self.cat.clear()
        self.assertEqual(len(self.cat.search()), 0)
