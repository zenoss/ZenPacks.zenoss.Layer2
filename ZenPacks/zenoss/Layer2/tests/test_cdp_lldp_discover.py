##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.Layer2.modeler.plugins\
    .zenoss.snmp.CDPLLDPDiscover import _extract_cdp_lldp_maps

cdpCacheEntry = {
    '10648.28': {
        'cdpCacheAddress': '\nW\xfe\x07',
        'cdpCacheAddressType': 1,
        'cdpCacheDeviceId': '08cc6843e573',
        'cdpCacheDevicePort': 'gi52',
        'cdpCacheNativeVLAN': 1,
        'cdpCachePlatform': 'asdf'
    }
}
lldpRemEntry = {
    '0.100.22': {
        'lldpRemPortDesc': '',
        'lldpRemPortId': 'gi52',
        'lldpRemSysDesc': '',
        'lldpRemSysName': 'asdf'
    }
}


class TestCDPLLDPDiscover(BaseTestCase):
    def test_extraction_of_both(self):
        res = _extract_cdp_lldp_maps({
            'cdpCacheEntry': cdpCacheEntry,
            'lldpRemEntry': lldpRemEntry
        })
        self.assertEqual(sorted(res), [{
            'description': '',
            'device_port': 'gi52',
            'id': 'lldp_0.100.22',
            'title': 'asdf'
        }, {
            'description': '',
            'device_port': 'gi52',
            'id': 'cdp_10648.28',
            'ip_address': '10.87.254.7',
            'location': '',
            'native_vlan': 1,
            'title': 'asdf'
        }])

    def test_cdp(self):
        res = _extract_cdp_lldp_maps({
            'cdpCacheEntry': cdpCacheEntry,
        })
        self.assertEqual(res, [{
            'description': '',
            'device_port': 'gi52',
            'id': 'cdp_10648.28',
            'ip_address': '10.87.254.7',
            'location': '',
            'native_vlan': 1,
            'title': 'asdf'
        }])

    def test_lldp(self):
        res = _extract_cdp_lldp_maps({
            'lldpRemEntry': lldpRemEntry
        })
        self.assertEqual(res, [{
            'description': '',
            'device_port': 'gi52',
            'id': 'lldp_0.100.22',
            'title': 'asdf'
        }])


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCDPLLDPDiscover))
    return suite
