##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
In this module DeviceRelationsProvider.getEdges defines impact relationships.

Network devices impact devices (usually servers) three links down
(3, to skip two interfaces) in graph throught layer2 layer, but
only if they are not also network devices, because this could create
circular impacts.

In the same way, devices are impacted by network devices, if they have that
network devices three links upstream in their network map.
'''

from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

from ZenPacks.zenoss.Impact.impactd.relations import ImpactEdge

from . import connections

import logging
log = logging.getLogger('zen.Layer2')


RP = 'ZenPacks.zenoss.Layer2'
AVAILABILITY = 'AVAILABILITY'
PERCENT = 'policyPercentageTrigger'
THRESHOLD = 'policyThresholdTrigger'


def guid(obj):
    return IGlobalIdentifier(obj).getGUID()


def edge(source, target):
    assert isinstance(source, basestring)
    assert isinstance(target, basestring)
    return ImpactEdge(source, target, RP)


class BaseRelationsProvider(object):
    '''
    Basic class for impact relations
    '''
    relationship_provider = RP

    impact_relationships = None
    impacted_by_relationships = None

    def __init__(self, adapted):
        self._object = adapted

    def belongsInImpactGraph(self):
        return True

    def guid(self):
        if not hasattr(self, '_guid'):
            self._guid = guid(self._object)

        return self._guid


class DeviceRelationsProvider(BaseRelationsProvider):
    ''' Adds upstream router(s) as dependency to device on impact graph '''
    def getEdges(self):
        device = self._object
        try:
            my_guid = self.guid()
            neighbors = connections.get_layer2_neighbor_devices(device)

            if connections.is_switch(device):
                for neighbor in neighbors:
                    if not connections.is_switch(neighbor):
                        yield edge(my_guid, guid(neighbor))
            else:
                for neighbor in neighbors:
                    if connections.is_switch(neighbor):
                        yield edge(guid(neighbor), my_guid)

        except Exception as e:
            log.exception(e)
