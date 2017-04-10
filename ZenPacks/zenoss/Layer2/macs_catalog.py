##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Dummy CatalogAPI for backward compatibility for some ZenPacks rely on it."""

import logging
log = logging.getLogger("zen.Layer2")


class CatalogAPI(object):

    """Dummy CatalogAPI which returns empty sets."""

    def __init__(self, dmd):
        log.warning('Used deprecated CatalogAPI')

    def get_if_upstream_devices(self, macs):
        return []

    def get_if_client_devices(self, macs):
        return []
