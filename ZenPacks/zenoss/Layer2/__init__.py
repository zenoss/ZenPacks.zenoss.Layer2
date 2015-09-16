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

import socket
import struct

import Globals

from Products.ZenUtils.Utils import unused
from Products.ZenModel.ZenPack import ZenPackBase
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory

import ZenPacks.zenoss.Layer2.patches

unused(Globals)

log = logging.getLogger('zen.Layer2')


setzPropertyCategory('zZenossGateway', 'Misc')


class ZenPack(ZenPackBase):
    """ Layer2 zenpack loader """

    packZProperties = [
        ('zZenossGateway', '', 'string'),
    ]

    def install(self, app):
        super(ZenPack, self).install(app)
        self._buildDeviceRelations()
        self._getDefaultGateway(app.zport.dmd)

    def _buildDeviceRelations(self):
        # TODO: figure out how this is usefull and remove if it is not.
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()

    def _getDefaultGateway(self, dmd):
        """
        Try to determine zZenossGateway value from /proc/net/route information
        """

        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                # Checks gateway value and flag if record actual
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue

                # Converts packed value into IP address
                val = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                if not dmd.Devices.zZenossGateway:
                    log.info("Setting zZenossGateway value to {}".format(val))
                    dmd.Devices.setZenProperty('zZenossGateway', val)

    def remove(self, app, leaveObjects=False):
        super(ZenPack, self).remove(app, leaveObjects)
        try:
            app.zport._delObject('macs_catalog')
        except AttributeError:
            pass  # already deleted
