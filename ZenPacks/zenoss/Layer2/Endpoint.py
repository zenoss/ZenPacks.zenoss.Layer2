##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from Products.ZenModel.Device import Device

class Endpoint(Device):
    meta_type = portal_type = 'Layer2Endpoint'

    def get_update_network_map(self):
        return False

    def set_update_network_map(self, arg):
        with open('/home/zenoss/out', 'w') as f:
            f.write('set_update_network_map triggered %s\n' % arg)
        return True
