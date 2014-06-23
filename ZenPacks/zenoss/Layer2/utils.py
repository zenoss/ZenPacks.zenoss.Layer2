##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2007, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################

import struct

def asmac(val):
    """Convert a byte string to a MAC address string.
    """
    mac = []
    for char in val:
        tmp = struct.unpack('B', char)[0]
        tmp =  str(hex(tmp))[2:]
        if len(tmp) == 1: tmp = '0' + tmp
        mac.append(tmp)
    return ":".join(mac).upper()
