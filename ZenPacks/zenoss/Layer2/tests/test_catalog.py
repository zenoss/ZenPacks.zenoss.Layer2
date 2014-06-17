##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

# from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase

class TestDataSourcePlugin(BaseTestCase):
    def test_onSuccess(self):
        print 'Hello!'

        self.assertEquals(2 + 2, 4)

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestDataSourcePlugin))
    return suite
