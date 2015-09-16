##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Models MAC address of connected clients using BRIDGE-MIB via SNMP."""

from Products.DataCollector.plugins.CollectorPlugin import GetTableMap
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.CollectorPlugin import SnmpPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.DataCollector.SnmpClient import SnmpClient
from Products.ZenUtils.Driver import drive

from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.zenoss.Layer2.utils import asmac


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
#   The status of this entry. The meanings of the values are:
#   one of the attributes of ForwardingEntryStatus class


class ForwardingEntryStatus(object):

    # none of the following. This would include the case where some
    # other MIB object (not the corresponding instance of
    # dot1dTpFdbPort, nor an entry in the dot1dStaticTable) is being
    # used to determine if and how frames addressed to the value of the
    # corresponding instance of dot1dTpFdbAddress are being forwarded.
    other = 1

    # this entry is not longer valid (e.g., it was learned but has since
    # aged-out), but has not yet been flushed from the table.
    invalid = 2

    # the value of the corresponding instance of dot1dTpFdbPort was
    # learned, and is being used.
    learned = 3

    # the value of the corresponding instance of dot1dTpFdbAddress
    # represents one of the bridge's addresses. The corresponding
    # instance of dot1dTpFdbPort indicates which of the bridge's ports
    # has this address.
    self = 4

    # the value of the corresponding instance of dot1dTpFdbAddress is
    # also the value of an existing instance of dot1dStaticAddress.
    mgmt = 5


dot1dBasePortEntry = '1.3.6.1.2.1.17.1.4.1'
#     "A list of information for each port of the
#     bridge."

dot1dBasePort = dot1dBasePortEntry + '.1'
#   "The port number of the port for which this entry
#     contains bridge management information."

dot1dBasePortIfIndex = dot1dBasePortEntry + '.2'
#     "The value of the instance of the ifIndex object,
#     defined in MIB-II, for the interface corresponding
#     to this port."


class ClientMACs(PythonPlugin):

    """Client MAC address modeler plugin.

    This is implemented as a PythonPlugin instead of SnmpPlugin because
    it needs to query the device with multiple community strings, and
    this is currently not supported by SnmpPlugin.

    """

    localDeviceProperties = (
        'get_ifinfo_for_layer2',
        'getHWManufacturerName',
        'macs_indexed',
    )

    deviceProperties = (
        PythonPlugin.deviceProperties +
        SnmpPlugin.deviceProperties +
        localDeviceProperties
    )

    @inlineCallbacks
    def collect(self, device, log):
        """Return deferred with results of collection."""
        log.info("%s: collecting client MAC addresses", device.id)

        self.log = log

        state = ClientMACsState(
            device=device,
            iftable=getattr(device, 'get_ifinfo_for_layer2', {}),
            macs_indexed=getattr(device, 'macs_indexed', False))

        results = []

        for community in state.snmp_communities():
            snmp_client = state.snmp_client(community=community)
            try:
                yield drive(snmp_client.doRun)
            except Exception:
                # Error will be logged at INFO by SnmpClient.
                pass
            else:
                client_results = snmp_client.getResults()
                for plugin, (_, tabledata) in client_results:
                    results.append(
                        {x.name: x.mapdata(y) for x, y in tabledata.items()})
            finally:
                snmp_client.stop()
        returnValue((state, results))

    def process(self, device, results, log):
        """Process collect's results. Return iterable of datamaps."""
        state, results = results

        for tabledata in results:
            state.update_iftable(tabledata)

        clientmacs = set()
        maps = []

        for iface_id, data in state.iftable.items():
            clientmacs.update(data['clientmacs'])
            maps.append(
                ObjectMap({
                    'compname': 'os',
                    'relname': 'interfaces',
                    'id': iface_id,
                    'clientmacs': list(set(data['clientmacs'])),
                    'baseport': data['baseport'],
                }))

        if not state.macs_indexed and state.iftable:
            reindex_map = ObjectMap({'set_reindex_maps': clientmacs})
            maps.insert(0, reindex_map)

        return maps


