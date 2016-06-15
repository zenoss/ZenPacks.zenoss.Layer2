##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
This module contains a zenmapper daemon, which updates connections catalog.
'''

from itertools import chain
import logging
import multiprocessing

import Globals
from Products.ZenUtils.CyclingDaemon import CyclingDaemon, DEFAULT_MONITOR

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import IConnectionsProvider

log = logging.getLogger('zen.ZenMapper')


def _worker(connections, redis_url):
    """
    Performs cataloging of L2 connections.
    CatalogAPI instance don't need access to dmd here.
    """
    cat = CatalogAPI(zport=None, redis_url=redis_url)
    for con in connections:
        cat.add_connection(con)


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
            " events. Default is %s." % DEFAULT_MONITOR
        )
        self.parser.add_option(
            "--clear",
            dest="clear",
            action="store_true",
            help="Clear MACs catalog"
        )

        self.parser.add_option(
            '-d', '--device', dest='device',
            help="Fully qualified device name ie www.confmon.com"
        )

        self.parser.add_option(
            '--redis-url',
            dest='redis_url', type='string',
            help='redis connection string: redis://[hostname]:[port]/[db]'
        )

        self.parser.add_option(
            '--workers',
            dest='workers', default=10, type="int",
            help='Workers number'
        )

    def get_connections_list(self, cat):
        if self.options.device:
            device = self.dmd.Devices.findDevice(self.options.device)
            if device:
                log.info(
                    "Updating connections for device %s",
                    self.options.device
                )
                yield IConnectionsProvider(device).get_connections()
            else:
                log.error(
                    "Device with id %s was not found",
                    self.options.device
                )
                yield
        else:
            for node in chain.from_iterable([
                    self.dmd.Devices.getSubDevicesGen(),
                    self.dmd.Networks.getSubNetworks()]):
                if cat.is_changed(node):
                    yield IConnectionsProvider(node).get_connections()
                node._p_invalidate()

    def main_loop(self):
        """
        zenmapper main loop
        """
        cat = CatalogAPI(self.dmd.zport, redis_url=self.options.redis_url)
        if self.options.clear:
            log.info('Clearing catalog')
            cat.clear()
        else:
            log.info('Updating catalog')
            pool = multiprocessing.Pool(processes=self.options.workers)

            for connections in self.get_connections_list(cat):
                pool.apply_async(_worker,
                    (list(connections), self.options.redis_url))

            pool.close()
            pool.join()


if __name__ == '__main__':
    main()
