##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenRelations.ToManyRelationship import ToManyRelationshipBase
from Products.ZenRelations.ToOneRelationship import ToOneRelationship
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

from ZenPacks.zenoss.Impact.impactd.relations import ImpactEdge

from .macs_catalog import CatalogAPI


RP = 'ZenPacks.zenoss.Layer2'
AVAILABILITY = 'AVAILABILITY'
PERCENT = 'policyPercentageTrigger'
THRESHOLD = 'policyThresholdTrigger'


def guid(obj):
    return IGlobalIdentifier(obj).getGUID()


def edge(source, target):
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
    '''
    Adds upstream router(s) as dependency to device on impact graph
    '''
    def getEdges(self):
        cat = CatalogAPI(self._object.zport)
        for brain in cat.get_upstream_devices(dev.id):
            router = brain.getObject()
            yield edge(guid(router), self.guid())
