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
from zope.component import subscribers

# Zenoss Imports
from Products.Zuul.facades import ZuulFacade

# ZenPack Imports
from .interfaces import IVTEPProvider


class VXLANFacade(ZuulFacade):

    """TODO"""

    def getVTEPs(self):
        """Return iterable of IVTEP instances for context."""
        for provider in subscribers([self.context], IVTEPProvider):
            for vtep in provider.vteps:
                yield vtep
