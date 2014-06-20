######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################

from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.Layer2.zeplugins import L2SuppressEventsPlugin

apply = L2SuppressEventsPlugin.apply

class TestSuppressEventsPlugin(BaseTestCase):
    def setUp(self):
        self.evtproxy = Mock(
            agent='zenping',
            summary='DOWN',
        )

    def test_imports(self):
        ''' if it imports - already good :) '''
# TODO: write actuall testcases

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSuppressEventsPlugin))
    return suite
