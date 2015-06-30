######################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################

from mock import Mock, sentinel

from Products.Five import zcml

import Products.ZenTestCase
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.Utils import monkeypatch

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.zenmapper import ZenMapper

from .create_fake_devices import create_topology, router


class TestUpdateCatalog(BaseTestCase):
    def afterSetUp(self):
        super(TestUpdateCatalog, self).afterSetUp()

        self.dmd.Devices.createOrganizer('/Network/Router/Cisco')

        self.cat = CatalogAPI(self.dmd.zport)

        class TestableZenMapper(ZenMapper):
            def __init__(self):
                ''' It breaks tests somewhere in parent class '''

        self.zenmapper = TestableZenMapper()
        self.zenmapper.dmd = self.dmd
        self.zenmapper.options = lambda: 1
        self.zenmapper.options.device = False
        self.zenmapper.options.clear = False

        zcml.load_config('testing-noevent.zcml', Products.ZenTestCase)
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)

    def topology(self, topology):
        # import pudb; pudb.set_trace()
        create_topology(topology, self.dmd, update_catalog=False)

    def test_empty_if_mapper_not_runned(self):
        self.topology('a b')
        self.assertEquals(len(self.cat.search()), 0)

    def test_pair(self):
        self.topology('a b')
        self.zenmapper.main_loop()
        self.assertIn(router('b'), self.cat.get_connected(router('a')))


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUpdateCatalog))
    return suite
