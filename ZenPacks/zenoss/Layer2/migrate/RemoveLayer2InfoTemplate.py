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
"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration


log = logging.getLogger('zen.Layer2')
TEMPLATES_ZPROPERTY = 'zDeviceTemplates'
MODELER_ZPROPERTY = 'zCollectorPlugins'

LAYER2INFO_TEMPLATE = 'Layer2Info'
CLIENTMACS_PLUGIN = 'zenoss.snmp.ClientMACs'


class RemoveLayer2InfoTemplate(ZenPackMigration):

    version = Version(1, 1, 0)

    def migrate(self, pack):
        log.info('Removing Layer2Info template')
        pack.dmd.Devices.rrdTemplates._delObject('Layer2Info')
