
import random
import string

from Products.ZenModel.IpInterface import IpInterface
from ZenPacks.zenoss.Layer2.utils import asmac

diamond = '''
    a b
    a c
    b d
    c d
'''

def main():
    create_topology(diamond)

def create_topology(connections):
    ''' Connections - iterable of pairs of device id's '''
    if isinstance(connections, basestring):
        connections = parse_topology(connections)

    for d1, d2 in connections:
        connect(get_device(d1), get_device(d2))

    dmd.Devices.reIndex()
    commit()

def parse_topology(text):
    return (x.strip().split() for x in text.splitlines() if x.strip())

def get_device(id):
    ''' Find device if exists, or return new '''
    d = find(id)
    if d:
        return d
    return create_router(id)

create_router = dmd.Devices.Network.Router.Cisco.createInstance

def connect(d1, d2):
    ''' Connect two devices by l2 link '''
    mac = random_mac()

    add_interface(d1, clientmacs=[mac])
    add_interface(d2, macaddress=mac)

def add_interface(dev, macaddress='', clientmacs=[]):
    ''' Add new interface to device '''
    eth_id = random_id()
    eth = IpInterface(eth_id, eth_id)
    eth.macaddress = macaddress
    eth.clientmacs = clientmacs
    dev.os.interfaces._setObject('unused_id_param', eth)

def random_id(length=6):
   return ''.join(random.choice(string.lowercase) for i in range(length))

def random_mac():
    return asmac(random_id())

if __name__ == '__main__':
    main()
