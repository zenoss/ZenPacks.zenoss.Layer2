##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import Globals  # NOQA: imported for side-effects

import collections
import contextlib
import copy
import itertools
import logging
import re
import socket
import struct

from zope.event import notify

from Products.Five import zcml

from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.events import pausedAndOptimizedIndexing
from Products.Zuul.catalog.events import IndexingEvent

from zenoss.protocols.protobufs.zep_pb2 import STATUS_SUPPRESSED

import ZenPacks.zenoss.Layer2
from ZenPacks.zenoss.Layer2 import connections
from ZenPacks.zenoss.Layer2 import progresslog
from ZenPacks.zenoss.Layer2 import suppression
from ZenPacks.zenoss.Layer2.zep import Layer2PostEventPlugin

TEST_TOPOLOGY_YUML = """
// Core Interconnect
[core-a]-[core-b]
//
// Row 1: Fully Redundant
[core-a]-[row-1a]
[core-b]-[row-1a]
[core-a]-[row-1b]
[core-b]-[row-1b]
[row-1a]-[row-1b]
[row-1a]-[rack-1-1a]
[row-1b]-[rack-1-1a]
[row-1a]-[rack-1-1b]
[row-1b]-[rack-1-1b]
[rack-1-1a]-[rack-1-1b]
[rack-1-1a]-[host-1-1-1]
[rack-1-1b]-[host-1-1-1]
[rack-1-1a]-[host-1-1-2]
[rack-1-1b]-[host-1-1-2]
[host-1-1-3]
[row-1a]-[rack-1-2a]
[row-1b]-[rack-1-2a]
[row-1a]-[rack-1-2b]
[row-1b]-[rack-1-2b]
[rack-1-2a]-[rack-1-2b]
[rack-1-2a]-[host-1-2-1]
[rack-1-2b]-[host-1-2-1]
//
// Row 2: No Redundancy
[core-a]-[row-2a]
[row-2a]-[rack-2-1a]
[rack-2-1a]-[host-2-1-1]
//
// Row 3: No Redundancy - Rack Disconnected from Host
[core-b]-[row-3a]
[row-3a]-[rack-3-1a]
[rack-3-1a]-[host-3-1-1]
//
// Row 4: Fully Redundant - Row Disconnected from Core
[row-4a]-[row-4b]
[row-4a]-[rack-4-1a]
[row-4b]-[rack-4-1a]
[row-4a]-[rack-4-1b]
[row-4b]-[rack-4-1b]
[rack-4-1a]-[rack-4-1b]
[rack-4-1a]-[host-4-1-1]
[rack-4-1b]-[host-4-1-1]
"""


