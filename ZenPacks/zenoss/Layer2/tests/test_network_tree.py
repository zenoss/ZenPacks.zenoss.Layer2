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
from mock import Mock, patch

from Products.Five import zcml
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from .create_fake_devices import get_device, add_interface, random_mac

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2.network_tree import\
    (get_connections, serialize, NodeAdapter, get_connections_json)
from ZenPacks.zenoss.Layer2 import connections


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
        connections.clear()

    @patch('ZenPacks.zenoss.Layer2.network_tree.get_connections')
    @patch('ZenPacks.zenoss.Layer2.network_tree.serialize')
    def test_get_connections_json(self, mock_serialize, mock_get_connections):
        self.data_root = Mock()
        self.data_root.Devices.findDevice.return_value = 'TEST'
        self.data_root.dmd.getObjByPath.return_value = None
        get_connections_json(self.data_root, 'TEST')
        self.assertTrue(mock_get_connections.called)
        mock_get_connections.assert_called_with('TEST', 1, None, False, False)
        self.assertTrue(mock_serialize.called)

    def test_get_vlan_connections_with_unaware_node(self):
        a = get_device('a', self.dmd)
        mac_a = random_mac()
        mac_b = random_mac()
        b = get_device('b', self.dmd)

        # make a look like a switch
        add_interface(
            a, macaddress=mac_a, clientmacs=[mac_b],
            vlans=['vlan1']
        )

        # make b look like a server
        add_interface(b, macaddress=mac_b, clientmacs=[], vlans=[])

        connections.add_node(a)
        connections.add_node(b)

        res = get_connections(a, depth=3, layers=['vlan1'])
        links = str(res['links'])
        self.assertIn("{'color': [u'layer2', u'vlan1']", links)


class TestNodeAdapter(BaseTestCase):
    def afterSetUp(self):
        obj = Mock()
        obj.macaddress = 'TE:ST:12:34:56:78'
        obj.getPrimaryUrlPath.return_value = '/zport/dmd/Devices/Test'
        obj.getEventSummary.return_value = [
            ['zenevents_5_noack noack', 0, 1],
            ['zenevents_4_noack noack', 0, 0],
            ['zenevents_3_noack noack', 0, 0],
            ['zenevents_2_noack noack', 0, 0],
            ['zenevents_1_noack noack', 0, 0]]
        self.instance = NodeAdapter(obj, '', {})
        self.properties = dir(self.instance)

    def test_instance_attributes(self):
        self.assertIn('id', self.properties)
        self.assertIn('path', self.properties)
        self.assertIn('name', self.properties)
        self.assertIn('image', self.properties)

    def test_path(self):
        self.assertEqual(self.instance.path, '/zport/dmd/Devices/Test')

    def test_name(self):
        self.assertEqual(self.instance.name, 'TE:ST:12:34:56:78')
        obj = Mock(spec=['getNetworkName'])
        obj.getNetworkName.return_value = 'network'
        self.assertEqual(NodeAdapter(obj, '', {}).name, 'network')

    def test_image(self):
        self.assertEqual(
            self.instance.image,
            '/++resource++ZenPacks_zenoss_Layer2/img/link.png')


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSerialize))
    suite.addTest(makeSuite(TestGetConnections))
    suite.addTest(makeSuite(TestNodeAdapter))
    return suite
