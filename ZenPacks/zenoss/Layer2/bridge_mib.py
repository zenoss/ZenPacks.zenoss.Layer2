# ftp://ftp.cisco.com/pub/mibs/v1/BRIDGE-MIB.my
dot1dTpFdbTable = '1.3.6.1.2.1.17.4.3'
#     "A table that contains information about unicast
#     entries for which the bridge has forwarding and/or
#     filtering information. This information is used
#     by the transparent bridging function in
#     determining how to propagate a received frame."

dot1dTpFdbEntry = dot1dTpFdbTable + '.1'
#     "Information about a specific unicast MAC address
#     for which the bridge has some forwarding and/or
#     filtering information."

dot1dTpFdbAddress = dot1dTpFdbEntry + '.1'
#     "A unicast MAC address for which the bridge has
#     forwarding and/or filtering information."

dot1dTpFdbPort = dot1dTpFdbEntry + '.2'
#     "Either the value '0', or the port number of the
#     port on which a frame having a source address
#     equal to the value of the corresponding instance
#     of dot1dTpFdbAddress has been seen. A value of
#     '0' indicates that the port number has not been
#     learned but that the bridge does have some
#     forwarding/filtering information about this
#     address (e.g. in the dot1dStaticTable).
#     Implementors are encouraged to assign the port
#     value to this object whenever it is learned even
#     for addresses for which the corresponding value of
#     dot1dTpFdbStatus is not learned(3)."

dot1dTpFdbStatus = dot1dTpFdbEntry + '.3'
# 	The status of this entry. The meanings of the values are:
#   one of the attributes of ForwardingEntryStatus class


class ForwardingEntryStatus(object):
    other = 1    # none of the following. This would
                 # include the case where some other
                 # MIB object (not the corresponding
                 # instance of dot1dTpFdbPort, nor an
                 # entry in the dot1dStaticTable) is
                 # being used to determine if and how
                 # frames addressed to the value of
                 # the corresponding instance of
                 # dot1dTpFdbAddress are being
                 # forwarded.

    invalid = 2  # this entry is not longer valid
                 # (e.g., it was learned but has since
                 # aged-out), but has not yet been
                 # flushed from the table.

    learned = 3  # the value of the corresponding
                 # instance of dot1dTpFdbPort was
                 # learned, and is being used.

    self = 4     # the value of the corresponding
                 # instance of dot1dTpFdbAddress
                 # represents one of the bridge's
                 # addresses. The corresponding
                 # instance of dot1dTpFdbPort
                 # indicates which of the bridge's
                 # ports has this address.

    mgmt = 5     # the value of the corresponding
                 # instance of dot1dTpFdbAddress is
                 # also the value of an existing
                 # instance of dot1dStaticAddress.

dot1dBasePortEntry = '1.3.6.1.2.1.17.1.4.1'
#     "A list of information for each port of the
#     bridge."

dot1dBasePort = dot1dBasePortEntry + '.1'
#  	"The port number of the port for which this entry
#     contains bridge management information."

dot1dBasePortIfIndex = dot1dBasePortEntry + '.2'
#     "The value of the instance of the ifIndex object,
#     defined in MIB-II, for the interface corresponding
#     to this port."
