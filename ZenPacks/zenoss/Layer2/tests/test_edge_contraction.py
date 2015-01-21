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
            {'source': 0, 'target': 1},
            {'source': 1, 'target': 2},
            {'source': 2, 'target': 3},
            {'source': 3, 'target': 4},
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
            nodes = [
                {'name': 0, 'important': True},
                {'name': 1},
                {'name': 3},
                {'name': 4, 'important': True},
            ],
            links=[
                {'source': 0, 'target': 1},
                {'source': 1, 'target': 2},
                {'source': 2, 'target': 3},
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
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
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
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
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
            {'source': 0, 'target': 1},
            {'source': 1, 'target': 2},
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
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

    def test_branch(self):
        ''' test based on real data '''
        nodes = [
             {'color': 'severity_debug',
              'highlight': True,
              'image': '/zport/dmd/img/icons/router.png',
              'important': True,
              'name': 'a'},
             {'color': 'severity_none',
              'highlight': False,
              'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png',
              'important': False,
              'name': '68:6E:6F:6D:78:6C'},
             {'color': 'severity_none',
              'highlight': False,
              'image': '/++resource++ZenPacks_zenoss_Layer2/img/link.png',
              'important': False,
              'name': '70:77:78:65:67:6C'}
        ]
        links = [
            {'color': 'gray', 'source': 0, 'target': 1},
            {'color': 'gray', 'source': 0, 'target': 2}
        ]
        self.assertEqual(contract_edges(nodes, links), dict(
            links=[],
            nodes=[
                 {'color': 'severity_debug',
                  'highlight': True,
                  'image': '/zport/dmd/img/icons/router.png',
                  'important': True,
                  'name': 'a'},
            ]
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
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
            {'source': 1, 'target': 3},
            {'source': 2, 'target': 3},
        ]
        res = contract_edges(nodes, links)

        self.assertEqual(res['links'], [
            {'source': 0, 'target': 1},
            {'source': 1, 'target': 2},
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


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestEdgeContraction))
    return suite