SCENARIOS = {

    # --- 1st Hop Suppression (No Gateways) ----------------------------------

    "1st.) 0/0": {
        "device": "host-1-1-3",  # device has no upstreams
        "down": ["rack-1-1a", "rack-1-1b"],
        "suppressed": False,
        },

    "1st.) 0/1": {
        "device": "host-3-1-1",
        "down": [],
        "suppressed": False,
        },

    "1st.) 1/1": {
        "device": "host-3-1-1",
        "down": ["rack-3-1a"],
        "suppressed": True,
        "root_causes": "rack-3-1a",
        },

    "1st.) 0/2": {
        "device": "host-1-1-1",
        "down": [],
        "suppressed": False,
        },

    "1st.) 1/2": {
        "device": "host-1-1-1",
        "down": ["rack-1-1a"],
        "suppressed": False,
        },

    "1st.) 2/2": {
        "device": "host-1-1-1",
        "down": ["rack-1-1a", "rack-1-1b"],
        "suppressed": True,
        "root_causes": "rack-1-1a,rack-1-1b",
        },

    "1st.) 0/1 switch": {
        "device": "rack-3-1a",
        "down": [],
        "suppressed": False,
        },

    "1st.) 1/1 switch": {
        "device": "rack-3-1a",
        "down": ["row-3a"],
        "suppressed": True,
        "root_causes": "row-3a",
        },

    "1st.) 0/2 switch": {
        "device": "rack-1-1a",
        "down": [],
        "suppressed": False,
        },

    "1st.) 1/2 switch": {
        "device": "rack-1-1a",
        "down": ["row-1a"],
        "suppressed": False,
        },

    "1st.) 2/2 switch": {
        "device": "rack-1-1a",
        "down": ["row-1a", "row-1b", "rack-1-1b"],
        "suppressed": True,
        "root_causes": "rack-1-1b,row-1a,row-1b",
        },

    # -- Multi-Hop - Gateway(s) @ 2nd Hop ------------------------------------

    "2hop) 0/1": {
        "device": "host-3-1-1",
        "gateways": ["row-3a"],
        "down": [],
        "suppressed": False,
        },

    "2hop) 1/1 @1st": {
        "device": "host-3-1-1",
        "gateways": ["row-3a"],
        "down": ["rack-3-1a"],
        "suppressed": True,
        "root_causes": "rack-3-1a",
        },

    "2hop) 1/1 @2nd": {
        "device": "host-3-1-1",
        "gateways": ["row-3a"],
        "down": ["row-3a"],
        "suppressed": True,
        "root_causes": "row-3a",
        },

    "2hop) 0/2": {
        "device": "host-1-1-1",
        "gateways": ["row-1a", "row-1b"],
        "down": [],
        "suppressed": False,
        },

    "2hop) 1/2 @1st": {
        "device": "host-1-1-1",
        "gateways": ["row-1a", "row-1b"],
        "down": ["rack-1-1a"],
        "suppressed": False,
        },

    "2hop) 2/2 @1st": {
        "device": "host-1-1-1",
        "gateways": ["row-1a", "row-1b"],
        "down": ["rack-1-1a", "rack-1-1b"],
        "suppressed": True,
        "root_causes": "rack-1-1a,rack-1-1b",
        },

    "2hop) 1/2 @2nd": {
        "device": "host-1-1-1",
        "gateways": ["row-1a", "row-1b"],
        "down": ["row-1a"],
        "suppressed": False,
        },

    "2hop) 2/2 @2nd": {
        "device": "host-1-1-1",
        "gateways": ["row-1a", "row-1b"],
        "down": ["row-1a", "row-1b"],
        "suppressed": True,
        "root_causes": "row-1a,row-1b",
        },

    # -- Multi-Hop - Gateway(s) @ 3rd Hop ------------------------------------

    "3hop) 0/2": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": [],
        "suppressed": False,
        },

    "3hop) 1/2 @1st": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["rack-1-1a"],
        "suppressed": False,
        },

    "3hop) 2/2 @1st": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["rack-1-1a", "rack-1-1b"],
        "suppressed": True,
        "root_causes": "rack-1-1a,rack-1-1b",
        },

    "3hop) 1/2 @2nd": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["row-1a"],
        "suppressed": False,
        },

    "3hop) 2/2 @2nd": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["row-1a", "row-1b"],
        "suppressed": True,
        "root_causes": "row-1a,row-1b",
        },

    "3hop) 1/2 @3rd": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["core-a"],
        "suppressed": False,
        },

    "3hop) 2/2 @3rd": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["core-a", "core-b"],
        "suppressed": True,
        "root_causes": "core-a,core-b",
        },

    # -- Multi-Hop Special Cases ---------------------------------------------

    "3hop) 2/2 @2nd (no path to gateways)": {
        "device": "host-4-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["row-4a", "row-4b"],
        "suppressed": False,
        },

    "3hop) 2/2 @2nd (extra failure toward gateway)": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["core-a", "row-1a", "row-1b"],
        "suppressed": True,
        "root_causes": "core-a,row-1a,row-1b",
        },

    "3hop) 2/2 @2nd (extra failure toward host)": {
        "device": "host-1-1-1",
        "gateways": ["core-a", "core-b"],
        "down": ["rack-1-1a", "row-1a", "row-1b"],
        "suppressed": True,
        "root_causes": "row-1a,row-1b",
        },

    "self) 2/2 @0th (device is one of failed gateways)": {
        "device": "core-a",
        "gateways": ["core-a", "core-b"],
        "down": ["core-a", "core-b"],
        "suppressed": False,
        },
    }


