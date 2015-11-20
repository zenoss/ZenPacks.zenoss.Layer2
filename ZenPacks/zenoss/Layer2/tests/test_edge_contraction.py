##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import Mock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.Layer2.edge_contraction import contract_edges


class TestEdgeContraction(BaseTestCase):
    def test_chain(self):
        '''
            ! - 0 - 0 - 0 - !
            to
            ! - 0 - 0 - !
        '''
        nodes = [
            {'name': 0, 'important': True},
            {'name': 1},
            {'name': 2},
            {'name': 3},
            {'name': 4, 'important': True},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 1, 'target': 2, 'directed': False},
            {'source': 2, 'target': 3, 'directed': False},
            {'source': 3, 'target': 4, 'directed': False},
        ]
        res = contract_edges(nodes, links)
        self.assertEqual(res, dict(
            nodes=[
                {'name': 0, 'important': True},
                {'name': 1},
                {'name': 3},
                {'name': 4, 'important': True},
            ],
            links=[
                {'source': 0, 'target': 1, 'directed': False},
                {'source': 1, 'target': 2, 'directed': False},
                {'source': 2, 'target': 3, 'directed': False},
            ]
        ))

    def test_star(self):
        '''
            0 - ! - 0
            to
            !
        '''
        nodes = [
            {'name': 0, 'important': True},
            {'name': 1},
            {'name': 2},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 0, 'target': 2, 'directed': False},
        ]
        res = contract_edges(nodes, links)
        self.assertEqual(res, dict(
            links=[],
            nodes=[
                {'name': 0, 'important': True},
            ]
        ))

    def test_all_unimportant(self):
        '''
            0 - 0 - 0
            to nothing
        '''
        nodes = [
            {'name': 0},
            {'name': 1},
            {'name': 2},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 0, 'target': 2, 'directed': False},
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
            links=[],
            nodes=[],
        ))

    def test_branch(self):
        '''
            ! - 0 - 0
            to
            !
        '''
        nodes = [
            {'name': 0, 'important': True},
            {'name': 1},
            {'name': 2},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 1, 'target': 2, 'directed': False},
        ]
        res = contract_edges(nodes, links)
        self.assertEqual(res, dict(
            links=[],
            nodes=[
                {'name': 0, 'important': True},
            ]
        ))

    def test_one_node(self):
        nodes = [{'name': 1, 'important': True}]
        self.assertEqual(contract_edges(nodes, []), dict(
            links=[],
            nodes=[
                {'name': 1, 'important': True}
            ]
        ))

    def test_branch2(self):
        ''' test based on real data '''
        nodes = [{
            'color': 'severity_debug',
            'highlight': True,
            'image': '/zport/dmd/img/icons/router.png',
            'important': True,
            'name': 'a'
        }, {
            'color': 'severity_none',
            'highlight': False,
            'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png',
            'important': False,
            'name': '68:6E:6F:6D:78:6C'
        }, {
            'color': 'severity_none',
            'highlight': False,
            'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png',
            'important': False,
            'name': '70:77:78:65:67:6C'
        }]
        links = [
            {'color': 'gray', 'source': 0, 'target': 1, 'directed': False},
            {'color': 'gray', 'source': 0, 'target': 2, 'directed': False}
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
            links=[],
            nodes=[{
                'color': 'severity_debug',
                'highlight': True,
                'image': '/zport/dmd/img/icons/router.png',
                'important': True,
                'name': 'a'
            }]
        ))

    def test_duplicate(self):
        '''
            ! - 0 - !
              \   /
                0
            to
            ! - 0 - !
        '''
        nodes = [
            {'name': 0, 'important': True},
            {'name': 1},
            {'name': 2},
            {'name': 3, 'important': True},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 0, 'target': 2, 'directed': False},
            {'source': 1, 'target': 3, 'directed': False},
            {'source': 2, 'target': 3, 'directed': False},
        ]
        res = contract_edges(nodes, links)

        self.assertEqual(res['links'], [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 1, 'target': 2, 'directed': False},
        ])
        self.assertIn(
            {'name': 0, 'important': True},
            res['nodes']
        )
        self.assertIn(
            {'name': 3, 'important': True},
            res['nodes']
        )
        self.assertEqual(len(res['nodes']), 3)

    def test_excessive_node(self):
        '''
        '''
        nodes = [
            {'name': 0, 'important': True},
            {'name': 1},
            {'name': 2},
            {'name': 3, 'important': True},
        ]
        links = [
            {'source': 0, 'target': 1, 'directed': False},
            {'source': 0, 'target': 2, 'directed': False},
            {'source': 1, 'target': 3, 'directed': False},
            {'source': 2, 'target': 3, 'directed': False},
        ]
        nodes = [
            {
                'important': True,
                'name': '-switch.zenoss.loc',
                'highlight': True,
                'color': 'severity_info',
                'path': '/zport/dmd/Devices/Network/Cisco/devices/10.10.10.10',
                'image': '/zport/dmd/img/icons/noicon.png'
            },
            {
                'important': False,
                'name': '2C:36:F8:7B:65:21',
                'highlight': False,
                'color': 'severity_none',
                'path': '/zport/dmd/Cisco/devices/10.10.10.10/os/in/GE0_33',
                'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png'
            },
            {
                'important': False,
                'name': '08:00:1B:00:7A:D6',
                'highlight': False,
                'color': 'severity_none',
                'path': '08:00:1B:00:7A:D6',
                'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png'
            }
        ]
        links = [
            {'color': 'gray', 'directed': False, 'target': 1, 'source': 0},
            {'color': 'gray', 'directed': True, 'target': 2, 'source': 1}
        ]
        res = contract_edges(nodes, links)
        self.assertEqual(res, dict(
            links=[],
            nodes=[{
                'color': 'severity_info',
                'highlight': True,
                'image': '/zport/dmd/img/icons/noicon.png',
                'important': True,
                'name': '-switch.zenoss.loc',
                'path': '/zport/dmd/Devices/Network/Cisco/devices/10.10.10.10'
            }]
        ))


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestEdgeContraction))
    return suite
