##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import IConnectionsProvider
import Globals
from Products.ZenUtils.CyclingDaemon import CyclingDaemon, DEFAULT_MONITOR
from transaction import commit

import logging
log = logging.getLogger('zen.ZenMapper')


class ZenMapper(CyclingDaemon):

    name = 'zenmapper'
    mname = name

    def buildOptions(self):
        super(CyclingDaemon, self).buildOptions()
        self.parser.add_option(
            '--cycletime',
            dest='cycletime', default=300, type="int",
            help="check events every cycletime seconds"
        )
        self.parser.add_option(
            "--monitor", dest="monitor",
            default=DEFAULT_MONITOR,
            help="Name of monitor instance to use for heartbeat "
            " events. Default is %s." % DEFAULT_MONITOR)

    def main_loop(self):
        log.info('Searching for connection providers')
        cat = CatalogAPI(self.dmd.zport)
        for device in self.dmd.Devices.getSubDevices():
            try:
                cp = IConnectionsProvider(device)
            except TypeError:
                log.debug(
                    'Ignoring {0} because could not adapt'.format(device.id)
                )
                continue
            for connection in cp.get_connections():
                cat.add_connection(connection)
        for network in self.dmd.Networks.getSubNetworks():
            try:
                cp = IConnectionsProvider(network)
            except TypeError:
                log.debug(
                    'Ignoring network_{0} because could not adapt'.format(
                        network.id
                    )
                )
                continue
            for connection in cp.get_connections():
                cat.add_connection(connection)
        commit()

if __name__ == '__main__':
    zenmapper = ZenMapper()
    zenmapper.run()
