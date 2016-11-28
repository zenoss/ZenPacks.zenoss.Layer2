##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from . import connections

# constants
MAX_LINKS = 100


class DeviceLinkProvider(object):
    '''
    Provides a links to the client devices connected to this device
    '''
    def __init__(self, device):
        self.device = device

    def getExpandedLinks(self):
        links = set()
        links_suffix = []

        for neighbor in connections.get_layer2_neighbor_devices(self.device):
            if not connections.is_switch(neighbor):
                # We're only providing links to switches.
                continue

            # The list of links might be huge, limit the output.
            if len(links) > MAX_LINKS:
                links_suffix.append(
                    '(list truncated to {} switches)'.format(MAX_LINKS))

                break

            links.add(
                'Switch: <a href="{}">{}</a>'.format(
                    neighbor.getPrimaryUrlPath(),
                    neighbor.titleOrId()))

        return ['<br />'] + sorted(links) + links_suffix
