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

import Globals

from Products.ZenUtils.Utils import unused
from Products.ZenModel.ZenPack import ZenPackBase
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory

import ZenPacks.zenoss.Layer2.patches

unused(Globals)

ZPROPERTY_CATEGORY = 'Layer 2'

setzPropertyCategory('zL2SuppressIfDeviceDown', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2SuppressIfPathsDown', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2PotentialRootCause', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2Gateways', ZPROPERTY_CATEGORY)
setzPropertyCategory('zZenossGateway', ZPROPERTY_CATEGORY)
setzPropertyCategory('zLocalMacAddresses', ZPROPERTY_CATEGORY)


class ZenPack(ZenPackBase):
    """ Layer2 zenpack loader """

    packZProperties = [
        ('zL2SuppressIfDeviceDown', True, 'boolean'),
        ('zL2SuppressIfPathsDown', True, 'boolean'),
        ('zL2PotentialRootCause', True, 'boolean'),
        ('zL2Gateways', [], 'lines'),
        ('zZenossGateway', '', 'string'),
        ('zLocalMacAddresses', ['00:00:00:00:00:00'], 'lines'),
        ]

    packZProperties_data = {
        'zL2SuppressIfDeviceDown': {
            'category': ZPROPERTY_CATEGORY,
            'label': 'Event Suppression: Device Down',
            'description': 'Suppresses non-ping events when it is down.',
            'type': 'boolean',
            },

        'zL2SuppressIfPathsDown': {
            'category': ZPROPERTY_CATEGORY,
            'label': 'Event Suppression: All Paths to Gateways Down',
            'description': 'Suppresses ping events when all paths to all gateways are down.',
            'type': 'boolean',
            },

        'zL2PotentialRootCause': {
            'category': ZPROPERTY_CATEGORY,
            'label': 'Event Suppression: Can Device be a Root Cause?',
            'description': 'Set to False only for endpoints like hosts.',
            },

        'zL2Gateways': {
            'category': ZPROPERTY_CATEGORY,
            'label': 'Device Gateways',
            'description': 'Gateways for device. Must be Zenoss device IDs.',
            'type': 'lines',
            },

        'zZenossGateway': {
            'category': ZPROPERTY_CATEGORY,
            'label': '[DEPRECATED] Use zL2Gateways',
            'description': '[DEPRECATED] Use zL2Gateways instead to support multiple gateways per device.',
            'type': 'string',
            },

        'zLocalMacAddresses': {
            'category': ZPROPERTY_CATEGORY,
            'label': 'Local MAC Addresses',
            'description': 'Suppress these MAC addresses when mapping interfaces.',
            'type': 'string',
            },
        }

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
            pass  # already deleted
