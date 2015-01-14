##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from __future__ import unicode_literals

import json
from mock import Mock, sentinel, MagicMock

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.Layer2.network_tree import get_connections_json, serialize

class TestSerialize(BaseTestCase):

    def test_exception(self):
        self.assertEqual(json.loads(serialize(Exception('test'))), dict(
            error='test'
        ))

    def test_text(self):
        self.assertEqual(json.loads(serialize('test')), dict(
            error='test'
        ))

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSerialize))
    return suite
