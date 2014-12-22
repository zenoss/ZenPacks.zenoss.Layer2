##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from mock import MagicMock, sentinel

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI, ConnectionsCatalogFactory

from ZenPacks.zenoss.Layer2.connections_provider import Connection


def fake_connection():
    con_id = 'connection_id'
    connected_to = ('connected_to1', 'connected_to2')
    layers = ('layer1', 'layer2')
    c = Connection(con_id, connected_to, layers)
    # d.getPhysicalPath.return_value = ('device_mock',)
    # d.id = 'id'
    # d.os.interfaces.return_value = [Mock(
    #     vlans=Mock(return_value=('id', 'vlan1')),
    #     macaddress='mac1',
    #     clientmacs=['mac2'],
    #     id='i1',
    #     device=Mock(return_value=Mock(id='device_mock')),
    #     getPhysicalPath=Mock(return_value=('device_mock', 'i1'))
    # )]
    return c


class TestCatalogAPI(BaseTestCase):
    def afterSetUp(self):
        super(TestCatalogAPI, self).afterSetUp()

        self.cat = CatalogAPI(self.app.zport)

    def test_catalog_is_empty(self):
        self.assertEqual(len(self.cat.search()), 0)

    def test_connection_is_added_to_catalog(self):
        c = fake_connection()
        self.cat.add_connection(c)
        catalogs = self.cat.search()
        print catalogs.entity_id, catalogs.connected_to, catalogs.layers




def aaa(ss, **kwards):
    print ss, '**' * 10, '\n', kwards