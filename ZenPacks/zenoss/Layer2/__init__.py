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

        self.post_install(app)

    def post_install(self, app):
        """Perform work that can be done after normal ZenPack install."""
        dc = app.zport.dmd.Devices.Network
        dc.bindTemplates(dc.zDeviceTemplates + ['Layer2Info'])
