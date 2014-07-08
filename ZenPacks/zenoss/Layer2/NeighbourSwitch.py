##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.component import adapts
from zope.interface import implements

from Products.ZenRelations.RelSchema import ToOne, ToManyCont

from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.Zuul.decorators import info
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.infos.component import ComponentInfo
from Products.Zuul.interfaces.component import IComponentInfo
from Products.Zuul.utils import ZuulMessageFactory as _t


class NeighbourSwitch(DeviceComponent, ManagedEntity):
    meta_type = portal_type = 'NeighbourSwitch'

    description = ''
    ip_address = ''
    device_port = ''
    native_vlan = ''
    location = ''

    _properties = ManagedEntity._properties + (
        {'id': 'description', 'type': 'string'},
        {'id': 'ip_address', 'type': 'string'},
        {'id': 'device_port', 'type': 'string'},
        {'id': 'native_vlan', 'type': 'string'},
        {'id': 'location', 'type': 'string'},
    )

    _relations = ManagedEntity._relations + (
        ('switch', ToOne(
            ToManyCont,
            'Products.ZenModel.Device.Device',
            'neighbour_switches')
        ),
    )

    # Meta-data: Zope object views and actions
    factory_type_information = ({
        'actions': ({
            'id': 'perfConf',
            'name': 'Template',
            'action': 'objTemplates',
            'permissions': (ZEN_CHANGE_DEVICE,),
            },),
        },)

    def device(self):
        return self.switch()


class INeighbourSwitchInfo(IComponentInfo):
    '''
    API Info interface for NeighbourSwitch.
    '''

    description = schema.TextLine(title=_t(u'Description'))
    ip_address = schema.TextLine(title=_t(u'IP Address'))
    device_port = schema.TextLine(title=_t(u'Device Port'))
    native_vlan = schema.TextLine(title=_t(u'Native VLAN'))
    location = schema.TextLine(title=_t(u'Physical Location'))


class NeighbourSwitchInfo(ComponentInfo):
    ''' API Info adapter factory for NeighbourSwitch '''

    implements(INeighbourSwitchInfo)
    adapts(NeighbourSwitch)

    #version = ProxyProperty('version')
    description = ProxyProperty('description')
    ip_address = ProxyProperty('ip_address')
    device_port = ProxyProperty('device_port')
    native_vlan = ProxyProperty('native_vlan')
    location = ProxyProperty('location')
