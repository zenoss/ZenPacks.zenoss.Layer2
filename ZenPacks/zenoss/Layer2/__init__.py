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
LOG = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenModel.Device import Device
from Products.ZenModel.PerformanceConf import PerformanceConf
from Products.ZenUtils.Utils import unused
from Products.ZenModel.ZenPack import ZenPackBase
from Products.ZenRelations.RelSchema import ToManyCont, ToOne
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory
from Products.Zuul.interfaces import ICatalogTool

import ZenPacks.zenoss.Layer2.patches

unused(Globals)

ZPROPERTY_CATEGORY = 'Layer 2'

setzPropertyCategory('zL2SuppressIfDeviceDown', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2SuppressIfPathsDown', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2PotentialRootCause', ZPROPERTY_CATEGORY)
setzPropertyCategory('zL2Gateways', ZPROPERTY_CATEGORY)
setzPropertyCategory('zZenossGateway', ZPROPERTY_CATEGORY)
setzPropertyCategory('zLocalMacAddresses', ZPROPERTY_CATEGORY)

# Relationships to patch onto Device.
DEVICE_RELATIONS = {
    'neighbor_switches': 'ZenPacks.zenoss.Layer2.NeighborSwitch',
    }

# Increase this number if more custom relationships are added.
RELATIONS_REVISION = 1
RELATIONS_REVISION_ATTR = "layer2_relations_revision"


class ZenPack(ZenPackBase):
    """ Layer2 zenpack loader """

    packZProperties = [
        ('zL2SuppressIfDeviceDown', False, 'boolean'),
        ('zL2SuppressIfPathsDown', False, 'boolean'),
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
        """Install ZenPack.

        This method is called when the ZenPack is installed or upgraded.

        Overrides Products.ZenModel.ZenPack.ZenPack.

        """
        super(ZenPack, self).install(app)
        self.install_relationships()

    def install_relationships(self):
        if getattr(self.dmd, RELATIONS_REVISION_ATTR, 0) >= RELATIONS_REVISION:
            # Avoid building relationships that already exist.
            return

        LOG.info('Adding relationships to existing devices')
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()

        setattr(self.dmd, RELATIONS_REVISION_ATTR, RELATIONS_REVISION)

    def remove(self, app, leaveObjects=False):
        """Remove ZenPack.

        This method is called when the ZenPack is upgraded or removed.
        The leaveObjects argument is True during upgrade, and False
        during removal.

        Overrides Products.ZenModel.ZenPack.ZenPack.

        """
        if not leaveObjects:
            setattr(self.dmd, RELATIONS_REVISION_ATTR, 0)
            self.remove_relationships()
            self.remove_catalogs()
            self.remove_properties()

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def remove_relationships(self):
        """Remove our relationship schema and instances from all devices."""
        LOG.info('Removing relationships from devices')
        for d in self.dmd.Devices.getSubDevicesGen():
            remove_relationships(d.__class__)
            d.buildRelations()

    def remove_catalogs(self):
        """Remove our catalogs."""
        try:
            self.zport._delObject('macs_catalog')
        except AttributeError:
            # already deleted
            pass

    def remove_properties(self):
        """Remove properties added to _properties."""
        for result in ICatalogTool(self.dmd.Monitors).search(PerformanceConf):
            try:
                collector = result.getObject()
            except Exception:
                continue

            # Skip collectors lacking an instance value of _properties.
            if collector._properties is collector.__class__._properties:
                continue

            # Remove l2_gateways property from all collectors (ZPS-2581)
            collector._properties = tuple(
                x for x in collector._properties
                if x.get("id") != "l2_gateways")


def add_relationships(cls):
    """Add our relationships to cls._relations."""
    our_relnames = set(DEVICE_RELATIONS)
    existing_relnames = {x[0] for x in cls._relations}
    new_reltuples = tuple(
        (relname, ToManyCont(ToOne, DEVICE_RELATIONS[relname], 'switch'))
        for relname in our_relnames.difference(existing_relnames))

    if new_reltuples:
        cls._relations += new_reltuples


def remove_relationships(cls):
    """Remove our relationships from cls._relations."""
    our_relnames = set(DEVICE_RELATIONS)
    existing_relnames = {x[0] for x in cls._relations}
    if our_relnames.intersection(existing_relnames):    
        cls._relations = tuple(
            (relname, relspec) for relname, relspec in cls._relations
            if relname not in our_relnames)


# Patch Device._relations with our relationships.
add_relationships(Device)
