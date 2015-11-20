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

from ZenPacks.zenoss.Layer2.patches import get_ifinfo_for_layer2, format_macs


class TestPatches(BaseTestCase):
    def test_get_ifinfo_for_layer2(self):
        device = Mock()
        interface = Mock(
            id=sentinel.ifid,
            ifindex=sentinel.ifindex,
            vlan_id=sentinel.vlan_id
        )
        device.os.interfaces.return_value = [interface]

        res = get_ifinfo_for_layer2(device)

        self.assertEqual(res, {
            sentinel.ifid: {
                'ifindex': sentinel.ifindex,
                'vlan_id': sentinel.vlan_id,
                'clientmacs': [],
                'baseport': 0,
            }
        })

    def test_format_macs(self):
        self.assertEqual(
            format_macs(
                ['aasdf', 'b', 'c'],
                lambda mac: None
            ),
            [{
                'text': 'Other',
                'expanded': False,
                'children': [
                    {'text': 'aasdf', 'leaf': True},
                    {'text': 'b', 'leaf': True},
                    {'text': 'c', 'leaf': True}
                ],
                'cls': 'folder'
            }]
        )


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestPatches))
    return suite
