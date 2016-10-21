##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
from Products.DataCollector.SnmpClient import SnmpClient
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.DataCollector.plugins.DataMaps import ObjectMap
from ZenPacks.zenoss.Layer2.modeler.plugins.zenoss.snmp.ClientMACs import \
    (ClientMACsState, ClientMACs)
from ZenPacks.zenoss.Layer2.modeler.plugins.zenoss.snmp.CDPLLDPDiscover import \
    (CDPLLDPDiscover)
from mock import Mock, patch


class TestClientMacsState(BaseTestCase):

    def afterSetUp(self):
        obj = Mock()
        obj.getHWManufacturerName = 'Cisco'
        obj.zSnmpCommunity = 'public@eng'
        iftable = {
            'test': {
                'vlan_id': 2.0, 'ifindex': 3, 'baseport': 0, 'clientmacs': []}}
        self.instance = ClientMACsState(obj, iftable)

    def test_instance_attributes(self):
        self.assertFalse(callable(self.instance.is_cisco))
        self.assertTrue(callable(self.instance.vlans))
        self.assertTrue(callable(self.instance.snmp_communities))
        self.assertTrue(callable(self.instance.snmp_client))

    def test_is_cisco(self):
        self.assertEqual(self.instance.is_cisco, True)

    def test_snmp_communities(self):
        for val in self.instance.snmp_communities():
            self.assertIn(val, ['public', 'public@2'])

    @patch.object(SnmpClient, 'initSnmpProxy', return_value='')
    def test_snmp_client(self, init_snmp_proxy):
        res = self.instance.snmp_client()
        self.assertEqual(init_snmp_proxy.called, True)
        self.assertIsInstance(res, SnmpClient)

    def test_update_iftable(self):
        input_data = {
            'dot1dBasePortEntry': {
                'test': {
                    'dot1dBasePortIfIndex': 3,
                    'dot1dBasePort': 5}},
            'dot1dTpFdbTable': {
                'test': {'dot1dTpFdbStatus': 3,
                         'dot1dTpFdbPort': 5}}}

        self.instance.update_iftable(input_data)
        self.assertEqual(self.instance.iftable['test']['baseport'], 5)


class TestModelerPlugins(TestClientMacsState):

    def afterSetUp(self):
        super(TestModelerPlugins, self).afterSetUp()
        self.device = Mock()
        self.log = Mock()
        self.device.zLocalMacAddresses = ['00:00:00:00:00:00', 'invalid_mac']

    def test_client_macs_imports(self):
        from ZenPacks.zenoss.Layer2.modeler.plugins.\
            zenoss.snmp.ClientMACs import ClientMACs

    def test_cdplldpdiscover_imports(self):
        from ZenPacks.zenoss.Layer2.modeler.plugins.\
            zenoss.snmp.CDPLLDPDiscover import CDPLLDPDiscover

    def test_ClientMACs_process(self):
        result = [self.instance, []]
        res = ClientMACs().process(self.device, result, self.log)
        for objmap in res:
            self.assertIsInstance(objmap, ObjectMap)

    def test_CDPLLDPDiscover_process(self):
        data = {'cdpCacheEntry': {'test': {'cdpCachePlatform': 'TEST',
                                           'cdpCacheAddress': 'TEST'},
                                  'withouttitle': {'cdpCachePlatform': ''}},
                'lldpRemEntry': {'new_test': {'lldpRemSysName': 'NEW TEST'},
                                 'test': {'lldpRemSysName': ''}}}
        input_data = [{}, data]
        res = CDPLLDPDiscover().process(self.device, input_data, self.log)
        maps = res.maps
        for objmap in maps:
            self.assertIsInstance(objmap, ObjectMap)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModelerPlugins))
    suite.addTest(makeSuite(TestClientMacsState))
    return suite
