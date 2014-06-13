##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from zope.event import notify
from zope.component import adapter
from zope.container.interfaces import IObjectAddedEvent, IObjectMovedEvent
from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.Zuul.catalog.interfaces import IGloballyIndexed
from Products.ZenUtils.guid.interfaces import IGloballyIdentifiable
from Products.Zuul.catalog.interfaces import IIndexingEvent


# @adapter(IGloballyIndexed, IObjectAddedEvent)
# def onObjectAdded(ob, event):
#     """
#     Simple subscriber that fires the indexing event for all
#     indices.
#     """
#     print "=" * 80
#     print "EVENT!"
#     print "=" * 80


# @adapter(IGloballyIdentifiable, IIndexingEvent)
# def publishModified(ob, event):
#     print "=" * 80
#     print "EVENT #2!"
#     print "=" * 80
