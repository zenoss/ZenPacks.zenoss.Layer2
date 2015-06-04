##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
"""
Custom ZenPack initialization code. All code defined in this module will be
executed at startup time in all Zope clients.
"""

import logging
log = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenUtils.Utils import unused
from Products.ZenModel.ZenPack import ZenPackBase

import ZenPacks.zenoss.Layer2.patches

unused(Globals)


class ZenPack(ZenPackBase):
    """Layer2 loader."""

    def install(self, app):
        super(ZenPack, self).install(app)
        self._buildDeviceRelations()

    def _buildDeviceRelations(self):
        # TODO: figure out how this is usefull and remove if it is not.
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()

    def remove(self, app, leaveObjects=False):
        super(ZenPack, self).remove(app, leaveObjects)
        try:
            app.zport._delObject('macs_catalog')
        except AttributeError:
            pass # already deleted
