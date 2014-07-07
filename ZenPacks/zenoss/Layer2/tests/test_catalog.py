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
from ZenPacks.zenoss.Layer2.macs_catalog import CatalogAPI

def fake_device():
    d = Mock()
    d.getPhysicalPath.return_value = ('device_mock',)
    d.id = 'id'
    d.os.interfaces.return_value = [Mock(
        macaddress='mac1',
        clientmacs=['mac2'],
    )]
    return d

class TestCatalogAPI(BaseTestCase):
    def afterSetUp(self):
        super(TestCatalogAPI, self).afterSetUp()

        self.cat = CatalogAPI(self.app.zport)

    def test_catalog_is_empty(self):
        self.assertEqual(len(self.cat.search()), 0)

    def test_device_is_added_to_catalog(self):
        d = fake_device()

        self.cat.add_device(d)
        brains = self.cat.search()

        self.assertEqual(len(brains), 1)
        self.assertEqual(brains[0].macaddresses, ['mac1'])
        self.assertEqual(brains[0].clientmacs, ['mac2'])
        self.assertEqual(brains[0].id, 'id')

    def test_device_is_deleted_from_catalog(self):
        d = fake_device()

        self.cat.add_device(d)
        self.cat.remove_device(d)

        self.assertEqual(len(self.cat.search()), 0)

    def test_get_device_macadresses(self):
        d = fake_device()

        self.cat.add_device(d)

        self.assertEqual(self.cat.get_device_macadresses('id'), ['mac1'])


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCatalogAPI))
    return suite