class ClientMACsState(object):

    """State scoped to each call to ClientMACs.collect().

    This separate state is used becaused a single ClientMACs object is
    instatiated and reused to collect from all devices repeatedly until
    zenmodeler is restarted. More often than not, we're only interested
    in maintainin state for a single collection of a single device.

    """

    device = None
    iftable = None
    macs_indexed = None

    def __init__(self, device=None, iftable=None, macs_indexed=None):
        self.device = device
        self.iftable = iftable
        self.macs_indexed = macs_indexed

    @property
    def is_cisco(self):
        manufacturer = getattr(self.device, 'getHWManufacturerName', 'Unknown')
        return 'cisco' in manufacturer.lower()

    def vlans(self):
        """Generate VLAN IDs as strings extracted from keys in iftable."""
        yield ''  # for query without VLAN id

        # Only Cisco devices support community@VLAN SNMP contexts.
        if self.is_cisco:
            # TODO: find a better way to get a list of vlans
            # not parsing from interface ids
            for ifid in self.iftable:
                if 'vlan' in ifid.lower():
                    vlan_id = ifid.lower().replace('vlan', '')

                    # https://jira.zenoss.com/browse/ZEN-16951
                    # vlan_id should be integer, not any string
                    try:
                        yield str(int(vlan_id))
                    except ValueError:
                        pass

    def snmp_communities(self):
        """Generate SNMP community strings."""
        for vlan in self.vlans():
            community = self.device.zSnmpCommunity.split('@')[0]
            if vlan:
                yield '{}@{}'.format(community, vlan)
            else:
                yield community

    def snmp_client(self, community='public'):
        """Return an SnmpClient instance."""
        self.device.zSnmpCommunity = community

        snmp_client = SnmpClient(
            hostname=self.device.id,
            ipaddr=self.device.manageIp,
            options=SnmpClientOptions(),
            device=self.device,
            datacollector=None,
            plugins=[ClientMACsSnmpPlugin()])

        snmp_client.initSnmpProxy()

        return snmp_client

    def update_iftable(self, tabledata):
        """Update iftable with queried SNMP table data."""
        dot1dTpFdbTable = tabledata.get("dot1dTpFdbTable", {})
        dot1dBasePortEntry = tabledata.get("dot1dBasePortEntry", {})

        for iface in self.iftable.values():
            ifindex = int(iface["ifindex"])

            for row in dot1dBasePortEntry.values():
                if ifindex == row.get('dot1dBasePortIfIndex'):
                    iface['baseport'] = row.get('dot1dBasePort')

                    for item in dot1dTpFdbTable.values():
                        mac = item.get('dot1dTpFdbAddress')
                        learned = item.get('dot1dTpFdbStatus') \
                            == ForwardingEntryStatus.learned
                        matched_baseport = iface['baseport'] \
                            == item.get('dot1dTpFdbPort')

                        if mac and learned and matched_baseport:
                            iface['clientmacs'].append(asmac(mac))


class SnmpClientOptions(object):

    """Minimal options to run SnmpClient."""

    force = True
    discoverCommunity = False


class ClientMACsSnmpPlugin(SnmpPlugin):

    """SNMP plugin used by ClientMACs plugin to gather SNMP data."""

    snmpGetTableMaps = (

        # Layer2: physical ports to MACs of clients
        GetTableMap(
            'dot1dTpFdbTable', dot1dTpFdbEntry, {
                '.1': 'dot1dTpFdbAddress',
                '.2': 'dot1dTpFdbPort',
                '.3': 'dot1dTpFdbStatus',
            }),

        # Ports to Interfaces
        GetTableMap(
            'dot1dBasePortEntry', dot1dBasePortEntry, {
                '.1': 'dot1dBasePort',
                '.2': 'dot1dBasePortIfIndex',
            }),
    )
