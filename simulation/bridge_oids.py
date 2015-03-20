
import random
import string
from twistedsnmp.pysnmpproto import v2c


class Network(object):
    def __init__(self, connections=None):
        self.hosts = {}
        self.current_ip = 127 << 24

        if connections:
            self.add_topology(connections)

    def add_topology(self, connections):
        ''' Connections - iterable of pairs of device id's '''

        if isinstance(connections, basestring):
            connections = parse_topology(connections)

        for c in connections:
            connect(
                self.get_host(c[0]),
                self.get_host(c[1])
            )

    def get_next_ip(self):
        self.current_ip += 1
        return asip(int2id(self.current_ip))

    def get_host(self, id):
        if id in self.hosts:
            return self.hosts[id]

        h = Host(name=id, ip=self.get_next_ip())
        self.hosts[id] = h
        return h

    def get_oids(self):
        oids = {}
        for k, host in self.hosts.iteritems():
            oids[host.ip] = host.get_oids()
        return oids

    def get_batchdump(self):
        lines = [
            "'/Devices/Network/simulated' "
            "zCollectorPlugins=["
            "'zenoss.snmp.DeviceMap', "
            "'zenoss.snmp.InterfaceMap'], "
            "zSnmpPort=1611"
        ]
        for host in self.hosts.values():
            lines.append(
                "'{ip}' setManageIp='{ip}', "
                "setTitle='{title}', "
                "setPerformanceMonitor='localhost'"
                .format(ip=host.ip, title=host.name)
            )
        return '\n'.join(lines)


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


def parse_topology(text):
    return (x.strip().split() for x in text.splitlines() if x.strip())


def connect(h1, h2):
    mac1 = random_mac()
    mac2 = random_mac()

    h1.add_interface(mac=mac1, clientmacs=[mac2])
    h2.add_interface(mac=mac2, clientmacs=[mac1])


class Host(object):
    netmask = '255.0.0.0'

    def __init__(self, name=None, ip=None):
        self.name = name or random_word()
        self.ip = ip or random_ip()
        self.interfaces = []

    def add_interface(self, **kwargs):
        self.interfaces.append(kwargs)

    def get_oids(self):
        oids = {}

        system = '.1.3.6.1.2.1.1'
        ifTable = '.1.3.6.1.2.1.2.2.1'
        ipAddrTable = '.1.3.6.1.2.1.4.20.1'
        dot1dTpFdbTable = '.1.3.6.1.2.1.17.4.3.1'
        dot1dBasePortEntry = '.1.3.6.1.2.1.17.1.4.1'

        oids[system + '.1.0'] = '%s simulated' % self.name  # sysDescr
        # sysObjectID
        oids[system + '.2.0'] = v2c.ObjectIdentifier('.1.3.6.1.4.1.9.1.516')
        oids[system + '.4.0'] = "support@somewhere.ca"  # sysContact
        oids[system + '.5.0'] = self.name  # sysName
        oids[system + '.6.0'] = "Somewhere"  # sysLocation

        for index, interface in enumerate(self.interfaces, 1):
            oids[ifTable + '.1.%s' % index] = index  # ifindex
            oids[ifTable + '.2.%s' % index] = 'interface%s' % index  # id
            oids[ifTable + '.3.%s' % index] = 6  # type = ethernetCsmacd
            oids[ifTable + '.4.%s' % index] = 1500  # mtu
            oids[ifTable + '.5.%s' % index] = v2c.Gauge32(1000 ** 3)  # mtu
            oids[ifTable + '.6.%s' % index] = interface['mac']  # MAC
            oids[ifTable + '.7.%s' % index] = 1  # adminStatus = up
            oids[ifTable + '.8.%s' % index] = 1  # operStatus = up

            ip = asip(int2id(index, 4))
            oids[ipAddrTable + '.1.%s' % ip] = v2c.IpAddress(ip)
            oids[ipAddrTable + '.2.%s' % ip] = index
            oids[ipAddrTable + '.3.%s' % ip] = v2c.IpAddress(self.netmask)

            for clientmac in interface['clientmacs']:
                oids[dot1dTpFdbTable + '.1.%s' % mac2oid(clientmac)] = clientmac
                # dot1dTpFdbPort
                oids[dot1dTpFdbTable + '.2.%s' % mac2oid(clientmac)] = index
                # dot1dTpFdbStatus = learned
                oids[dot1dTpFdbTable + '.3.%s' % mac2oid(clientmac)] = 3

            # binds port number and interface index
            oids[dot1dBasePortEntry + '.1.%s' % index] = index  # port number
            oids[dot1dBasePortEntry + '.2.%s' % index] = index  # ifindex

        return oids


def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)


def asip(val):
    """Convert a byte string to a IP.  """
    return '.'.join(str(ord(c)) for c in val)


def mac2oid(val):
    return '.'.join(str(int(b, 16)) for b in val.split(':'))


def random_id(length=6):
    return ''.join(
        random.choice(string.lowercase)
        for i in range(length)
    )


def int2id(i, length=4):
    if length == 0:
        return ''
    if i:
        return int2id(i / 256, length - 1) + chr(i % 256)
    else:
        return chr(0) * length


def random_ip():
    return asip(random_id(4))


def random_mac():
    return asmac(random_id())


def random_word():
    return random.choice(
        open('/usr/share/dict/words').readlines()
    ).strip()
