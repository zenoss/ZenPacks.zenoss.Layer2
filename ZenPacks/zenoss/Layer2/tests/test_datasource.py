##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import doctest
from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenEvents import ZenEventClasses
from Products.DataCollector.plugins.CollectorPlugin import GetTableMap

from ZenPacks.zenoss.Layer2.dsplugins import Layer2InfoPlugin, PLUGIN_NAME
from ZenPacks.zenoss.Layer2.dsplugins import ForwardingEntryStatus
from ZenPacks.zenoss.Layer2 import dsplugins
from ZenPacks.zenoss.Layer2.utils import asmac


class TestDataSourcePlugin(BaseTestCase):
    def setUp(self):
        config = Mock(datasources=[Mock(getHWManufacturerName='Cisco')])
        self.plugin = Layer2InfoPlugin(config)
        self.plugin.component = sentinel.component
        self.config = Mock(datasources=[Mock(eventClass=sentinel.eventClass)])

    def test_onSuccess(self):
        res = dict(
            values={
                sentinel.component: sentinel.value
            },
            events=[],
        )
        res = self.plugin.onSuccess(res, self.config)

        events = res['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['component'], sentinel.component)
        self.assertEqual(events[0]['severity'], ZenEventClasses.Clear)
        self.assertEqual(events[0]['eventClass'], sentinel.eventClass)

    def test_onError(self):
        res = self.plugin.onError(
            Mock(value=sentinel.error_value),
            self.config
        )
        events = res['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['component'], sentinel.component)
        self.assertEqual(events[0]['summary'], 'sentinel.error_value')
        self.assertEqual(events[0]['severity'], ZenEventClasses.Error)
        self.assertEqual(events[0]['eventClass'], sentinel.eventClass)

    def test_get_vlans(self):
        self.plugin.iftable = {
            'Vlan207': 0,
            'Vlan208': 0,
            'GigabitEthernet2_0_38': 0,
            'StackSub-St1-1': 0,
            'Vlan1': 0,
            'Port-channel8': 0,
        }

        res = list(self.plugin.get_vlans())

        self.assertEqual(res, ['', '207', '208', '1'])

    def test_get_maps(self):
        clientmacs = [sentinel.clientmac1]
        self.plugin.iftable = {
            'if1': {
                'clientmacs': clientmacs,
                'baseport': sentinel.baseport,
            }
        }
        self.plugin.macs_indexed = True

        maps = list(self.plugin.get_maps())

        self.assertEqual(len(maps), 2)
        self.assertEqual(maps[0].set_reindex_maps, set(clientmacs))
        self.assertEqual(maps[1].compname, 'os')
        self.assertEqual(maps[1].relname, 'interfaces')
        self.assertEqual(maps[1].id, 'if1')
        self.assertEqual(maps[1].clientmacs, clientmacs)
        self.assertEqual(maps[1].baseport, sentinel.baseport)

    def test_get_snmp_data(self):
        sc = Mock()
        base_oid = '.1.3.6.1.2.1.17.4.3.1'
        tablemap = GetTableMap(
            sentinel.table_map_name,
            base_oid,
            {
                '.1': sentinel.suboid1,
                '.2': sentinel.suboid2,
            }
        )
        data = {
            base_oid + '.1': {
                base_oid + '.1.1234': sentinel.value1,
            },
            base_oid + '.2': {
                base_oid + '.2.1234': sentinel.value2,
            }
        }
        sc._tabledata = {
            PLUGIN_NAME: {
                tablemap: data,
            }
        }

        data = self.plugin.get_snmp_data(sc)

        self.assertEqual(data, {
            sentinel.table_map_name: {
                '1234': {
                    sentinel.suboid1: sentinel.value1,
                    sentinel.suboid2: sentinel.value2,
                }
            }
        })

    def test_prep_iftable(self):
        res = {
            'dot1dTpFdbTable': sentinel.forwarding_table,
            'dot1dBasePortEntry': {
                'key': {
                    'dot1dBasePortIfIndex': 22,
                    'dot1dBasePort': sentinel.baseport,
                },
            },
        }
        self.plugin.iftable = {
            'if1': {
                'ifindex': '22',
                'clientmacs': [],
            }
        }
        self.plugin._extract_clientmacs = Mock()

        self.plugin._prep_iftable(res)

        ifdata = self.plugin.iftable['if1']
        self.assertEqual(ifdata.get('baseport'), sentinel.baseport)
        self.plugin._extract_clientmacs.assertCalledWith(
            sentinel.forwarding_table,
            ifdata
        )

    def test_extract_clientmacs(self):
        mac = 'asdf'
        table = {'key': {
            'dot1dTpFdbAddress': mac,
            'dot1dTpFdbStatus': ForwardingEntryStatus.learned,
            'dot1dTpFdbPort': sentinel.port,
        }}
        interface = {
            'baseport': sentinel.port,
            'clientmacs': [],
        }

        self.plugin._extract_clientmacs(table, interface)

        self.assertEqual(interface['clientmacs'], [asmac(mac)])


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestDataSourcePlugin))
    suite.addTests(doctest.DocTestSuite(dsplugins))
    return suite
