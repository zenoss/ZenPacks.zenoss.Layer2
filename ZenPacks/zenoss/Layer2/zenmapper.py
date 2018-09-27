##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
This module contains a zenmapper daemon, which updates connections graph.
'''

import datetime
import logging
import math
import multiprocessing
import optparse
import os
import resource
import sys

import Globals
from Products.ZenModel.Device import Device
from Products.ZenUtils.CmdBase import remove_args
from Products.ZenUtils.CyclingDaemon import CyclingDaemon, DEFAULT_MONITOR
from Products.ZenUtils.Utils import convToUnits
from Products.Zuul.interfaces import ICatalogTool

from ZenPacks.zenoss.Layer2 import connections
from ZenPacks.zenoss.Layer2.progresslog import ProgressLogger

LOG = logging.getLogger('zen.zenmapper')

# How often (in seconds) to update connection information for all devices.
DEFAULT_CYCLETIME = 300

# Hot often (in seconds) to optimize database tables. 0 means never.
DEFAULT_OPTIMIZE_INTERVAL = 0

# ZenMapper.updates_nodes() will log at INFO level instead of DEBUG if it
# takes longer than LONG_TIME seconds to update a node's edges, or if memory
# grows more than HIGH_MEMORY bytes while updating a node's edges.
LONG_TIME = 300
HIGH_MEMORY = pow(1024, 3)


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
        LOG.exception("failed to start worker process")


def main():
    zenmapper = ZenMapper()
    zenmapper.run()


class ZenMapper(CyclingDaemon):
    name = 'zenmapper'
    mname = name

    def __init__(self, noopts=0, app=None, keeproot=False):
        super(ZenMapper, self).__init__(noopts, app, keeproot)
        self._workers = {}

        if self.options.worker:
            self.log = self.log.getChild(
                "worker-{}".format(
                    self.options.offset))

    def buildOptions(self):
        super(CyclingDaemon, self).buildOptions()

        # Options common to multiple Zenoss processes.
        self.parser.add_option(
            "--monitor",
            dest="monitor",
            default=DEFAULT_MONITOR,
            help="Name of monitor to use for heartbeat events.\n"
                 "[default: %default]")

        self.parser.add_option(
            "--cycletime",
            dest="cycletime",
            default=DEFAULT_CYCLETIME,
            type="int",
            help="How often (in seconds) to update connections.\n"
                 "[default: %default]")

        self.parser.add_option(
            "-d",
            "--device",
            dest="device",
            help="Specific device ID for which to update connections.\n"
                 "[optional]")

        # Options specific to zenmapper.
        group = optparse.OptionGroup(self.parser, "ZenMapper Options")
        self.parser.add_option_group(group)

        group.add_option(
            "--clear",
            dest="clear",
            action="store_true",
            help="Clear all connections.")

        group.add_option(
            "--force",
            dest="force",
            action="store_true",
            help="Force update for unchanged devices.")

        group.add_option(
            "--optimize-interval",
            dest="optimize_interval",
            default=DEFAULT_OPTIMIZE_INTERVAL,
            type="int",
            help="How often (in seconds) to optimize database.\n"
                 "[default: %default]")

        group.add_option(
            "--workers",
            dest="workers",
            default=2,
            type="int",
            help="Number of workers.\n"
                 "[default: %default]")

        # Internal-use-only options. These are passed to workers by the main
        # process, and not expected to be passed to the main process by the
        # user.
        group.add_option(
            "--worker",
            dest="worker",
            action="store_true",
            help=optparse.SUPPRESS_HELP)

        group.add_option(
            "--offset",
            dest="offset",
            type="int",
            help=optparse.SUPPRESS_HELP)

        group.add_option(
            "--chunk",
            dest="chunk",
            type="int",
            help=optparse.SUPPRESS_HELP)

    def start_worker(self, worker_id, chunk_size):
        """
        Creates new process of zenmapper with a task to process chunk of nodes
        """
        if worker_id in self._workers and self._workers[worker_id].is_alive():
            self.log.info("worker-%i still running", worker_id)
        else:
            self.log.info("starting worker-%i for %s nodes", worker_id, chunk_size)
            p = multiprocessing.Process(
                target=exec_worker,
                args=(worker_id, chunk_size)
                )
            p.daemon = True
            p.start()
            self._workers[worker_id] = p

    def get_paths_and_uuids(self, uuids=False):
        """Return list of paths and list of uuids."""
        path_list, uuid_list = [], []

        for brain in ICatalogTool(self.dmd.Devices).search(Device):
            path = path_from_brain(brain)
            if path:
                path_list.append(path)

            if uuids:
                uuid = uuid_from_brain(brain)
                if uuid:
                    uuid_list.append(uuid)

        return path_list, uuid_list

    def update_nodes(self, paths):
        """Update nodes given paths."""
        updated = 0
        progress = ProgressLogger(self.log, total=len(paths), interval=60)

        for node in nodes_from_paths(self.dmd.Devices, paths):
            progress.increment()

            if not node.getZ("zL2UpdateInBackground", True):
                self.log.debug("%s: zL2UpdateInBackground = False", node.id)
                continue

            start_time = datetime.datetime.now()
            start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            try:
                added = connections.update_node(node, force=self.options.force)
            except Exception:
                self.log.exception("%s: unexpected exception while updating", node.id)
                continue

            if added:
                end_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                end_time = datetime.datetime.now()
                duration = end_time - start_time
                growth = (end_rss - start_rss) * 1024

                long_time = duration.total_seconds() > LONG_TIME
                high_memory = growth > HIGH_MEMORY

                if long_time and high_memory:
                    log_level = logging.INFO
                else:
                    log_level = logging.DEBUG

                self.log.log(
                    log_level,
                    "%s: updated (%s in %s)",
                    node.id,
                    convToUnits(growth, 1024.0, "B"),
                    duration)

                updated += 1
            else:
                self.log.debug("%s: already up to date", node.id)

        return updated

    def run(self):
        """Execute startup-time-only tasks."""
        super(ZenMapper, self).run()

        # Clean up deprecated data.
        connections.migrate()

        if self.options.clear:
            self.log.info("clearing database")
            connections.clear()

    def main_loop(self):
        if self.options.device:
            device = self.dmd.Devices.findDeviceByIdExact(self.options.device)
            if device:
                self.update_nodes([device.getPrimaryId()])
            else:
                self.log.error("device %s not found", self.options.device)

            return

        if self.options.worker:
            node_paths = self.get_paths_and_uuids(uuids=False)[0]
        else:
            node_paths, node_uuids = self.get_paths_and_uuids(uuids=True)

            self.log.info("pruning non-existent nodes")
            connections.compact(node_uuids)

            if connections.should_optimize(self.options.optimize_interval):
                self.log.info("optimizing database")
                connections.optimize()
                self.log.info("finished optimizing database")

        # Paths must be sorted for workers to get the right chunks.
        node_paths.sort()

        # Start workers if configured, but only if cycling.
        if self.options.workers > 0 and self.options.cycle:
            chunk_size = int(
                math.ceil(len(node_paths) / float(self.options.workers)))

            self.log.info(
                "starting %s workers (%s nodes each)",
                self.options.workers,
                chunk_size)

            for i in xrange(self.options.workers):
                self.start_worker(i, chunk_size)

            return

        if self.options.worker:
            start = self.options.offset * self.options.chunk
            node_paths = node_paths[start:start + self.options.chunk]

        self.log.info("checking %s nodes", len(node_paths))

        start_time = datetime.datetime.now()
        start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        updated = self.update_nodes(node_paths)

        end_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        growth = (end_rss - start_rss) * 1024

        self.log.info(
            "updated %s of %s nodes (%s in %s)",
            updated,
            len(node_paths),
            convToUnits(growth, 1024.0, "B"),
            duration)


def path_from_brain(brain):
    try:
        path = brain.getPath()
        if path:
            return path
    except Exception:
        return


def uuid_from_brain(brain):
    try:
        uuid = brain.uuid
        if uuid:
            return uuid
    except Exception:
        return


def nodes_from_paths(root, paths):
    for path in paths:
        try:
            node = root.unrestrictedTraverse(path)
            yield node
        except Exception:
            continue
        else:
            node._p_deactivate()
            if node._p_jar:
                node._p_jar.cacheGC()


if __name__ == '__main__':
    main()
