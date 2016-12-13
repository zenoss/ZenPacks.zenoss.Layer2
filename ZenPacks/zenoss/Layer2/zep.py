##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Event (ZEP) plugins."""

from . import suppression


class Layer2PostEventPlugin(object):

    """IPostEventPlugin utility.

    This plugin attempts to suppress events in the following situations:

    * The event is non-ping event from a device that is ping down.
    * The event is a ping event resulting from a network outage.

    The following zProperties control what suppression may occur.

    * zL2SuppressIfDeviceDown
    * zL2SuppressIfPathsDown
    * zL2PotentialRootCause
    * zL2Gateways

    Events identified for suppression will have their eventState field
    set to 2 (suppressed), and their rootCases detail field set to a
    comma-separated list of the device ids that are the root causes for
    the suppression.

    """

    @staticmethod
    def apply(evtproxy, dmd):
        """Process event (evtproxy) using dmd as context."""
        suppression.get_suppressor(dmd).process_event(evtproxy)
