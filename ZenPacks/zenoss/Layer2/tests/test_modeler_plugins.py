##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenTestCase.BaseTestCase import BaseTestCase


class TestModelerPlugins(BaseTestCase):
    def test_client_macs_imports(self):
        from ZenPacks.zenoss.Layer2.modeler.plugins.\
            zenoss.snmp.ClientMACs import ClientMACs

    def test_cdplldpdiscover_imports(self):
        from ZenPacks.zenoss.Layer2.modeler.plugins.\
            zenoss.snmp.CDPLLDPDiscover import CDPLLDPDiscover


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModelerPlugins))
    return suite
