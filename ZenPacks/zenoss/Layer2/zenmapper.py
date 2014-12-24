##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from twisted.internet.defer import maybeDeferred
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
    init_log = True

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
        if self.init_log:
            log.info("Initializing")
            self.init_log = False
        obj = ZenMapperTask(self.dmd)
        task = maybeDeferred(obj.find_connections)
        task.addCallback(obj.onSuccess)
        task.addErrback(obj.onError)


class ZenMapperTask(object):
    def __init__(self, dmd):
        self.dmd = dmd
        self.connection = CatalogAPI(dmd.zport)

    def find_connections(self):
        log.info('Serching for connection providers')
        devices = self.dmd.Devices.getSubDevices()
        cp_list = []
        for device in devices:
            try:
                cp = IConnectionsProvider(device)
                cp_list.extend(list(cp.get_connections()))
            except TypeError:
                continue
        return cp_list

    def onSuccess(self, result):
        log.info('Updating catalog')
        for connection in result:
            self.connection.add_connection(connection)
        commit()

    def onError(self, reason):
        log.error('Error collecting data: {}'.format(reason.getErrorMessage()))


if __name__ == '__main__':
    zenmapper = ZenMapper()
    zenmapper.run()
