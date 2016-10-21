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
import re

from Products.Zuul.catalog.global_catalog import GlobalCatalog


def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)


def asip(val):
    """Convert a byte string to an IP address string.  """
    return '.'.join(str(ord(c)) for c in val)


def is_valid_macaddr802(value):
    if not isinstance(value, basestring):
        return False

    allowed = re.compile(r'^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$', re.IGNORECASE)
    if allowed.match(value):
        return True

    return False


def filterMacSet(existing, excluded):
    """Remove all excluded MACs from existing; returns set() of MAC addresses.
       * original and excluded are any iterables of MACs
       * 'excluded' are MAC addresses to be removed from existing
       * 'existing' is assumed to be a valid MAC iterable
    """
    existing_macs = set(x.lower() for x in existing)
    excluded_macs = set()
    for mac in excluded:
        # Ensure each element of excluded is valid MAC
        if is_valid_macaddr802(mac):
            excluded_macs.add(mac.lower())

    return existing_macs - excluded_macs


# Once upon a time this was defined here, but now is moved
# to the more proper place. Do not remove this unless you
# write proper migration of zport.connections_catalog or
# version 1.1.0 of Layer2 will be so old, that no one will
# have connections_catalog in their ZODB pickled from utils.
class ConnectionsCatalog(GlobalCatalog):
    pass
