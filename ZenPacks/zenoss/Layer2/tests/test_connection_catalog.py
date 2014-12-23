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

from ZenPacks.zenoss.Layer2.connections_provider import Connection


def fake_connection():
    con_id = 'connection_id'
    connected_to = ('connected_to1', 'connected_to2')
    layers = ('layer1', 'layer2')
    c = Connection(con_id, connected_to, layers)
    return c


class TestCatalogAPI(BaseTestCase):
    def afterSetUp(self):
        super(TestCatalogAPI, self).afterSetUp()
        self.cat = CatalogAPI(self.app.zport)
        self.cat.name = 'test_catalog_name'
        self.connction = fake_connection()

    def test_catalog_is_empty(self):
        self.assertEqual(len(self.cat.search()), 0)

    def test_connection_is_added_to_catalog(self):
        self.cat.add_connection(self.connction)
        brains = self.cat.search()

        self.assertEqual(len(brains), 1)
        self.assertEqual(brains[0].entity_id, 'connection_id')
        self.assertEqual(
            brains[0].connected_to, ('connected_to1', 'connected_to2')
        )
        self.assertEqual(brains[0].layers, ('layer1', 'layer2'))

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
        self.assertEqual(len(self.cat.search(entity_id='connection_id')), 1)
        self.assertEqual(len(self.cat.search(entity_id='incorrect_id')), 0)

    def test_catalog(self):
        self.assertEqual(self.cat.catalog.id, 'test_catalog_name')
