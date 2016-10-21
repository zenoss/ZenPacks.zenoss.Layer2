##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.Layer2.utils import (asmac,
                                          is_valid_macaddr802,
                                          filterMacSet)


class TestUtils(BaseTestCase):
    def test_asmac(self):
        self.assertEqual(
            asmac('\x01\x23\x45\x67\x89\xab'),
            '01:23:45:67:89:AB'
        )

    def test_is_valid_macaddr802(self):
        mac = '01:23:45:67:89:AB'
        self.assertTrue(is_valid_macaddr802(mac))

    def test_filterMacSet(self):
        a = ['01:23:45:67:89:AB', '00:00:00:00:00:00']
        b = ['00:00:00:00:00:00', 'invalid_mac']
        c = filterMacSet(a, b)
        self.assertTrue('00:00:00:00:00:00' not in c)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUtils))
    return suite
