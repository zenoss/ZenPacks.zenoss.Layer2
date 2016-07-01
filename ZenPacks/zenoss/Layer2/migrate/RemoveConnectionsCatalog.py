##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Remove legacy connections catalog"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration

log = logging.getLogger('zen.Layer2')


class RemoveConnectionsCatalog(ZenPackMigration):

    version = Version(1, 2, 1)

    def migrate(self, pack):
        log.info('Removing ConnectionsCatalog')
        if hasattr(pack.dmd.zport, 'connections_catalog'):
            pack.dmd.zport._delObject('connections_catalog')
