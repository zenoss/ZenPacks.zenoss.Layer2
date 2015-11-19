##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from __future__ import unicode_literals

import json
from mock import Mock, sentinel, MagicMock

from Products.Five import zcml
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from .create_fake_devices import get_device, add_interface, random_mac

import ZenPacks.zenoss.Layer2 
from ZenPacks.zenoss.Layer2.network_tree import get_connections, serialize
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI

class TestSerialize(BaseTestCase):

    def test_exception(self):
        self.assertEqual(json.loads(serialize(Exception('test'))), dict(
            error='test'
        ))

    def test_text(self):
        self.assertEqual(json.loads(serialize('test')), dict(
            error='test'
        ))

class TestGetConnections(BaseTestCase):
    def afterSetUp(self):
        super(TestGetConnections, self).afterSetUp()
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)

    def test_get_vlan_connections_with_unaware_node(self):
        a = get_device('a', self.dmd)
        mac_a = random_mac()
        mac_b = random_mac()
        b = get_device('b', self.dmd)

        # make a look like a switch
        add_interface(a, macaddress=mac_a, clientmacs=[mac_b], layers=['layer2', 'vlan1'])

        # make b look like a server
        add_interface(b, macaddress=mac_b, clientmacs=[], layers=['layer2'])

        catapi = CatalogAPI(self.dmd.zport)
        catapi.add_node(a)
        catapi.add_node(b)

        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)

        # import pudb; pudb.set_trace()
        res = get_connections(a, depth=3, layers=['vlan1'])
        print res



def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSerialize))
    suite.addTest(makeSuite(TestGetConnections))
    return suite
