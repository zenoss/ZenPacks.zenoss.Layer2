##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Add Redis enndpoint to zenmapper service"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.Layer2')


class AddRedisEndpoint(ZenPackMigration):

    version = Version(1, 2, 1)

    def migrate(self, pack):
        # Apply only on ZP upgrade.
        if pack.prevZenPackVersion is None:
            return

        try:
            import servicemigration as sm
            from servicemigration.endpoint import Endpoint
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

        redis_endpoint = Endpoint(name="redis", purpose="import",
                                  application="redis", portnumber=6379,
                                  protocol="tcp")

        log.info("Looking for zenmapper services to migrate")
        services = filter(lambda s: s.name == "zenmapper", ctx.services)

        # Add the Redis endpoint import if it does not exist
        if not services:
            log.info("Found no 'zenmapper' services to migrate")
            # short circuit
            return
        for service in services:
            if not filter(lambda endpoint: endpoint.purpose == "import" and
                          endpoint.application == 'redis',
                          service.endpoints):
                log.info("Adding 'redis' endpoint import to service '%s'",
                         service.name)
                service.endpoints.append(redis_endpoint)
        ctx.commit()
