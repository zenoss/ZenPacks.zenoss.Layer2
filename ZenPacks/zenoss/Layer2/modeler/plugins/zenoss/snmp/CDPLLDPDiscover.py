######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################


__doc__ = """CDP and LLDP

Gather neighbor switches information of Cisco Discovery Protocol and
Link Layer Discovery Protocol from SNMP, and create DMD interface objects

"""

from Products.ZenUtils.Utils import prepId
from Products.DataCollector.plugins.CollectorPlugin import SnmpPlugin, GetTableMap

class CDPLLDPDiscover(SnmpPlugin):
    """
    Map CDP/LLDP entries to DMD 'NeighborSwitch' objects
    """
    order = 100
    compname = ""
    relname = "neighbor_switches"
    modname = "ZenPacks.zenoss.Layer2.NeighborSwitch"

    snmpGetTableMaps = (
        # CDP cache entries
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
        # LLDP remote systems entries
        GetTableMap('lldpRemEntry', '.1.0.8802.1.1.2.1.4.1.1',
                {
                    '.7': 'lldpRemPortId',
                    '.8': 'lldpRemPortDesc',
                    '.9': 'lldpRemSysName',
                    '.10': 'lldpRemSysDesc'
                }
        ),
    )

    def process(self, device, results, log):
        """
        From SNMP info gathered from the device, convert them
        to NeighborSwitch objects.
        """
        getdata, tabledata = results
        log.info('Modeler %s processing data for device %s', self.name(), device.id)
        
        log.debug("%s tabledata = %s", device.id, tabledata)
        self.rm = self.relMap()
        self.hashes = set()

        # CDP data
        for idx, data in tabledata.get("cdpCacheEntry").items():
            self._add_item(
                idx=prepId("cdp_{}".format(idx)),
                title=data.get('cdpCachePlatform', ''),
                description=data.get('cdpCacheSysName', ''),
                device_port=data.get('cdpCacheDevicePort', ''),
                ip_address=self.asip(data.get('cdpCacheAddress', '')),
                native_vlan=data.get('cdpCacheNativeVLAN', ''),
                location=data.get('cdpCachePhysLocation', '')
            )

        # LLDP data
        for idx, data in tabledata.get("lldpRemEntry").items():
            self._add_item(
                idx=prepId("lldp_{}".format(idx)),
                title=data.get('lldpRemSysName', ''),
                description=data.get('lldpRemSysDesc', ''),
                device_port=data.get('lldpRemPortDesc', '') \
                            or data.get('lldpRemPortId', '')
            )
        log.debug(self.rm)
        return self.rm

    def _add_item(self, idx, title, description, device_port, ip_address="", \
        native_vlan="", location=""):
        """
        Adds neighbor switch OM, ensuring it's unique
        """
        if not title:
            return

        om_dict = {
            'title': title,
            'description': description,
            'ip_address': ip_address,
            'device_port': device_port,
            'native_vlan': native_vlan,
            'location': location
            }
        om_hash = hash(frozenset(om_dict.items()))

        # CDP/LLDP table can contain duplicate entries, eliminating them
        if not om_hash in self.hashes:
            self.hashes.add(om_hash)
            om_dict['id'] = idx
            self.rm.append(self.objectMap(om_dict))
