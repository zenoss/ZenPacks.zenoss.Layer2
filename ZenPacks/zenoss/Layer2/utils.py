##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
    Miscelanous utilities.
'''


def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)


def asip(val):
    """Convert a byte string to an IP address string.  """
    return '.'.join(str(ord(c)) for c in val)


# Once upon a time this was defined here, but now is moved
# to the more proper place. Do not remove this unless you
# write proper migration of zport.connections_catalog or
# version 1.1.0 of Layer2 will be so old, that no one will
# have connections_catalog in their ZODB pickled from utils.
from .connections_catalog import ConnectionsCatalog