class TestSuppression(BaseTestCase):
    def afterSetUp(self):
        super(TestSuppression, self).afterSetUp()

        # Get our necessary adapters registered.
        zcml.load_config("configure.zcml", ZenPacks.zenoss.Layer2)

        # Configure zProperties.
        self.dmd.Devices._setProperty("zL2SuppressIfDeviceDown", True, "boolean")
        self.dmd.Devices._setProperty("zL2SuppressIfPathsDown", True, "boolean")
        self.dmd.Devices._setProperty("zL2PotentialRootCause", True, "boolean")
        self.dmd.Devices._setProperty("zL2Gateways", [], "lines")

        # Clear connections database.
        connections.clear()

        # Create devices.
        Stresser(self.dmd).from_yuml(TEST_TOPOLOGY_YUML)

    def _assert_suppression(self, event, suppressed, root_causes):
        """Assert that event has been correctly suppressed."""
        event_state = getattr(event, "eventState", None)
        found_causes = getattr(event, "rootCauses", None)

        if suppressed:
            assert event_state == STATUS_SUPPRESSED, "not suppressed"
            assert found_causes == root_causes, (
                "rootCauses is {!r} instead of {!r}".format(
                    found_causes,
                    root_causes))
        else:
            assert event_state != STATUS_SUPPRESSED, "incorrectly suppressed"
            assert found_causes is None, (
                "rootCauses incorrectly set to {!r}".format(
                    found_causes,
                    event.eventClass))

    def test_l2_scenarios(self):
        suppressor = suppression.get_suppressor(self.dmd)

        for label, data in SCENARIOS.items():
            try:
                d = self.dmd.Devices.findDeviceByIdExact(data["device"])
                d.setZenProperty("zL2Gateways", data.get("gateways", []))

                def mkevent():
                    return MockEvent(
                        device=data["device"],
                        eventClass="/Status/Ping",
                        severity=5)

                suppressor.clear_caches()

                with downed_devices(data["down"]):
                    # Test twice to make sure caching doesn't result in
                    # a wrong outcome.
                    for _ in range(2):
                        event = mkevent()
                        Layer2PostEventPlugin.apply(event, self.dmd)
                        self._assert_suppression(
                            event,
                            suppressed=data["suppressed"],
                            root_causes=data.get("root_causes"))

            except AssertionError as e:
                SCENARIOS[label]["failure"] = str(e)

        # Consolidate and raise failures all together.
        failures = {
            k: v["failure"]
            for k, v in SCENARIOS.items()
            if "failure" in v}

        if failures:
            self.fail(
                "Suppression failures follow:\n{}".format(
                    "\n".join(
                        "  {}: {}".format(k, v)
                        for k, v in sorted(failures.items()))))

    def test_non_ping_event_on_down_device(self):
        suppressor = suppression.get_suppressor(self.dmd)
        suppressor.clear_caches()

        p_event = MockEvent(device="host-1-1-1", eventClass="/Status/Ping", severity=5)
        Layer2PostEventPlugin.apply(p_event, self.dmd)
        self._assert_suppression(p_event, suppressed=False, root_causes=None)

        np_event = MockEvent(device="host-1-1-1", eventClass="/Perf", severity=3)
        Layer2PostEventPlugin.apply(np_event, self.dmd)
        self._assert_suppression(np_event, suppressed=True, root_causes="host-1-1-1")

    def test_non_ping_event_on_up_device(self):
        suppressor = suppression.get_suppressor(self.dmd)
        suppressor.clear_caches()

        np_event = MockEvent(device="host-1-1-1", eventClass="/Perf", severity=3)
        Layer2PostEventPlugin.apply(np_event, self.dmd)
        self._assert_suppression(np_event, suppressed=False, root_causes="host-1-1-1")


class MockEvent(object):
    def __init__(self, **kwargs):
        self.agent = "stresser"
        self.monitor = "localhost"
        self.summary = "defaul summary"
        self.component = ""
        for k, v in kwargs.items():
            setattr(self, k, v)


@contextlib.contextmanager
def downed_devices(devices):
    original_get_status = copy.copy(connections.get_status)

    def patched_get_status(dmd, node):
        for device in devices:
            if node.endswith("/{}".format(device)):
                return False

        return True

    # Patch get_status to return False for devices.
    connections.get_status = patched_get_status

    # Execute context manager's body.
    try:
        yield
    finally:
        # Unpatch get_status.
        connections.get_status = original_get_status


# -- Performance Testing -----------------------------------------------------

