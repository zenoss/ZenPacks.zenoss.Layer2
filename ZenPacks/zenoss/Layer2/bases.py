##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""TODO"""


# Zope Imports
from zope.component import adapts
from zope.interface import implements

# Zenoss Imports
from Products.ZenModel.ZenModelBase import ZenModelBase

# ZenPack Imports
from .interfaces import IVTEP, IVTEPProvider


class VTEPBase(object):

    """TODO"""

    implements(IVTEP)

    def __init__(self, context):
        self.context = context


class VTEPProviderBase(object):

    """TODO"""

    implements(IVTEPProvider)
    adapts(ZenModelBase)

    def __init__(self, context):
        self.context = context
