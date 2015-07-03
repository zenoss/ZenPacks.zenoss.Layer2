from collections import defaultdict
from pprint import pprint
from subprocess import check_output
import sys

from tabulate import tabulate

from ZenPacks.zenoss.Layer2 import bridge_mib

TEST = False

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

ifType = ifEntry + '.3' # just type

ifPhysAddress = ifEntry + '.6'
# The interface's address at its protocol sub-layer. For
# example, for an 802.x interface, this object normally
# contains a MAC address. The interface's media-specific MIB
# must define the bit and byte ordering and the format of the
# value of this object. For interfaces which do not have such
# an address (e.g., a serial line), this object should contain
# an octet string of zero length.

sysDescr = '1.3.6.1.2.1.1.1.0'

def main():

    client = SnmpClient(sys.argv[1:])
    print client.get(sysDescr)

    print client.get_table(
        {
            ifIndex: 'Index',
            ifDescr: 'Description',
            ifType: 'Type',
            ifPhysAddress: 'MAC',
        }
    )

    print client.get_table(
        {
            bridge_mib.dot1dTpFdbAddress: 'MAC',
            bridge_mib.dot1dTpFdbPort: 'Port',
            bridge_mib.dot1dTpFdbStatus: 'Status',
        },
        {
            bridge_mib.dot1dTpFdbStatus: lambda x: bridge_mib.ForwardingEntryStatus.names[x],
        }
    )
    print client.get_table(
        walk,
        {
            bridge_mib.dot1dBasePort: 'Port',
            bridge_mib.dot1dBasePortIfIndex: 'Interface',
        }
    )




# Define class for dictionary with autovivification
Tree = lambda: defaultdict(Tree)

def printtree(tree, tab=''):
    for k, v in tree.iteritems():
        print tab, k, ':',
        if isinstance(v, defaultdict):
            print
            printtree(v, tab + '\t')
        else:
            print v

bridge_mib.ForwardingEntryStatus.names = dict(
    (k, v)
    for v, k in bridge_mib.ForwardingEntryStatus.__dict__.iteritems()
    if k in range(1, 6)
)


def parse_value(v):
    # Hex-STRING: 08 CC 68 44 02 12
    t, v = v.split(':', 1)
    if t == 'INTEGER':
        return int(v)
    elif t == 'Hex-STRING':
        return ':'.join(v.strip().split())
    else:
        return v


class SnmpClient(object):
    def __init__(self, arguments):
        self.command = ['snmpwalk', '-v2c', '-On'] + arguments

    def walk(self, oid):
        if TEST:
            return TEST_WALKS[oid]
        args = self.command + [oid]
        print 'Executing:', ' '.join(args)
        res = {}
        for line in check_output(args).splitlines():
            try:
                k, v = line.split(' = ')
                res[k] = v
            except ValueError: # were not able to split, continuation
                res[k] += '\n' + line
        return res

    def get(self, oid):
        res = self.walk(oid)
        return parse_value(res['.' + oid])

    def get_table(self, fields, fields_parsers={}):
        walk = {}
        for field in fields:
            walk.update(self.walk(field))

        return format_table(walk, fields, fields_parsers)


def format_table(walk_res, fields, fields_parsers={}):
    prefix_length = len(fields.keys()[0])
    table = Tree()
    for k, v in walk_res.iteritems():
        prefix, key = k[1:prefix_length + 1], k[prefix_length + 1:]
        if prefix in fields:
            table[key][fields[prefix]] = fields_parsers.get(prefix, lambda x: x)(parse_value(v))

    res = []
    titles = fields.values()
    for row in table.values():
        res.append([row[title] for title in titles])

    return tabulate(res, titles)


TEST_WALKS = {
    bridge_mib.dot1dTpFdbEntry: {
 '.1.3.6.1.2.1.17.4.3.1.1.0.208.184.12.3.71': 'Hex-STRING: 00 D0 B8 0C 03 47 ',
 '.1.3.6.1.2.1.17.4.3.1.1.0.34.86.52.191.20': 'Hex-STRING: 00 22 56 34 BF 14 ',
 '.1.3.6.1.2.1.17.4.3.1.1.212.133.100.68.36.112': 'Hex-STRING: D4 85 64 44 24 70 ',
 '.1.3.6.1.2.1.17.4.3.1.1.8.204.104.67.229.115': 'Hex-STRING: 08 CC 68 43 E5 73 ',
 '.1.3.6.1.2.1.17.4.3.1.1.8.204.104.67.236.72': 'Hex-STRING: 08 CC 68 43 EC 48 ',
 '.1.3.6.1.2.1.17.4.3.1.1.8.204.104.68.1.9': 'Hex-STRING: 08 CC 68 44 01 09 ',
 '.1.3.6.1.2.1.17.4.3.1.1.8.204.104.68.2.18': 'Hex-STRING: 08 CC 68 44 02 12 ',
 '.1.3.6.1.2.1.17.4.3.1.2.0.208.184.12.3.71': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.0.34.86.52.191.20': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.212.133.100.68.36.112': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.8.204.104.67.229.115': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.8.204.104.67.236.72': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.8.204.104.68.1.9': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.2.8.204.104.68.2.18': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.4.3.1.3.0.208.184.12.3.71': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.0.34.86.52.191.20': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.212.133.100.68.36.112': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.8.204.104.67.229.115': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.8.204.104.67.236.72': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.8.204.104.68.1.9': 'INTEGER: 3',
 '.1.3.6.1.2.1.17.4.3.1.3.8.204.104.68.2.18': 'INTEGER: 3'
    },
    bridge_mib.dot1dBasePortEntry : {
 '.1.3.6.1.2.1.17.1.4.1.1.1': 'INTEGER: 1',
 '.1.3.6.1.2.1.17.1.4.1.1.2': 'INTEGER: 2',
 '.1.3.6.1.2.1.17.1.4.1.2.1': 'INTEGER: 10101',
 '.1.3.6.1.2.1.17.1.4.1.2.2': 'INTEGER: 10102',
 '.1.3.6.1.2.1.17.1.4.1.3.1': 'OID: .0.0',
 '.1.3.6.1.2.1.17.1.4.1.3.2': 'OID: .0.0',
 '.1.3.6.1.2.1.17.1.4.1.4.1': 'Counter32: 0',
 '.1.3.6.1.2.1.17.1.4.1.4.2': 'Counter32: 0',
 '.1.3.6.1.2.1.17.1.4.1.5.1': 'Counter32: 0',
 '.1.3.6.1.2.1.17.1.4.1.5.2': 'Counter32: 0'
    }
}

if __name__ == '__main__':
    main()

