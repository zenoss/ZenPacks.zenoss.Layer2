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

from ZenPacks.zenoss.Layer2.utils import asmac


class TestUtils(BaseTestCase):
    def test_asmac(self):
        self.assertEqual(
            asmac('\x01\x23\x45\x67\x89\xab'),
            '01:23:45:67:89:AB'
        )


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestUtils))
    return suite
