##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from itertools import chain
import logging
log = logging.getLogger('zen.ZenMapper')

import Globals
from Products.ZenUtils.CyclingDaemon import CyclingDaemon, DEFAULT_MONITOR
from transaction import commit

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import IConnectionsProvider


def main():
    zenmapper = ZenMapper()
    zenmapper.run()


class ZenMapper(CyclingDaemon):
    name = 'zenmapper'
    mname = name

    def buildOptions(self):
        super(CyclingDaemon, self).buildOptions()
        self.parser.add_option(
            '--cycletime',
            dest='cycletime', default=300, type="int",
            help="update connections every CYCLETIME seconds. 300 by default"
        )
        self.parser.add_option(
            "--monitor", dest="monitor",
            default=DEFAULT_MONITOR,
            help="Name of monitor instance to use for heartbeat "
            " events. Default is %s." % DEFAULT_MONITOR)

        self.parser.add_option(
            '-d', '--device', dest='device',
            help="Fully qualified device name ie www.confmon.com"
        )

    def get_devices_list(self):
        if self.options.device:
            device = self.dmd.Devices.findDevice(self.options.device)
            if device:
                log.info(
                    "Updating connections for device %s",
                    self.options.device
                )
                return [device]
            else:
                log.error(
                    "Device with id %s was not found",
                    self.options.device
                )
        else:
            return chain(
                self.dmd.Devices.getSubDevices(),
                self.dmd.Networks.getSubNetworks()
            )

    def main_loop(self):
        log.info('Updating catalog')
        cat = CatalogAPI(self.dmd.zport)
        for entity in self.get_devices_list():
            try:
                log.debug('Checking %s', entity.id)
                cat.add_node(entity)
            except TypeError:
                log.debug('Could not adapt %. Ignoring.', entity.id)
        commit()

if __name__ == '__main__':
    main()
