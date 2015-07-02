######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################


'''
Layer2InfoPlugin only does modelling of client MAC addresses, for interfaces.
It is implemented as monitoring plugin, not as modeler plugin because there is
no way to tell one modeler to run after another, and we need to run this code
after interfaces are modeled.
'''

from logging import getLogger
log = getLogger('zen.Layer2Plugins')

import re

from twisted.internet import defer

from Products.DataCollector.SnmpClient import SnmpClient
from Products.DataCollector.plugins.CollectorPlugin import SnmpPlugin
from Products.DataCollector.plugins.CollectorPlugin import GetTableMap
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses
from Products.ZenUtils.Utils import prepId
from Products.ZenUtils.Driver import drive

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource \
    import PythonDataSourcePlugin

from .bridge_mib import dot1dTpFdbEntry, dot1dBasePortEntry
from .bridge_mib import ForwardingEntryStatus
from .utils import asmac

PLUGIN_NAME = "Layer2Info"


class Layer2Options(object):
    """ Minimal options to run SnmpPlugin """
    force = True
    discoverCommunity = False


class Layer2SnmpPlugin(SnmpPlugin):
    """
    Snmp plugin to collect MAC forwarding tables and ports
    """

    snmpGetTableMaps = (
        # Layer2: physical ports to MACs of clients
        GetTableMap('dot1dTpFdbTable', dot1dTpFdbEntry, {
            '.1': 'dot1dTpFdbAddress',
            '.2': 'dot1dTpFdbPort',
            '.3': 'dot1dTpFdbStatus'
        }),
        # Ports to Interfaces
        GetTableMap('dot1dBasePortEntry', dot1dBasePortEntry, {
            '.1': 'dot1dBasePort',
            '.2': 'dot1dBasePortIfIndex'
        })
    )

    def name(self):
        return PLUGIN_NAME


def join_vlan(community, vlan):
    ''' Return the same community string with other vlan.
        If it had vlan already - replace it.

        This is for SNMP Community String Indexing.
        Read more: http://goo.gl/y32XSu

        >>> join_vlan('public', '1')
        'public@1'
        >>> join_vlan('public@1', '2')
        'public@2'
        >>> join_vlan('public@1', '')
        'public'
        >>> join_vlan('public', '')
        'public'
    '''
    return community.split('@')[0] + (
        ('@' + vlan) if vlan else ''
    )


