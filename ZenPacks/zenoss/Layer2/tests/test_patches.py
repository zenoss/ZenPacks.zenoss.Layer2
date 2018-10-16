##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import Mock, sentinel

from Products.Five import zcml

from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenHub.services.ModelerService import ModelerService
from Products.ZenTestCase.BaseTestCase import BaseTestCase

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2 import connections
from ZenPacks.zenoss.Layer2.patches import get_ifinfo_for_layer2


class TestPatches(BaseTestCase):
    def afterSetUp(self):
        super(TestPatches, self).afterSetUp()

        # Get our necessary adapters registered.
        zcml.load_config("configure.zcml", ZenPacks.zenoss.Layer2)

        # Clear connections database.
        connections.clear()

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

    def test_remote_applyDataMaps(self):
        service = ModelerService(self.dmd, "localhost")

        device = self.dmd.Devices.createInstance("test-device")
        device.setPerformanceMonitor("localhost")
        device.setManageIp("127.0.0.1")
        device.index_object()

        from zope.event import notify
        from Products.Zuul.catalog.events import IndexingEvent
        notify(IndexingEvent(device))

        eth0_mac = "00:00:00:00:00:01"
        client_mac = "00:00:00:00:00:02"

        # Test that disabling zL2UpdateOnModel works.
        device.setZenProperty("zL2UpdateOnModel", False)
        service.remote_applyDataMaps(
            device.id, [
                RelationshipMap(
                    relname="interfaces",
                    compname="os",
                    modname="Products.ZenModel.IpInterface",
                    objmaps=[{
                        "id": "eth0",
                        "interfaceName": "eth0",
                        "speed": int(1e9),
                        "macaddress": eth0_mac,
                        "clientmacs": [client_mac]}])])

        self.assertEqual(
            connections.get_device_by_mac(self.dmd, eth0_mac),
            None)

        # Test that enabling zL2UpdateOnModel works.
        device.setZenProperty("zL2UpdateOnModel", True)
        service.remote_applyDataMaps(
            device.id, [
                RelationshipMap(
                    relname="interfaces",
                    compname="os",
                    modname="Products.ZenModel.IpInterface",
                    objmaps=[{
                        "id": "eth0",
                        "interfaceName": "eth0",
                        "speed": int(1e10),
                        "macaddress": eth0_mac,
                        "clientmacs": [client_mac]}])])

        self.assertEqual(
            connections.get_device_by_mac(self.dmd, eth0_mac),
            device)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestPatches))
    return suite
