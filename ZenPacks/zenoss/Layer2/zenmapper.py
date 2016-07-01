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
import os
import sys
import logging
import multiprocessing

import Globals
from Products.ZenUtils.CmdBase import remove_args
from Products.ZenUtils.CyclingDaemon import CyclingDaemon, DEFAULT_MONITOR
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import IConnectionsProvider

log = logging.getLogger('zen.ZenMapper')


def exec_worker(offset, chunk):
    """
    Used to create a worker for zenmapper daemon. Removes the
    "cycle", "workers" and "daemon" sys args and replace the current process by
    executing sys args
    """
    argv = [sys.executable]
    # Remove unwanted parameters from worker processes
    argv.extend(remove_args(sys.argv[:],
        ['-D','--daemon', '-c', '--cycle'], ['--workers']))
    # Tell the worker process to log to the log file and not just to console
    argv.append('--duallog')
    argv.append('--worker')
    argv.append('--offset=%i' % offset)
    argv.append('--chunk=%i' % chunk)
    try:
        os.execvp(argv[0], argv)
    except:
        log.exception("Failed to start process")


def main():
    zenmapper = ZenMapper()
    zenmapper.run()


class ZenMapper(CyclingDaemon):
    name = 'zenmapper'
    mname = name

    def __init__(self, noopts=0, app=None, keeproot=False):
        super(ZenMapper, self).__init__(noopts, app, keeproot)
        self._workers = {}

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
            "--force",
            dest="force",
            action="store_true",
            help="Force reindex"
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
            dest='workers', default=2, type="int",
            help='Workers number'
        )

        self.parser.add_option(
            "--worker",
            dest="worker",
            action="store_true",
            help="Run as worker"
        )

        self.parser.add_option(
            '--offset',
            dest='offset', type="int",
            help='Start point to process in worker'
        )

        self.parser.add_option(
            '--chunk',
            dest='chunk', type="int",
            help='Chunk size to process in worker'
        )

    def get_nodes_list(self, sort=False):
        """
        Returns list of devices and networks to index
        """
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
                return []

        nodes = chain.from_iterable([
            self.dmd.Devices.getSubDevicesGen(),
            self.dmd.Networks.getSubNetworks()])
        if not sort:
            return list(nodes)
        return sorted(nodes, key=lambda x: IGlobalIdentifier(x).getGUID())

    def start_worker(self, worker_id, chunk):
        """
        Creates new process of zenmapper with a task to process chunk of nodes
        """
        if worker_id in self._workers and self._workers[worker_id].is_alive():
            log.info('Worker %i still running.' % worker_id)
        else:
            log.info('Starting worker %i with chunk %i' % (worker_id, chunk))
            p = multiprocessing.Process(
                target=exec_worker,
                args=(worker_id, chunk)
                )
            p.daemon = True
            p.start()
            self._workers[worker_id] = p

    def _do_job(self, offset, chunk):
        """
        Do actual indexing of nodes into L2 catalog
        """
        if chunk:
            log.info('Worker %i: updating catalog' % offset)
            nodes = self.get_nodes_list(sort=True)[offset*chunk:offset*chunk + chunk]
            for node in nodes:
                self.cat.add_node(node, force=self.options.force)
                node._p_invalidate()
            log.info('Worker %i: finished job.' % offset)
        else:
            log.info('Updating catalog.')
            for node in self.get_nodes_list(sort=True):
                self.cat.add_node(node, force=self.options.force)
                node._p_invalidate()

    def _compact_catalog(self):
        """
        Removes records for deleted devices.
        """
        for worker in self._workers.values():
            if worker.is_alive():
                return

        if self.options.device:
            return

        guids = [IGlobalIdentifier(x).getGUID() for x in self.get_nodes_list()]
        log.info('Compacting catalog')
        self.cat.compact_catalog(guids)

    def main_loop(self):
        """
        zenmapper main loop
        """
        self.cat = CatalogAPI(self.dmd.zport, redis_url=self.options.redis_url)

        if self.options.clear:
            log.info('Clearing catalog')
            self.cat.clear()
        elif self.options.cycle and self.options.workers > 0:
            self._compact_catalog()
            chunk = len(self.get_nodes_list()) / self.options.workers + 1
            for i in xrange(self.options.workers):
                self.start_worker(i, chunk)
        elif self.options.worker:
            offset = self.options.offset
            chunk = self.options.chunk
            self._do_job(offset, chunk)
        else:
            self._compact_catalog()
            self._do_job(offset=0, chunk=0)


if __name__ == '__main__':
    main()
