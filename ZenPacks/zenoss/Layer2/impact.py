##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, 2015 all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenModel.IpInterface import IpInterface
from Products.ZenModel.Device import Device
from Products.ZenRelations.ToManyRelationship import ToManyRelationshipBase
from Products.ZenRelations.ToOneRelationship import ToOneRelationship
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier

from ZenPacks.zenoss.Impact.impactd.relations import ImpactEdge

from .connections_catalog import CatalogAPI

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


class ImpactCatalogAPI(CatalogAPI):

    def getNlayer2(self, entity_id, method, N):
        ''' Yield objects that are N hops (forward or backward) from given '''
        for id in self.get_bfs_connected(
            entity_id=entity_id,
            layers=['layer2'],
            method=method,
            depth=N
        ):
            if id == entity_id or id.startswith('!'):
                continue
            obj = self.get_link(id) or self.get_obj(id)
            if obj:
                yield obj

    def impacts(self, entity_id, depth):
        for obj in self.getNlayer2(
            entity_id, self.get_directly_connected, depth
        ):
            yield obj

    def impacted_by(self, entity_id, depth):
        for obj in self.getNlayer2(
            entity_id, self.get_reverse_connected, depth
        ):
            yield obj


class DeviceRelationsProvider(BaseRelationsProvider):
    ''' Adds upstream router(s) as dependency to device on impact graph '''
    def getEdges(self):
        cat = ImpactCatalogAPI(self._object.zport)
        try:
            this_id = self._object.getPrimaryUrlPath()

            for obj in cat.impacts(this_id, 3):
                yield edge(self.guid(), guid(obj))

            for obj in cat.impacted_by(this_id, 3):
                yield edge(guid(obj), self.guid())

            if self._object.getPrimaryUrlPath().startswith(
                '/zport/dmd/Devices/Network/'
            ):
                # Yield interfaces
                for obj in cat.impacted_by(this_id, 2):
                    if isinstance(obj.aq_base, IpInterface):
                        yield edge(guid(obj), self.guid())

        except Exception as e:
            log.exception(e)


class InterfaceRelationsProvider(BaseRelationsProvider):
    ''' Adds client devices as dependencies for interfaces '''

    def getEdges(self):
        cat = ImpactCatalogAPI(self._object.zport)
        try:
            this_id = self._object.getPrimaryUrlPath()
            node_id = cat.get_node_by_link(this_id)

            for obj in cat.impacts(node_id, 2):
                if isinstance(obj.aq_base, Device):
                    yield edge(self.guid(), guid(obj))

        except Exception as e:
            log.exception(e)
