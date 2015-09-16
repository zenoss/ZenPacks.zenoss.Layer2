'''
    Script for checking forwarding table information over SNMP.
    (Calls snmpwalk, so check if it is in path)

    Usage:

    python bridge_snmp.py view -c <community_string> <host>

    python bridge_snmp.py clientmacs -c <community_string> <host>

    By default creates cache of walks in snmpwalk_cache.json file.
'''
from collections import defaultdict
import json
from pprint import pprint
from subprocess import check_output
import sys


try:
    from texttable import Texttable
except ImportError:
    Texttable = None


def main():

    action = sys.argv[1]

    client = SnmpClient(sys.argv[2:], cache='snmpwalk_cache.json')

    dict(
        view=view,
        clientmacs=clientmacs,
        vlan_clientmacs=vlan_clientmacs
    )[action](client)


def clientmacs(client):
    for fwd_entry in client.get_table({
        dot1dTpFdbAddress: 'MAC',
        dot1dTpFdbStatus: 'Status',
    }, {
        dot1dTpFdbStatus: lambda x: ForwardingEntryStatus.names.get(x, x),
    }).values():
        print fwd_entry['MAC'], fwd_entry['Status']


def vlan_clientmacs(client):
    for vlan_index in client.get_table({
        vtpVlanName: 'Vlan'
    }).keys():
        vlan = int(vlan_index[3:])
        print 'Vlan:', vlan
        client.set_vlan_index(vlan)
        clientmacs(client)

    aging_time = client.get(dot1dTpAgingTime)
    print 'Aging time: %ss' % aging_time


def view(client):
    name = client.get(sysDescr)
    aging_time = client.get(dot1dTpAgingTime)

    ifindex = {}
    for pi in client.get_table({
        dot1dBasePort: 'Port',
        dot1dBasePortIfIndex: 'Interface',
    }).values():
        ifindex[pi['Port']] = pi['Interface']

    interfaces = {}

    for interface in client.get_table({
        ifIndex: 'Index',
        ifDescr: 'Description',
        ifType: 'Type',
        ifPhysAddress: 'MAC',
    }).values():
        interfaces[interface['Index']] = dict(
            Description=interface['Description'],
            Type=interface['Type'],
            MAC=interface['MAC'],
            Clientmacs=[],
        )

    for fwd_entry in client.get_table({
        dot1dTpFdbAddress: 'MAC',
        dot1dTpFdbPort: 'Port',
        dot1dTpFdbStatus: 'Status',
    }, {
        dot1dTpFdbStatus: lambda x: ForwardingEntryStatus.names.get(x, x),
    }).values():
        try:
            i = interfaces[ifindex[fwd_entry['Port']]]
            i['Clientmacs'].append(
                '%s (%s)' % (fwd_entry['MAC'], fwd_entry['Status'])
            )
        except KeyError:
            pass

    print name
    print 'Aging time: %ss' % aging_time
    print format_table(
        interfaces.values(),
        ['Description', 'Type', 'MAC', 'Clientmacs'],
        [30, 20, 20, 100],
    )


# Define class for dictionary with autovivification
def Tree():
    return defaultdict(Tree)


def printtree(tree, tab=''):
    for k, v in tree.iteritems():
        print tab, k, ':',
        if isinstance(v, defaultdict):
            print
            printtree(v, tab + '\t')
        else:
            print v


class SnmpClient(object):
    def __init__(self, arguments, cache=None):
        self.command = ['snmpwalk', '-v2c', '-On'] + arguments
        print self.command
        self.cache = cache

    def check_output(self, args):
        command = ' '.join(args)
        output = None
        cache = {}
        if self.cache:
            try:  # to read cache and find output there
                with open(self.cache) as f:
                    cache = json.load(f)
            except Exception as e:
                print e
            output = cache.get(command)

        if output:
            print 'Got %s result from cache' % command
        else:
            print 'Executing:', command
            output = check_output(args).splitlines()

            if self.cache:
                # store output in cache
                cache[command] = output
                with open(self.cache, 'w') as f:
                    json.dump(cache, f, indent=2)

        return output

    def set_vlan_index(self, index):
        ''' Change command so community string is vlan indexed '''
        community_string_pos = self.command.index('-c') + 1
        try:
            community_string = self.command[community_string_pos]
        except IndexError:
            raise ValueError('There were no community string after -c')

        community_string_and_vlan = community_string.split('@')

        community_string = '{}@{}'.format(community_string_and_vlan[0], index)
        self.command[community_string_pos] = community_string

    def walk(self, oid):
        args = self.command + [oid]

        res = {}
        for line in self.check_output(args):
            try:
                k, v = line.split(' = ')
                res[k] = v
            except ValueError:  # were not able to split, continuation
                res[k] += '\n' + line
        return res

    def get(self, oid):
        res = self.walk(oid)
        return parse_value(res['.' + oid])

    def get_table(self, fields, fields_parsers={}):
        walk = {}
        for field in fields:
            walk.update(self.walk(field))

        prefix_length = len(fields.keys()[0])
        table = Tree()
        for k, v in walk.iteritems():
            prefix, key = k[1:prefix_length + 1], k[prefix_length + 1:]
            if prefix in fields:
                table[key][fields[prefix]] = \
                    fields_parsers.get(prefix, lambda x: x)(parse_value(v))

        return table


