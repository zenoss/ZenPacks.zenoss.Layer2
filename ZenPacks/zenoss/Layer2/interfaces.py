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
from zope.interface import Attribute, Interface


class IVTEPProvider(Interface):

    """TODO"""

    name = Attribute("Provider name.")
    vteps = Attribute("Iterable of IVTEP instances.")


class IVTEP(Interface):

    """TODO"""

    ip_addresses = Attribute("Iterable of local IP addresses.")
    vnis = Attribute("Iterable of member VNIs.")
    peer_ips = Attribute("Iterable of peer IP addresses.")
