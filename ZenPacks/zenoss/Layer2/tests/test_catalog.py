##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenEvents import ZenEventClasses
from Products.DataCollector.plugins.CollectorPlugin import GetTableMap

from ZenPacks.zenoss.Layer2.dsplugins import Layer2InfoPlugin, PLUGIN_NAME


class TestDataSourcePlugin(BaseTestCase):
    def setUp(self):
        self.plugin = Layer2InfoPlugin()
        self.plugin.component = sentinel.component

    def test_onSuccess(self):
        res = dict(
            values={
                sentinel.component: sentinel.value
            },
            events=[],
        )
        res = self.plugin.onSuccess(res, sentinel.config)

        events = res['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['component'], sentinel.component)
        self.assertEqual(events[0]['severity'], ZenEventClasses.Clear)

    def test_onError(self):
        res = self.plugin.onError(2, sentinel.config)
        events = res['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['component'], sentinel.component)
        self.assertEqual(events[0]['summary'], '2')
        self.assertEqual(events[0]['severity'], ZenEventClasses.Error)

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

        self.assertEqual(res, ['207', '208', '1'])

    def test_get_maps(self):
        self.plugin.iftable = {
            'if1': {
                'clientmacs': sentinel.clientmacs,
                'baseport': sentinel.baseport,
            }
        }

        maps = list(self.plugin.get_maps())

        self.assertEqual(len(maps), 2)
        self.assertEqual(maps[1].set_reindex_maps, True)
        self.assertEqual(maps[0].compname, 'os/interfaces/if1')
        self.assertEqual(maps[0].clientmacs, sentinel.clientmacs)
        self.assertEqual(maps[0].baseport, sentinel.baseport)

    def test_get_snmp_data(sc):
        sc = Mock()
        tablemap = GetTableMap(
                'dot1dTpFdbTable',
                '.1.3.6.1.2.1.17.4.3.1',
                {'.1': 'dot1dTpFdbAddress'}
        )
        data = {
            '.1.3.6.1.2.1.17.4.3.1.1': '????' # TODO: what here? 
        }
        sc._tabledata = {
            PLUGIN_NAME: {
                tablemap: data,
            }
        }
        data = self.plugin.get_snmp_data(sc)
        # TODO: finish this test


    def test_prep_iftable(self):
        res = {}

        # self.plugin._prep_iftable(res)

        

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestDataSourcePlugin))
    return suite
