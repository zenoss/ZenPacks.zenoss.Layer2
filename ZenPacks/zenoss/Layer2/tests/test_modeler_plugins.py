##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import unittest

from Products.DataCollector.SnmpClient import SnmpClient
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.DataCollector.plugins.DataMaps import ObjectMap

from ZenPacks.zenoss.Layer2.modeler.plugins.zenoss.snmp.ClientMACs import (
    ClientMACsState,
    ClientMACs,
    mac_from_snmpindex,
    )

from ZenPacks.zenoss.Layer2.modeler.plugins.zenoss.snmp.CDPLLDPDiscover import (
    CDPLLDPDiscover,
    )

from mock import Mock, patch


class TestFunctions(unittest.TestCase):

    """Tests for functions that don't require ZODB."""

    def test_mac_from_snmpindex(self):
        self.assertRaisesRegexp(
            ValueError,
            r"^no MAC address in '1\.2\.3\.4'$",
            mac_from_snmpindex,
            "1.2.3.4")

        self.assertRaisesRegexp(
            ValueError,
            r"^no MAC address in None$",
            mac_from_snmpindex,
            None)

        self.assertRaisesRegexp(
            ValueError,
            r"^no MAC address in '12345'$",
            mac_from_snmpindex,
            '12345')

        self.assertRaisesRegexp(
            ValueError,
            r"^no MAC address in 'foo'$",
            mac_from_snmpindex,
            'foo')

        self.assertEqual(
            '01:23:45:67:89:AE',
            mac_from_snmpindex('.1.35.69.103.137.174'))

        self.assertEqual(
            '01:23:45:67:89:AF',
            mac_from_snmpindex('.20.1.35.69.103.137.175'))


class TestClientMacsState(BaseTestCase):

    def afterSetUp(self):
        obj = Mock()
        obj.getHWManufacturerName = 'Cisco'
        obj.zSnmpCommunity = 'public'
        iftable = {
            'test1d': {
                'vlan_id': 2.0,
                'ifindex': 3,
                'baseport': 0,
                'clientmacs': [],
                },
            'test1q': {
                'vlan_id': "12",
                'ifindex': "4",
                'baseport': None,
                'clientmacs': [],
                },
            }

        self.instance = ClientMACsState(obj, iftable)

    def test_instance_attributes(self):
        self.assertFalse(callable(self.instance.is_cisco))
        self.assertFalse(callable(self.instance.primary_community))
        self.assertFalse(callable(self.instance.other_communities))
        self.assertFalse(callable(self.instance.all_communities))
        self.assertTrue(callable(self.instance.get_snmp_client))

    def test_is_cisco(self):
        self.assertEqual(self.instance.is_cisco, True)

    def test_snmp_communities(self):
        self.assertEqual(
            set(self.instance.all_communities),
            set(['public', 'public@2', 'public@12']))

    @patch.object(SnmpClient, 'initSnmpProxy', return_value='')
    def test_snmp_client(self, init_snmp_proxy):
        res = self.instance.get_snmp_client('public')
        self.assertEqual(init_snmp_proxy.called, True)
        self.assertIsInstance(res, SnmpClient)

    def test_update_iftable(self):
        input_data = {
            'dot1dBasePortTable': {
                'test1d': {
                    'dot1dBasePortIfIndex': 3,
                    'dot1dBasePort': 5,
                    },
                'test1q': {
                    'dot1dBasePortIfIndex': 4,
                    'dot1dBasePort': 6,
                    },
                },
            'dot1dTpFdbTable': {
                '.20.1.35.69.103.137.171': {
                    'tpFdbStatus': 3,
                    'tpFdbPort': 5,
                    },
                '.1.35.69.103.137.174': {
                    'tpFdbStatus': 3,
                    'tpFdbPort': 5,
                    },
                },
            'dot1qTpFdbTable': {
                '.20.1.35.69.103.137.172': {
                    'tpFdbStatus': 3,
                    'tpFdbPort': 5,
                    },
                '.20.1.35.69.103.137.173': {
                    'tpFdbStatus': 3,
                    'tpFdbPort': 6,
                    },
                '.20.1.35.69.103.137.175': {
                    'tpFdbStatus': 3,
                    'tpFdbPort': 6,
                    }
                },
            }

        self.instance.update_iftable(input_data)

        self.assertEqual(self.instance.iftable['test1d']['baseport'], 5)
        self.assertEqual(
            set(self.instance.iftable['test1d']['clientmacs']),
            set([
                '01:23:45:67:89:AB',
                '01:23:45:67:89:AC',
                '01:23:45:67:89:AE',
                ]))

        self.assertEqual(self.instance.iftable['test1q']['baseport'], 6)
        self.assertEqual(
            set(self.instance.iftable['test1q']['clientmacs']),
            set([
                '01:23:45:67:89:AD',
                '01:23:45:67:89:AF',
                ]))


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
    suite.addTest(makeSuite(TestFunctions))
    suite.addTest(makeSuite(TestModelerPlugins))
    suite.addTest(makeSuite(TestClientMacsState))
    return suite
