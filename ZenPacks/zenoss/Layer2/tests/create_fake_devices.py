##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
This file contains functions that help to create devices for test, and make
connections between them.

    Most useful functions:

    create_topology - creates topology from description
    get_device - finds or creates device
    connect - connects two devices
'''

import random
import string

from Products.ZenModel.IpInterface import IpInterface
from ZenPacks.zenoss.Layer2.utils import asmac
from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI


def main():
    create_topology(diamond, dmd)
    # create_topology(Y_to_existing)
    # create_topology(binary_tree_topology(deepness=3, root='test'))
    # create_topology(Y)
    commit()

Y = '''
    a1 b1
    a1 c1
'''

diamond = '''
    a b A
    a c B
    b d A
    c d B
'''

two = '''
    one two layer
'''

Y_to_existing = '''
    10.87.100.1 fake1
    fake1 fake2
    fake1 fake3
'''


def binary_tree_topology(deepness=5, root='bin', edges=[]):
    if deepness <= 0:
        return

    l = root + '0'
    edges.append((root, l))
    binary_tree_topology(deepness - 1, l, edges)

    r = root + '1'
    edges.append((root, r))
    binary_tree_topology(deepness - 1, r, edges)

    return edges


def create_topology(connections, dmd, update_catalog=True):
    '''
        Connections should be iterable of pairs or triples
        (third element could be comma separated list of layers)
        Or multiline string, with space separated values in its lines.
    '''
    if isinstance(connections, basestring):
        connections = parse_topology(connections)

    for c in connections:
        layers = c[2].split(',') if len(c) > 2 else None
        connect(
            get_device(c[0], dmd),
            get_device(c[1], dmd),
            dmd,
            layers,
            update_catalog
        )

    dmd.Devices.reIndex()


def parse_topology(text):
    return (x.strip().split() for x in text.splitlines() if x.strip())


def get_device(id, dmd, organizer='/Network/Router/Cisco'):
    ''' Find device if exists, or return new '''
    d = dmd.Devices.findDevice(id)
    if d:
        return d

    dc = dmd.Devices.createOrganizer(organizer)
    return dc.createInstance(id)


def connect(d1, d2, dmd, layers=None, update_catalog=True):
    ''' Connect two devices by l2 link '''
    mac1 = random_mac()
    mac2 = random_mac()

    add_interface(d1, macaddress=mac1, clientmacs=[mac2], layers=layers)
    add_interface(d2, macaddress=mac2, clientmacs=[mac1], layers=layers)

    if update_catalog:
        catapi = CatalogAPI(dmd.zport)
        catapi.add_node(d1)
        catapi.add_node(d2)


def add_interface(dev, macaddress='', clientmacs=[], layers=None):
    ''' Add new interface to device '''
    eth_id = random_id()
    eth = IpInterface(eth_id, eth_id)
    eth.macaddress = macaddress
    eth.clientmacs = clientmacs
    if layers:
        eth.vlans = layers
    dev.os.interfaces._setObject('unused_id_param', eth)


def random_id(length=6):
    return ''.join(
        random.choice(string.lowercase)
        for i in range(length)
    )


def random_mac():
    return asmac(random_id())


def router(name):
    return '/zport/dmd/Devices/Network/Router/Cisco/devices/%s' % name

if __name__ == '__main__':
    main()
