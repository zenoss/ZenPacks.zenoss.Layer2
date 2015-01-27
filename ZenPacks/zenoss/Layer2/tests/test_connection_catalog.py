##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import MagicMock, sentinel

from Products.Five import zcml
import Products.ZenTestCase
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenEvents import ZenEventClasses

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import Connection,\
    BaseConnectionsProvider

from .create_fake_devices import create_topology, router


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
        self.connection = fake_connection('test_id')

    def test_catalog_is_empty(self):
        self.assertEqual(len(self.cat.search()), 0)

    def test_connection_is_added_to_catalog(self):
        self.cat.add_connection(self.connection)
        brains = self.cat.search()

        self.assertEqual(len(brains), 1)
        self.assertEqual(brains[0].entity_id, 'test_id')
        self.assertEqual(
            brains[0].connected_to, ('connected_to1', 'connected_to2')
        )
        self.assertEqual(brains[0].layers, ('layer1', 'layer2', 'layer1'))

    def test_remove_connection(self):
        self.cat.add_connection(self.connection)
        self.cat.remove_connection(self.connection)
        brains = self.cat.search()

        self.assertEqual(len(brains), 0)

    def test_validate_connection(self):
        self.assertEqual(
            self.cat.validate_connection(self.connection), self.connection
        )

    def test_search(self):
        self.cat.add_connection(self.connection)
        self.assertEqual(len(self.cat.search(entity_id='test_id')), 1)
        self.assertEqual(len(self.cat.search(entity_id='incorrect_id')), 0)

    def test_add_remove_node(self):
        cp = fake_connections_provider(self.dmd)
        self.assertEqual(len(self.cat.search()), 0)
        self.cat.add_node(cp)
        self.assertEqual(len(self.cat.search()), 1)
        self.cat.remove_node(cp)
        self.assertEqual(len(self.cat.search()), 0)

    def test_get_directly_connected(self):
        self.cat.add_node(fake_connections_provider(self.dmd))
        self.assertTrue(
            [x for x in self.cat.get_directly_connected('connection_id')] ==
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


class TestCheckWorkingPath(BaseTestCase):
    def afterSetUp(self):
        super(TestCheckWorkingPath, self).afterSetUp()

        self.dmd.Devices.createOrganizer('/Network/Router/Cisco')
        self.cat = CatalogAPI(self.dmd.zport)

        zcml.load_config('testing.zcml', Products.ZenTestCase)
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)

    def topology(self, topology):
        create_topology(topology, self.dmd)

    def test_check_nearest_down(self):
        self.topology('''
            a b
            b c
        ''')

        self.cat.get_status = lambda x: x != router('b')
        self.assertFalse(
            self.cat.check_working_path(router('a'), router('c'))
        )

    def test_check_next_nearest_down(self):
        self.topology('''
            a b
            b c
            c d
        ''')

        self.cat.get_status = lambda x: x != router('c')
        self.assertFalse(
            self.cat.check_working_path(router('a'), router('d'))
        )


    def test_check_one_way_down(self):
        self.topology('''
            a b
            a c
            b d
            c d
        ''')

        self.cat.get_status = lambda x: x != router('c')
        self.assertTrue(
            self.cat.check_working_path(router('a'), router('d'))
        )

    def test_check_two_ways_down(self):
        self.topology('''
            a b
            a c
            b d
            c d
        ''')

        self.cat.get_status = lambda x: x in (router('a'), router('d'))
        self.assertFalse(
            self.cat.check_working_path(router('a'), router('d'))
        )

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCatalogAPI))
    suite.addTest(makeSuite(TestCheckWorkingPath))
    return suite