def join_if_list(v):
    if isinstance(v, list):
        return ', '.join(v)
    return v


def format_table(table, titles, widths):
    res = [titles]
    for row in table:
        res.append([join_if_list(row[title]) for title in titles])

    if Texttable:
        table = Texttable()
        table.set_cols_dtype(['t'] * len(titles))
        table.set_cols_width(widths)
        table.add_rows(res)
        return table.draw()
    else:
        res = ['\t'.join(l) for l in res]
        return '\n'.join(res)


def parse_value(v):
    try:
        t, v = v.split(':', 1)
    except ValueError:
        return v
    if t == 'INTEGER':
        try:
            return int(v)
        except ValueError:
            return v
    elif t == 'Hex-STRING':
        return ':'.join(v.strip().split())
    else:
        return v


# ftp://ftp.cisco.com/pub/mibs/v1/BRIDGE-MIB.my
dot1dTpFdbTable = '1.3.6.1.2.1.17.4.3'
#     "A table that contains information about unicast
#     entries for which the bridge has forwarding and/or
#     filtering information. This information is used
#     by the transparent bridging function in
#     determining how to propagate a received frame."

dot1dTpFdbEntry = dot1dTpFdbTable + '.1'
#     "Information about a specific unicast MAC address
#     for which the bridge has some forwarding and/or
#     filtering information."

dot1dTpFdbAddress = dot1dTpFdbEntry + '.1'
#     "A unicast MAC address for which the bridge has
#     forwarding and/or filtering information."

dot1dTpFdbPort = dot1dTpFdbEntry + '.2'
#     "Either the value '0', or the port number of the
#     port on which a frame having a source address
#     equal to the value of the corresponding instance
#     of dot1dTpFdbAddress has been seen. A value of
#     '0' indicates that the port number has not been
#     learned but that the bridge does have some
#     forwarding/filtering information about this
#     address (e.g. in the dot1dStaticTable).
#     Implementors are encouraged to assign the port
#     value to this object whenever it is learned even
#     for addresses for which the corresponding value of
#     dot1dTpFdbStatus is not learned(3)."

dot1dTpFdbStatus = dot1dTpFdbEntry + '.3'
# 	The status of this entry. The meanings of the values are:
#   one of the attributes of ForwardingEntryStatus class


class ForwardingEntryStatus(object):
    other = 1
    # none of the following. This would
    # include the case where some other
    # MIB object (not the corresponding
    # instance of dot1dTpFdbPort, nor an
    # entry in the dot1dStaticTable) is
    # being used to determine if and how
    # frames addressed to the value of
    # the corresponding instance of
    # dot1dTpFdbAddress are being
    # forwarded.

    invalid = 2
    # this entry is not longer valid
    # (e.g., it was learned but has since
    # aged-out), but has not yet been
    # flushed from the table.

    learned = 3
    # the value of the corresponding
    # instance of dot1dTpFdbPort was
    # learned, and is being used.

    self = 4
    # the value of the corresponding
    # instance of dot1dTpFdbAddress
    # represents one of the bridge's
    # addresses. The corresponding
    # instance of dot1dTpFdbPort
    # indicates which of the bridge's
    # ports has this address.

    mgmt = 5
    # the value of the corresponding
    # instance of dot1dTpFdbAddress is
    # also the value of an existing
    # instance of dot1dStaticAddress.


ForwardingEntryStatus.names = dict(
    (k, v)
    for v, k in ForwardingEntryStatus.__dict__.iteritems()
    if k in range(1, 6)
)


dot1dBasePortEntry = '1.3.6.1.2.1.17.1.4.1'
#     "A list of information for each port of the
#     bridge."

dot1dBasePort = dot1dBasePortEntry + '.1'
#  	"The port number of the port for which this entry
#     contains bridge management information."

dot1dBasePortIfIndex = dot1dBasePortEntry + '.2'
#     "The value of the instance of the ifIndex object,
#     defined in MIB-II, for the interface corresponding
#     to this port."

ifEntry = '1.3.6.1.2.1.2.2.1'
# An entry containing management information applicable to a
# particular interface.

ifIndex = ifEntry + '.1'
# A unique value, greater than zero, for each interface. It
# is recommended that values are assigned contiguously
# starting from 1. The value for each interface sub-layer
# must remain constant at least from one re-initialization of
# the entity's network management system to the next re-
# initialization.

ifDescr = ifEntry + '.2'
# A textual string containing information about the
# interface. This string should include the name of the
# manufacturer, the product name and the version of the
# interface hardware/software."

ifType = ifEntry + '.3'  # just type

ifPhysAddress = ifEntry + '.6'
# The interface's address at its protocol sub-layer. For
# example, for an 802.x interface, this object normally
# contains a MAC address. The interface's media-specific MIB
# must define the bit and byte ordering and the format of the
# value of this object. For interfaces which do not have such
# an address (e.g., a serial line), this object should contain
# an octet string of zero length.

sysDescr = '1.3.6.1.2.1.1.1.0'
dot1dTpAgingTime = '1.3.6.1.2.1.17.4.2.0'
vtpVlanName = '1.3.6.1.4.1.9.9.46.1.3.1.1.4'

if __name__ == '__main__':
    main()
