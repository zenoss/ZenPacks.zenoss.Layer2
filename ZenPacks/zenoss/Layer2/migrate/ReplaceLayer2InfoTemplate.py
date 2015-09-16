##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Replace Layer2Info template with ClientMACs modeler plugin.

This migration script finds all device classes and devices that have the
Layer2Info monitoring template bound. It then unbinds the monitoring
template and adds the zenoss.snmp.ClientMACs modeler plugin instead.

The Layer2Info monitoring template was created to model client MAC
addresses on switches. It was done as a datasource because Cisco devices
required polling using multiple community strings which zenmodeler and
SnmpClient didn't support.

We then ran into a problem that required us switching from the epoll to
select twisted reactor to simultaneously use more than 1024 file
descriptors. This broke the Layer2Info template because it used
pynetsnmp under the covers which required a select reactor.

It turns out that a modeler plugin could be used to do this modeling
after all. It just had to be a PythonPlugin instead of an SnmpPlugin.

"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration


LOG = logging.getLogger('zen.Layer2')
TEMPLATES_ZPROPERTY = 'zDeviceTemplates'
MODELER_ZPROPERTY = 'zCollectorPlugins'

LAYER2INFO_TEMPLATE = 'Layer2Info'
CLIENTMACS_PLUGIN = 'zenoss.snmp.ClientMACs'


class ReplaceLayer2InfoTemplate(ZenPackMigration):

    """Migrations required to replace Layer2Info monitoring template."""

    version = Version(1, 0, 3)

    def migrate(self, pack):
        migrate(pack.dmd.primaryAq(), devices=False)


def migrate(dmd, devices=False):
    """Replace Layer2Info template with ClientMACs modeler plugin.

    By default devices is False which means only device classes will be
    checked for the Layer2Info monitoring template being bound. It's
    possible that devices might also have Layer2Info locally bound. The
    script will miss those in an effort to run quickly.

    If you want a comprehensive replacement including local device
    bindings, you should run the following commands in zendmd.

        from ZenPacks.zenoss.Layer2.migrate import ReplaceLayer2InfoTemplate
        ReplaceLayer2InfoTemplate.migrate(dmd, devices=True)
        commit()

    """
    LOG.info("replacing Layer2Info template with ClientMACs modeler plugin")
    map(
        replace,
        dmd.Devices.getOverriddenObjects(
            TEMPLATES_ZPROPERTY,
            showDevices=devices))


def replace(obj):
    """Replace Layer2Info template with ClientMACs modeler plugin on obj."""
    if LAYER2INFO_TEMPLATE not in obj.zDeviceTemplates:
        # zDeviceTemplates was overridden, but didn't include Layer2Info.
        return

    if obj.aqBaseHasAttr('getOrganizerName'):
        logname = obj.getOrganizerName()
    else:
        logname = obj.titleOrId()

    LOG.info("replacing on %s", logname)

    obj.setZenProperty(
        TEMPLATES_ZPROPERTY, [
            t for t in obj.zDeviceTemplates
            if t != LAYER2INFO_TEMPLATE
        ])

    zCollectorPlugins = list(obj.zCollectorPlugins)
    if CLIENTMACS_PLUGIN not in zCollectorPlugins:
        zCollectorPlugins.append(CLIENTMACS_PLUGIN)
        obj.setZenProperty(MODELER_ZPROPERTY, zCollectorPlugins)
