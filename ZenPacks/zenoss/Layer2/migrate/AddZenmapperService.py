##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Add zenmapper service"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.Layer2')


class AddZenmapperService(ZenPackMigration):

    version = Version(1, 2, 1)

    def migrate(self, pack):
        # Apply only on ZP upgrade.
        if pack.prevZenPackVersion is None:
            return

        try:
            import servicemigration as sm
        except ImportError:
            # No servicemigrations, which means we are on Zenoss 4.2.x or 5.0.x
            # No need to install service on Zenoss 5.0.x as service install
            # performed on each upgrade.
            return

        sm.require("1.0.0")

        try:
            ctx = sm.ServiceContext()
        except:
            log.warn("Couldn't generate service context, skipping.")
            return

        # Check whether zenmapper service is already installed.
        services = filter(lambda s: s.name == "zenmapper", ctx.services)
        if not services:
            log.info('Deploying zenmapper service')
            pack.installServices()

