##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.Five import zcml
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from .create_fake_devices import get_device, add_interface, random_mac

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2 import connections


class TestLinks(BaseTestCase):
    """
    device link tests
    """

    def afterSetUp(self):
        super(TestLinks, self).afterSetUp()
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)
        connections.clear()

    def tearDown(self):
        connections.clear()
        super(TestLinks, self).tearDown()

    def test_get_expanded_links(self):
        # a has an empty ExpandedLink string
        a = get_device('b', self.dmd, organizer='/Server/SSH/Linux')
        self.assertEqual(len(a.getExpandedLinks()), 0)

        a = get_device('a', self.dmd)
        mac_a = random_mac()
        mac_b = random_mac()
        b = get_device('b', self.dmd, organizer='/Server/SSH/Linux')

        # make a look like a switch
        add_interface(
            a, macaddress=mac_a, clientmacs=[mac_b],
            vlans=['vlan1']
        )

        # make b look like a server
        add_interface(b, macaddress=mac_b, clientmacs=[], vlans=[])

        connections.update_node(a)
        connections.update_node(b)

        self.assertIn('Switch', b.getExpandedLinks())
        self.assertIn("/zport/dmd/Devices/Network/Router/Cisco/devices/a",
                      b.getExpandedLinks())