class Stresser(object):
    def __init__(self, dmd, starting_mac=None, starting_ip=None):
        self.dmd = dmd
        self.log = logging.getLogger("zen.Layer2.stresser")
        self.macs = collections.defaultdict(dict)
        self.mac_counter = int_from_mac(starting_mac or "01:00:00:00:00:00")
        self.ips = {}
        self.ip_counter = int_from_ip(starting_ip or "127.1.0.0")

    def next_mac(self):
        self.mac_counter += 1
        inhex = "{:012x}".format(self.mac_counter)
        return ':'.join(s.encode('hex') for s in inhex.decode('hex'))

    def mac_pair(self, a, b):
        if b not in self.macs[a]:
            self.macs[a][b] = self.next_mac()

        if a not in self.macs[b]:
            self.macs[b][a] = self.next_mac()

        return (self.macs[a][b], self.macs[b][a])

    def next_ip(self):
        self.ip_counter += 1
        return ip_from_int(self.ip_counter)

    def ip(self, a):
        if a not in self.ips:
            self.ips[a] = self.next_ip()

        return self.ips[a]

    def from_yuml(self, yuml):
        nodes = collections.OrderedDict()

        node_pattern = re.compile(r'^\[([^\]]+)\]$')
        edge_pattern = re.compile(r'^\[([^\]]+)\]-\[([^\]]+)\]$')
        for line in yuml.strip().splitlines():
            node_match = node_pattern.match(line)
            if node_match:
                node = node_match.group(1)
                if node not in nodes:
                    nodes[node] = []

            else:
                edge_match = edge_pattern.match(line)
                if edge_match:
                    left, right = edge_match.groups()
                    if left not in nodes:
                        nodes[left] = []

                    if right not in nodes:
                        nodes[right] = []

                    if right not in nodes[left]:
                        nodes[left].append(right)

                    if left not in nodes[right]:
                        nodes[right].append(left)

        return self.from_nodes(nodes)

    def from_counts(self, sites=1, rows=4, racks=8, hosts=32):
        nodes = collections.OrderedDict()
        sides = ("a", "b")

        for site in range(1, sites + 1):
            def add_node(node, connected_nodes):
                nodes["s{}-{}".format(site, node)] = [
                    "s{}-{}".format(site, x) for x in connected_nodes]

            add_node("gw-a", ["gw-b", "core-a", "core-b"])
            add_node("gw-b", ["gw-a", "core-a", "core-b"])

            add_node(
                "core-a",
                ["core-b", "gw-a", "gw-b"] +
                list(itertools.chain.from_iterable(zip(
                    ("row-{}a".format(x + 1) for x in range(rows)),
                    ("row-{}b".format(x + 1) for x in range(rows))))))

            add_node(
                "core-b",
                ["core-a", "gw-a", "gw-b"] +
                list(itertools.chain.from_iterable(zip(
                    ("row-{}a".format(x + 1) for x in range(rows)),
                    ("row-{}b".format(x + 1) for x in range(rows))))))

            for row in range(1, rows + 1):
                for side in sides:
                    add_node(
                        "row-{}{}".format(row, side),
                        ["core-a", "core-b"] +
                        list(itertools.chain.from_iterable(zip(
                            ("rack-{}-{}a".format(row, x + 1) for x in range(racks)),
                            ("rack-{}-{}b".format(row, x + 1) for x in range(racks))))))

                for rack in range(1, racks + 1):
                    for side in sides:
                        add_node(
                            "rack-{}-{}{}".format(row, rack, side),
                            ["row-{}a".format(row), "row-{}b".format(row)] +
                            ["host-{}-{}-{}".format(row, rack, x + 1) for x in range(hosts)])

                    for host in range(1, hosts + 1):
                        add_node(
                            "host-{}-{}-{}".format(row, rack, host),
                            ["rack-{}-{}{}".format(row, rack, x) for x in sides])

        return self.from_nodes(nodes)

    def from_nodes(self, nodes):
        self.log.info("creating %s devices", len(nodes))
        progress = progresslog.ProgressLogger(
            self.log,
            prefix="creating devices",
            total=len(nodes),
            interval=1)

        devices = {}

        with pausedAndOptimizedIndexing():
            for node, connected_nodes in nodes.items():
                devices[node] = self.create_device(node, connected_nodes)
                progress.increment()

        # Update all nodes in Redis graph.
        [connections.update_node(d, force=True) for d in devices.values()]

        self.log.info("finished creating %s devices", len(nodes))
        return devices

    def create_device(self, node, connected_nodes):
        device = self.dmd.Devices.findDeviceByIdExact(node)
        if device:
            device.deleteDevice()

        site = node.split("-", 1)[0]
        gateways = ["{}-gw-a".format(site), "{}-gw-b".format(site)]
        is_host = "host" in node

        dc = self.dmd.Devices.createOrganizer(
            "/Test/Layer2/Site-{}/{}".format(
                site,
                "Host" if is_host else "Switch"))

        dc.setZenProperty("zL2PotentialRootCause", False if is_host else True)
        dc.setZenProperty("zL2Gateways", gateways)

        device = dc.createInstance(node)
        device.setPerformanceMonitor("localhost")
        device.manageIp = self.ip(node)

        from Products.ZenModel.IpInterface import IpInterface

        mgmt_if_id = "mgmt"
        device.os.interfaces._setObject(mgmt_if_id, IpInterface(mgmt_if_id))
        mgmt_if = device.os.interfaces._getOb(mgmt_if_id)
        mgmt_if.macaddress = self.mac_pair(node, None)[0]
        mgmt_if.setIpAddresses(["{}/16".format(self.ip(node))])
        mgmt_if.index_object()
        notify(IndexingEvent(mgmt_if))

        for connected_node in connected_nodes:
            connecting_if_id = "to-{}".format(connected_node)
            device.os.interfaces._setObject(
                connecting_if_id,
                IpInterface(connecting_if_id))

            local_mac, client_mac = self.mac_pair(node, connected_node)

            connecting_if = device.os.interfaces._getOb(connecting_if_id)
            connecting_if.macaddress = local_mac

            if not is_host:
                connecting_if.clientmacs = [client_mac]

            connecting_if.setIpAddresses(
                ["{}/16".format(self.ip(node))])

            notify(IndexingEvent(connecting_if))

        if "rack" in node:
            for x in xrange(24):
                lan_if_id = "lan-{}".format(x)
                device.os.interfaces._setObject(
                    lan_if_id,
                    IpInterface(lan_if_id))

                lan_if = device.os.interfaces._getOb(lan_if_id)
                lan_if.macaddress = self.next_mac()
                lan_if.clientmacs = [self.next_mac() for _ in xrange(256)]

            notify(IndexingEvent(lan_if))

        notify(IndexingEvent(device))
        device.index_object()

        return device

    def create_marker_event(self, summary):
        self.dmd.ZenEventManager.sendEvent(dict(
            device="stresser",
            severity=2,
            summary=summary,
            agent="stresser",
            monitor="localhost"))

    def create_events(self, x=1, clear=False, ping=False, filt=None, side=None):
        """Create events for devices."""
        events = []

        for device in [b.id for b in self.dmd.Devices.deviceSearch()]:
            if not filt or filt in device:
                if not side or device.endswith(side):
                    for i in range(x):
                        if ping:
                            events.append(dict(
                                device=device,
                                severity=0 if clear else 5,
                                summary="ping is {}".format("UP" if clear else "DOWN"),
                                eventClass="/Status/Ping",
                                agent="zenping",
                                monitor="localhost"))
                        else:
                            events.append(dict(
                                device=device,
                                severity=0 if clear else 3,
                                summary="your general run-of-the-mill performance problem",
                                agent="zenperfsnmp",
                                monitor="localhost"))

                        if clear:
                            # Only send 1 clear regardless of x.
                            break

        self.create_marker_event(
            "n={} x={} clear={} ping={} filt={} side={}"
            .format(
                len(events), x, clear, ping, filt, side))

        self.dmd.ZenEventManager.sendEvents(events)


def int_from_ip(ip):
    """Return 179680512 given "10.181.181.0"."""
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def ip_from_int(i):
    """Return "10.181.181.0" given 179680512."""
    return socket.inet_ntoa(struct.pack("!I", i))


def index_from_mac(mac):
    """Return "1.2.3.4.5.26" given "01:02:03:04:05:1a"."""
    return ".".join(str(int(x, 16)) for x in mac.split(":"))


def int_from_mac(mac):
    """Return 1108152157466 given "01:02:03:04:05:1a"."""
    return int(mac.translate(None, ":"), 16)


def hex_from_mac(mac):
    """Return "0x010203040526" given "01:02:03:04:05:1a"."""
    return "0x{}".format(mac.translate(None, ":"))
