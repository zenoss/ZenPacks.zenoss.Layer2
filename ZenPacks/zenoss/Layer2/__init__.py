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
from Products.ZenModel.IpInterface import IpInterface
from Products.Zuul.interfaces.component import IIpInterfaceInfo
from Products.Zuul.infos.component.ipinterface import IpInterfaceInfo
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq

unused(Globals)


# Monkey patching IpInterface and add Layer2 properties
IpInterface.clientmac = ''
IpInterface.baseport = 0
IpInterface._properties = IpInterface._properties + (
    {'id':'clientmac', 'type':'string', 'mode':'w'},
    {'id':'baseport', 'type':'int', 'mode':'w'},
)

IIpInterfaceInfo.clientmac = schema.TextLine(
    title=u"Client MAC Address", group="Details", order=13)
IIpInterfaceInfo.baseport = schema.TextLine(
    title=u"Physical Port", group="Details", order=14)

IpInterfaceInfo.clientmac = ProxyProperty('clientmac')
IpInterfaceInfo.baseport = ProxyProperty('baseport')

def getClientsLinks(self):
    macs = self._object.clientmac
    if not macs:
        return ""

    links = []
    for mac in macs.split(', '):
        if not mac: continue
        is_found = False

        cat = ICatalogTool(self._object.dmd)
        brains = cat.search("Products.ZenModel.IpInterface.IpInterface")
        for brain in brains:
            obj = brain.getObject()
            if obj.macaddress == mac:
                links.append('<a href="{}">{}</a>'.format(
                    obj.getPrimaryUrlPath(), mac))
                is_found = True
                break

        if not is_found:
            links.append(mac)

    return ', '.join(links)

IpInterfaceInfo.getClientsLinks = getClientsLinks
