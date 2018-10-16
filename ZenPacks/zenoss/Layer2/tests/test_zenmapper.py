######################################################################
#
# Copyright (C) Zenoss, Inc. 2015-2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################

from Products.Five import zcml

import Products.ZenTestCase
from Products.ZenTestCase.BaseTestCase import BaseTestCase

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2 import connections
from ZenPacks.zenoss.Layer2.zenmapper import ZenMapper

from .create_fake_devices import create_topology, router


class TestUpdateCatalog(BaseTestCase):
    def afterSetUp(self):
        super(TestUpdateCatalog, self).afterSetUp()

        self.dmd.Devices.createOrganizer('/Network/Router/Cisco')

        class TestableZenMapper(ZenMapper):
            def __init__(self):
                ''' It breaks tests somewhere in parent class '''

        self.zenmapper = TestableZenMapper()
        self.zenmapper.dmd = self.dmd
        self.zenmapper._workers = {}
        self.zenmapper.options = lambda: 1
        self.zenmapper.options.device = False
        self.zenmapper.options.clear = False
        self.zenmapper.options.cycle = False
        self.zenmapper.options.redis_url = ''
        self.zenmapper.options.workers = 0
        self.zenmapper.options.worker = False
        self.zenmapper.options.force = False
        self.zenmapper.options.optimize_interval = 0

        import logging
        self.zenmapper.log = logging.getLogger("test")

        zcml.load_config('testing-noevent.zcml', Products.ZenTestCase)
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)
        connections.clear()

    def topology(self, topology):
        create_topology(topology, self.dmd, update_catalog=False)

    def test_pair(self):
        self.topology('a b')
        a = self.dmd.getObjByPath(router("a"))
        b = self.dmd.getObjByPath(router("b"))

        # Test that disabling background updates works.
        a.setZenProperty("zL2UpdateInBackground", False)
        b.setZenProperty("zL2UpdateInBackground", False)
        self.zenmapper.main_loop()
        a_neighbors = connections.get_layer2_neighbor_devices(a)
        self.assertNotIn(b, a_neighbors)

        # Test that enabling background updates works.
        a.setZenProperty("zL2UpdateInBackground", True)
        b.setZenProperty("zL2UpdateInBackground", True)
        self.zenmapper.main_loop()
        a_neighbors = connections.get_layer2_neighbor_devices(a)
        self.assertIn(b, a_neighbors)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateCatalog))
    return suite
