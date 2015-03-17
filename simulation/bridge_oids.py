
import random
import string
from twistedsnmp.pysnmpproto import v2c


def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)

def mac2oid(val):
    return '.'.join(str(int(b, 16)) for b in val.split(':'))

def random_id(length=6):
   return ''.join(random.choice(string.lowercase) for i in range(length))

def random_mac():
    return asmac(random_id())


def get_host_oids(hostname):
    oids = {}

    system = '.1.3.6.1.2.1.1'
    oids[system + '.1.0'] = '%s simulated' % hostname # sysDescr
    oids[system + '.2.0'] = v2c.ObjectIdentifier('.1.3.6.1.4.1.9.1.516') # sysObjectID
    oids[system + '.4.0'] = "support@somewhere.ca" # sysContact
    oids[system + '.5.0'] = hostname # sysName
    oids[system + '.6.0'] = "Somewhere" # sysLocation

    def add_interface(index, ip, mac, clientmacs, netmask='255.0.0.0'):
        ifTable = '.1.3.6.1.2.1.2.2.1'
        oids[ifTable + '.1.%s' % index] = index # ifindex
        oids[ifTable + '.2.%s' % index] = 'interface%s' % index # id
        oids[ifTable + '.3.%s' % index] = 6 # type = ethernetCsmacd
        oids[ifTable + '.4.%s' % index] = 1500 # mtu
        oids[ifTable + '.5.%s' % index] = v2c.Gauge32(1000 ** 3) # mtu
        oids[ifTable + '.6.%s' % index] = mac # MAC
        oids[ifTable + '.7.%s' % index] = 1 # adminStatus = up
        oids[ifTable + '.8.%s' % index] = 1 # operStatus = up

        ipAddrTable = '.1.3.6.1.2.1.4.20.1'
        oids[ipAddrTable + '.1.%s' % ip] = v2c.IpAddress(ip)
        oids[ipAddrTable + '.2.%s' % ip] = index
        oids[ipAddrTable + '.3.%s' % ip] = v2c.IpAddress(netmask)


        dot1dTpFdbTable = '1.3.6.1.2.1.17.4.3.1'
        for clientmac in clientmacs:
            oids[dot1dTpFdbTable + '.1.%s' % mac2oid(clientmac)] = clientmac
            oids[dot1dTpFdbTable + '.2.%s' % mac2oid(clientmac)] = index # dot1dTpFdbPort
            oids[dot1dTpFdbTable + '.3.%s' % mac2oid(clientmac)] = 3 # dot1dTpFdbStatus = learned

        dot1dBasePortEntry = '.1.3.6.1.2.1.17.1.4.1' # binds port number and interface index
        oids[dot1dBasePortEntry + '.1.%s' % index] = index # port number
        oids[dot1dBasePortEntry + '.2.%s' % index] = index # interface index

    for i in range(1, 5):
        add_interface(i, '127.0.0.%s' % i, random_mac(), [random_mac() for x in range(5)])

    return oids

