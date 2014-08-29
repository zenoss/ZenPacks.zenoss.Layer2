##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2007, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################

def asmac(val):
    """Convert a byte string to a MAC address string.  """
    return ':'.join('%02X' % ord(c) for c in val)
