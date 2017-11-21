##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Remove existing service, then reinstall from definition."""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

try:
    import servicemigration as sm
    from Products.ZenUtils.application import ApplicationState
    from Products.ZenUtils.controlplane.application import getConnectionSettings
    from Products.ZenUtils.controlplane import ControlPlaneClient
    from Products.ZenUtils.controlplane import ControlCenterError
except ImportError:
    CONTROL_CENTER = False
else:
    CONTROL_CENTER = True

LOG = logging.getLogger("zen.Layer2")

# Name of service to remove.
SERVICE_NAME = "zenmapper"


class ReplaceService(ZenPackMigration):
    version = Version(1, 4, 0)

    def migrate(self, pack):
        if pack.prevZenPackVersion is None:
            # Do nothing if this is a fresh install of self.version.
            return

        if not CONTROL_CENTER:
            return

        sm.require("1.0.0")

        try:
            ctx = sm.ServiceContext()
        except Exception as e:
            LOG.warn("failed to replace %s service: %s", SERVICE_NAME, e)
            return

        service = get_service_id(ctx)
        if not service:
            return

        client = ControlPlaneClient(**getConnectionSettings())

        # Stop and remove the old service.
        remove_service(client, service)

        # Install the new service.
        pack.installServices()


def get_service_id(ctx):
    """Return service to be removed or None."""
    for service in ctx.getServiceChildren(ctx.getTopService()):
        if service.name == SERVICE_NAME:
            return service


def stop_service(client, service):
    """Stop service."""
    service_id = service._Service__data['ID']

    try:
        status = client.queryServiceStatus(service_id)
    except Exception as e:
        LOG.warn("failed to get %s service status: %s", service.name, e)
    else:
        for instance_status in status.itervalues():
            if instance_status.status != ApplicationState.STOPPED:
                try:
                    client.stopService(service_id)
                except Exception as e:
                    LOG.warn("failed to stop %s service: %s", service.name, e)

                return


def remove_service(client, service):
    """Remove service. Stopping it first if necessary."""
    stop_service(client, service)

    try:
        client.deleteService(service._Service__data['ID'])
    except ControlCenterError as e:
        LOG.warn("failed to remove %s service: %s", service.name, e)
