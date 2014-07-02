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
log = logging.getLogger('zen.Layer2')

import Globals

from Products.ZenUtils.Utils import unused
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.ZenModel.Device import Device
from Products.ZenModel.IpInterface import IpInterface
from Products.Zuul.interfaces.component import IIpInterfaceInfo
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq

import ZenPacks.zenoss.Layer2.patches

unused(Globals)


# -- IP Interfaces overrides --------------------------------------------------

# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmacs = []
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id':'clientmacs', 'type':'string', 'mode':'w'},
    {'id':'baseport', 'type':'int', 'mode':'w'},
)

IIpInterfaceInfo.clientmacs = schema.TextLine(
    title=u"Clients MAC Addresses", group="Details", order=13)
IIpInterfaceInfo.baseport = schema.TextLine(
    title=u"Physical Port", group="Details", order=14)

# -- UI overrides goes here --------------------------------------------------

IpInterfaceInfo.clientmacs = ProxyProperty('clientmacs')
IpInterfaceInfo.baseport = ProxyProperty('baseport')
