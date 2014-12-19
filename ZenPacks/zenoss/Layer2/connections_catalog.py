##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.Layer2')

from ZenPacks.zenoss.Layer2.utils import BaseCatalogAPI

from .connections_provider import IConnection


class CatalogAPI(BaseCatalogAPI):
    name = 'connections_catalog'
    fields = dict(
        entity_id='str',
        connected_to='list',
        layers='list'
    )

    @staticmethod
    def validate_connection(connection):
        connection = IConnection(connection)
        IConnection.validateInvariants(connection)
        return connection

    def add_connection(self, connection):
        ''' Add a connection to a catalog '''
        connection = self.validate_connection(connection)

        self.catalog.catalog_object(connection, uid=connection.hash)
        log.debug('%s added to %s' % (connection, self.name))

    def remove_connection(self, connection):
        self.catalog.uncatalog_object(connection.hash)
        log.debug('%s removed from %s' % (connection, self.name))