class Layer2InfoPlugin(PythonDataSourcePlugin):
    """
    Datasource plugin for Device to collect MAC forwarding tables
    """

    proxy_attributes = (
        'zSnmpCommunity',
        'zSnmpVer',
        'zSnmpPort',
        'zSnmpTimeout',
        'zSnmpTries',
        'zSnmpSecurityName',
        'zSnmpAuthType',
        'zSnmpPrivType',
        'zSnmpPrivPassword',
        'zSnmpEngineId',
        'get_ifinfo_for_layer2',
        'getHWManufacturerName',
        'macs_indexed',
    )

    component = None

    def __init__(self, config):
        self.isCisco = 'cisco' in getattr(
            config.datasources[0],
            'getHWManufacturerName',
            '').lower()

    def get_snmp_client(self, config, ds0):
        sc = SnmpClient(
            hostname=config.id,
            ipaddr=config.manageIp,
            options=Layer2Options(),
            device=ds0,
            datacollector=self,
            plugins=[Layer2SnmpPlugin(), ]
        )
        sc.initSnmpProxy()
        return sc

    @defer.inlineCallbacks
    def collect(self, config):
        """
        Iterates over device's Ip Interfaces and gathers Layer 2 information
        with SNMP
        """
        results = self.new_data()
        ds0 = config.datasources[0]
        ds0.id = config.id

        self.iftable = ds0.get_ifinfo_for_layer2

        self.macs_indexed = ds0.macs_indexed

        self.jobs = []

        for vlan in self.get_vlans():  # ["1", "951"]:
            ds0.zSnmpCommunity = join_vlan(ds0.zSnmpCommunity, vlan)
            sc = self.get_snmp_client(config, ds0)

            try:
                yield drive(sc.doRun)
            except Exception:
                # Error will be logged at INFO by SnmpClient.
                pass
            else:
                self._prep_iftable(self.get_snmp_data(sc))
            finally:
                sc.stop()

        results['maps'] = self.get_maps()

        defer.returnValue(results)

    @staticmethod
    def get_snmp_data(sc):
        plugin_data = sc._tabledata.get(PLUGIN_NAME, {})
        return dict(
            (tmap.name, tmap.mapdata(data))
            for tmap, data in plugin_data.iteritems()
        )

    def get_vlans(self):
        '''
        Yields sequence of strings - vlans ids,
        extracted from keys in self.iftable
        '''
        yield ''  # for query without VLAN id

        # Only Cisco devices support community@VLAN SNMP contexts.
        if self.isCisco:
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

    @staticmethod
    def _extract_clientmacs(dot1dTpFdbTable, interface):
        ''' Gets clientmacs for interface from dot1dTpFdbTable '''
        for item in dot1dTpFdbTable.values():
            mac = item.get('dot1dTpFdbAddress')
            forwarding_status = item.get('dot1dTpFdbStatus')
            if (
                mac
                and (forwarding_status == ForwardingEntryStatus.learned)
                and (interface['baseport'] == item.get('dot1dTpFdbPort'))
            ):
                interface['clientmacs'].append(asmac(mac))

    def _prep_iftable(self, tabledata):
        """
        Extracts MAC addresses and switch ports from Snmp data
        """
        dot1dTpFdbTable = tabledata.get("dot1dTpFdbTable", {})
        dot1dBasePortEntry = tabledata.get("dot1dBasePortEntry", {})
        for interface_data in self.iftable.values():
            ifindex = int(interface_data["ifindex"])

            for row in dot1dBasePortEntry.values():
                if ifindex == row.get('dot1dBasePortIfIndex'):
                    baseport = row.get('dot1dBasePort')
                    interface_data['baseport'] = baseport
                    self._extract_clientmacs(dot1dTpFdbTable, interface_data)

    def get_maps(self):
        """
        Create Object/Relationship map for component remodeling.

        @param datasource: device datasourse
        @type datasource: instance of PythonDataSourceConfig
        @yield: ObjectMap|RelationshipMap
        """
        clientmacs = set()
        res = []

        for ifid, data in self.iftable.items():
            clientmacs.update(data['clientmacs'])
            res.append(ObjectMap({
                "compname": 'os',
                'relname': 'interfaces',
                'id': ifid,
                'modname': 'Products.ZenModel.IpInterface',
                'clientmacs': list(set(data['clientmacs'])),
                'baseport': data['baseport']
            }))

        if not self.macs_indexed and self.iftable:
            log.info('There are interfaces and they were not indexed yet')
            clientmacs = 'reindex please'
        res.insert(0, ObjectMap({
            "set_reindex_maps": clientmacs,
        }))
        return res

    def onSuccess(self, result, config):
        """
        This method return a data structure with zero or more events, values
        and maps.  result - is what returned from collect.
        """
        ds = config.datasources[0]
        for component in result['values'].keys():
            result['events'].append({
                'component': component,
                'summary': 'Layer2 Info ok',
                'eventKey': ds.eventKey,
                'eventClass': ds.eventClass,
                'severity': ZenEventClasses.Clear,
            })
        return result

    def onError(self, result, config):
        """
        This callback creates event if error occured.
        """
        log.error(result)
        data = self.new_data()
        msg = str(result.value)
        ds = config.datasources[0]

        if 'timeout' not in msg.lower():
            data['events'].append({
                'component': self.component,
                'summary': msg,
                'eventKey': ds.eventKey,
                'eventClass': ds.eventClass,
                'severity': ZenEventClasses.Error,
            })
        return data
