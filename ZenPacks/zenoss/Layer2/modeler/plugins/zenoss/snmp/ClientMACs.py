##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Models MAC address of connected clients using BRIDGE-MIB via SNMP."""

import collections
import copy

from Products.DataCollector.plugins.CollectorPlugin import GetTableMap
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.CollectorPlugin import SnmpPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.DataCollector.SnmpClient import SnmpClient
from Products.ZenUtils.Driver import drive

from twisted.internet.defer import inlineCallbacks, returnValue

from ZenPacks.zenoss.Layer2.utils import asmac, filterMacSet, is_valid_macaddr802


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
        'zLocalMacAddresses',
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

        # Inspect MAC addresses format in zLocalMacAddresses
        for mac in device.zLocalMacAddresses:
            if not is_valid_macaddr802(mac):
                log.warn("Invalid MAC Address '%s' found in %s", mac, 'zLocalMacAddresses')

        self.log = log

        state = ClientMACsState(
            device=device,
            iftable=getattr(device, 'get_ifinfo_for_layer2', {}),
            macs_indexed=getattr(device, 'macs_indexed', False))

        results = []

        for community in state.all_communities:
            snmp_client = state.get_snmp_client(community=community)
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
            # zLocalMacAddresses are usually internal MACS with no external use
            # hence remove the zLocalMacAddresses from device.clientmacs

            filtered_macs = filterMacSet(data['clientmacs'],
                                         device.zLocalMacAddresses)
            clientmacs.update(filtered_macs)

            maps.append(
                ObjectMap({
                    'compname': 'os',
                    'relname': 'interfaces',
                    'id': iface_id,
                    'clientmacs': sorted(filtered_macs),
                    'baseport': data['baseport'],
                }))

        # Also remove zLocalMacAddresses from device.set_reindex_maps()
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

    @property
    def primary_community(self):
        """Return device's primary SNMP community string."""
        return self.device.zSnmpCommunity

    @property
    def other_communities(self):
        """Return list of SNMP community strings other than the primary."""
        if not self.is_cisco:
            return []

        communities = []

        for ifid, info in self.iftable.iteritems():
            vlan_id = info.get('vlan_id')

            if not vlan_id and 'vlan' in ifid.lower():
                vlan_id = ifid.lower().replace('vlan', '')

            if vlan_id:
                # https://jira.zenoss.com/browse/ZEN-16951
                # vlan_id should be integer, not any string
                try:
                    communities.append(
                        "{}@{}".format(
                            self.primary_community,
                            int(vlan_id)))
                except Exception:
                    pass

        return communities

    @property
    def all_communities(self):
        """Return list of all SNMP communities to try."""
        return [self.primary_community] + self.other_communities

    def get_snmp_client(self, community):
        """Return an SnmpClient instance."""
        device_copy = copy.deepcopy(self.device)
        device_copy.zSnmpCommunity = community

        snmp_client = SnmpClient(
            hostname=device_copy.id,
            ipaddr=device_copy.manageIp,
            options=SnmpClientOptions(),
            device=device_copy,
            datacollector=None,
            plugins=[ClientMACsSnmpPlugin()])

        snmp_client.initSnmpProxy()

        return snmp_client

    def update_iftable(self, tabledata):
        """Update iftable with queried SNMP table data."""
        port_table = tabledata.get('dot1dBasePortTable', {})
        portid_to_ifindex = {
            x.get('dot1dBasePort'): x.get('dot1dBasePortIfIndex')
            for x in port_table.itervalues()}

        ifindex_to_portid = {v: k for k, v in portid_to_ifindex.iteritems()}
        ifindex_to_macs = collections.defaultdict(list)

        for tp_fdb_tablename in ('dot1dTpFdbTable', 'dot1qTpFdbTable'):
            tp_fdb_table = tabledata.get(tp_fdb_tablename, {})

            for tp_fdb_entry in tp_fdb_table.itervalues():
                entry_status = tp_fdb_entry.get('tpFdbStatus')
                if entry_status != ForwardingEntryStatus.learned:
                    continue

                entry_port = tp_fdb_entry.get('tpFdbPort')
                if not entry_port:
                    continue

                ifindex = portid_to_ifindex.get(entry_port)
                if not ifindex:
                    continue

                mac = tp_fdb_entry.get('tpFdbAddress')
                if mac:
                    ifindex_to_macs[ifindex].append(asmac(mac))

        for iface in self.iftable.itervalues():
            ifindex = int(iface['ifindex'])
            iface['clientmacs'].extend(ifindex_to_macs.get(ifindex, []))
            baseport = ifindex_to_portid.get(ifindex)
            if baseport:
                iface['baseport'] = baseport


class SnmpClientOptions(object):

    """Minimal options to run SnmpClient."""

    force = True
    discoverCommunity = False


class ClientMACsSnmpPlugin(SnmpPlugin):

    """SNMP plugin used by ClientMACs plugin to gather SNMP data."""

    snmpGetTableMaps = (

        # BRIDGE-MIB: Map of ports to interfaces.
        GetTableMap(
            'dot1dBasePortTable', '1.3.6.1.2.1.17.1.4.1', {
                '.1': 'dot1dBasePort',
                '.2': 'dot1dBasePortIfIndex',
            }),

        # BRIDGE-MIB: Physical ports to MAC addresses of clients.
        GetTableMap(
            'dot1dTpFdbTable', '1.3.6.1.2.1.17.4.3.1', {
                '.1': 'tpFdbAddress',
                '.2': 'tpFdbPort',
                '.3': 'tpFdbStatus',
            }),

        # Q-BRIDGE: Physical ports to MAC addresses of clients.
        GetTableMap(
            'dot1qTpFdbTable', '1.3.6.1.2.1.17.7.1.2.2.1', {
                '.1': 'tpFdbAddress',
                '.2': 'tpFdbPort',
                '.3': 'tpFdbStatus',
            }),
    )
