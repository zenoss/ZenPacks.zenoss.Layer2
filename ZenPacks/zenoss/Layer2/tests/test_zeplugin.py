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

from zenoss.protocols.protobufs.zep_pb2 import STATUS_SUPPRESSED


class TestSuppressEventsPlugin(BaseTestCase):
    def setUp(self):
        import ZenPacks.zenoss.Layer2.zeplugins as zeplugins

        self.apply_plugin = zeplugins.L2SuppressEventsPlugin.apply
        self.CatalogAPI = zeplugins.CatalogAPI = Mock()

        self.evtproxy = Mock(
            agent='zenping',
            summary='DOWN',
            eventState=None,
        )
        self.dmd = Mock()

    def apply(self):
        self.apply_plugin(self.evtproxy, self.dmd)

    def mock_catalog(self, val):
        self.CatalogAPI.return_value.check_working_path.return_value = val

    def is_suppressed(self):
        return self.evtproxy.eventState == STATUS_SUPPRESSED

    def test_upstream_up(self):
        self.mock_catalog(True)

        self.apply()

        self.assertFalse(self.is_suppressed())

    def test_suppresses(self):
        self.mock_catalog(False)

        self.apply()

        self.assertTrue(self.is_suppressed())

    def test_not_zenping(self):
        self.evtproxy.agent = 'zencommand'

        self.apply()

        self.assertFalse(self.is_suppressed())


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSuppressEventsPlugin))
    return suite
