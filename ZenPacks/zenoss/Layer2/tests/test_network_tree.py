##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from __future__ import unicode_literals

import json
from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.Layer2.network_tree2 import get_json
from ZenPacks.zenoss.Layer2.network_tree2 import COMMON_LINK_COLOR, L2_LINK_COLOR

class TestGetJSON(BaseTestCase):

    def test_empty(self):
        self.assertEqual(json.loads(get_json([])), {
            'links': [],
            'nodes': []
        })

    def test_two_nodes(self):
        a = 'a', 'a_img', 'a_col'
        b = 'b', 'b_img', 'b_col'

        self.assertEqual(json.loads(get_json([
            (a, b, False),
        ])), {
            'links': [
                {'source': 0, 'target': 1, 'color': COMMON_LINK_COLOR},
            ],
            'nodes': [
                {'name': 'a', 'image': 'a_img', 'color': 'a_col', 'highlight': False},
                {'name': 'b', 'image': 'b_img', 'color': 'b_col', 'highlight': False},
            ]
        })

    def test_l2_link(self):
        a = 'a', 'a_img', 'a_col'
        b = 'b', 'b_img', 'b_col'

        self.assertEqual(json.loads(get_json([
            (a, b, True),
        ])), {
            'links': [
                {'source': 0, 'target': 1, 'color': L2_LINK_COLOR},
            ],
            'nodes': [
                {'name': 'a', 'image': 'a_img', 'color': 'a_col', 'highlight': False},
                {'name': 'b', 'image': 'b_img', 'color': 'b_col', 'highlight': False},
            ]
        })


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestGetJSON))
    return suite
