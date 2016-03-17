##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Remove Layer2Info template """

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.Layer2')


class RemoveLayer2InfoTemplate(ZenPackMigration):

    version = Version(1, 1, 0)

    def migrate(self, pack):
        log.info('Removing Layer2Info template')
        try:
            pack.dmd.Devices.rrdTemplates._delObject(
                'Layer2Info', suppress_events=True
            )
        except Exception:
            # If this doesn't work, it's almost certainly because it was already removed
            # If it fails for some other reason, we still don't really care
            pass
