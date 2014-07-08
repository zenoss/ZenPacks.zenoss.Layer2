######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################


__doc__ = """CDP

Gather neighbour switches information of Cisco Discovery Protocol from SNMP,
and create DMD interface objects

"""

import re

from Products.ZenUtils.Utils import cleanstring, unsigned, prepId
from Products.DataCollector.plugins.CollectorPlugin import SnmpPlugin, GetTableMap

class CDP(SnmpPlugin):
    """
    Map CDP entries to DMD 'NeighbourSwitch' objects
    """
    order = 100
    compname = ""
    relname = "neighbour_switches"
    modname = "ZenPacks.zenoss.Layer2.NeighbourSwitch"

    snmpGetTableMaps = (
        # Extended interface information.
        GetTableMap('cdpCacheEntry', '.1.3.6.1.4.1.9.9.23.1.2.1.1',
                {
                    '.1': 'cdpCacheIfIndex',
                    '.4': 'cdpCacheAddress',
                    '.6': 'cdpCacheDeviceId',
                    '.7': 'cdpCacheDevicePort',
                    '.8': 'cdpCachePlatform',
                    '.11': 'cdpCacheNativeVLAN',
                    '.17': 'cdpCacheSysName',
                    '.23': 'cdpCachePhysLocation'
                }
        ),
    )

    def process(self, device, results, log):
        """
        From SNMP info gathered from the device, convert them
        to NeighbourSwitch objects.
        """
        getdata, tabledata = results
        log.info('Modeler %s processing data for device %s', self.name(), device.id)
        
        log.debug("%s tabledata = %s", device.id, tabledata)
        rm = self.relMap()
        for idx, data in tabledata.get("cdpCacheEntry").items():
            title = data.get('cdpCachePlatform', '')
            if title:
                om = self.objectMap({
                    'id': prepId("cdp_{}".format(idx)),
                    'title': title,
                    'description': data.get('cdpCacheSysName', ''),
                    'ip_address': self.asip(data.get('cdpCacheAddress', '')),
                    'device_port': data.get('cdpCacheDevicePort', ''),
                    'native_vlan': data.get('cdpCacheNativeVLAN', ''),
                    'location': data.get('cdpCachePhysLocation', '')
                    })
            rm.append(om)
        return rm
