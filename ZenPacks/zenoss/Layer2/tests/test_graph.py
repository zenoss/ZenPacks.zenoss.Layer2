##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Test cases for graph module."""

# stdlib imports
import os
import unittest

# zenpack imports
from ZenPacks.zenoss.Layer2 import graph

# constants
NS = "t"


class TestRedisDiscovery(unittest.TestCase):
    """Redis discovery testing."""

    def setUp(self):
        # Store existing value of environment variables so we can
        # restore them after this test.
        self.controlplane = os.environ.get("CONTROLPLANE", "")
        self.redis_url = os.environ.get("REDIS_URL", "")

        # Unset environment variables so the tests can set them as
        # needed.
        os.environ["CONTROLPLANE"] = ""
        os.environ["REDIS_URL"] = ""

    def tearDown(self):
        # Restore environment variables to their pre-test values.
        os.environ["CONTROLPLANE"] = self.controlplane
        os.environ["REDIS_URL"] = self.redis_url

    def test_discover_redis_url_zenoss4(self):
        """Test when running on same server as redis in Zenoss 4."""
        self.assertEqual(
            "redis://localhost:16379/1",
            graph.discover_redis_url())

    def test_discover_redis_url_zenoss4_explicit(self):
        """Test when user has manually set REDIS_URL in Zenoss 4."""
        os.environ["REDIS_URL"] = "FOO"
        self.assertEqual("FOO", graph.discover_redis_url())

    def test_discover_redis_url_zenoss5(self):
        """Test when running in Zenoss 5."""
        os.environ["CONTROLPLANE"] = "1"
        self.assertEqual(
            "redis://localhost:6379/1",
            graph.discover_redis_url())


class TestGraph(unittest.TestCase):
    """Graph and Origin class tests."""

    def setUp(self):
        self.graph = graph.Graph(NS)
        self.redis = graph.discover_redis()
        self.redis.flushdb()

    def tearDown(self):
        self.redis = graph.discover_redis()
        self.redis.flushdb()

    def test_checksums(self):
        # First origin behaves.
        origin1 = graph.Origin(NS, "o1")
        self.assertIsNone(origin1.get_checksum())
        origin1.add_edges([("s1", "t1", ["layer1"])], "checksum1")
        self.assertEqual(origin1.get_checksum(), "checksum1")

        # Second origin behaves as well as the first.
        origin2 = graph.Origin(NS, "o2")
        self.assertIsNone(origin2.get_checksum())
        origin2.add_edges([("s1", "t1", ["layer1"])], "checksum2")
        self.assertEqual(origin2.get_checksum(), "checksum2")

        # Origin2 shouldn't interfere with origin1's checksum.
        self.assertEqual(origin1.get_checksum(), "checksum1")

        # Clearing an origin should clear only its checksum.
        origin2.clear()
        self.assertIsNone(origin2.get_checksum())
        self.assertEqual(origin1.get_checksum(), "checksum1")

    def test_clear_all_origins(self):
        origin1 = graph.Origin(NS, "o1")
        origin1.add_edges([("s1", "t1", ["layer1"])], "checksum1")
        origin2 = graph.Origin(NS, "o2")
        origin2.add_edges([("s1", "t1", ["layer1"])], "checksum2")

        # Clearing all origins should delete all Redis keys.
        origin1.clear()
        origin2.clear()
        self.assertEqual(len(self.redis.keys()), 0)

    def test_clear_graph(self):
        origin1 = graph.Origin(NS, "o1")
        origin1.add_edges([("s1", "t1", ["layer1"])], "checksum1")
        origin2 = graph.Origin(NS, "o2")
        origin2.add_edges([("s1", "t1", ["layer1"])], "checksum2")

        # Clearing the graph should delete all Redis keys.
        self.graph.clear()
        self.assertEqual(len(self.redis.keys()), 0)

    def test_remove_nodes(self):
        create_topology()

        # Validate edges pre-removal.
        self.assertItemsEqual(
            self.graph.get_edges("h1", ["layer2"]), [
                ("h1", "sw1", {"layer2"}),
                ("h1", "sw2", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["layer2"]), [
                ("sw1", "h1", {"layer2"}),
                ("sw1", "h2", {"layer2"}),
                ("sw1", "r1", {"layer2"}),
                ("sw1", "r2", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("r1", ["layer2"]), [
                ("r1", "sw1", {"layer2"}),
                ("r1", "sw2", {"layer2"}),
                ])

        # Simulate removal of (h|sw|r)2 nodes.
        o_host1 = graph.Origin(NS, "host1")
        o_host1.clear()
        o_host1.add_edges([
            ("h1", "n1", ["layer3"]),
            ], "host1")

        o_switch1 = graph.Origin(NS, "switch1")
        o_switch1.clear()
        o_switch1.add_edges([
            ("sw1", "h1", ["layer2"]),
            ("sw1", "r1", ["layer2", "cdp"]),
            ("sw1", "n2", ["layer3"]),
            ], "switch1")

        o_router1 = graph.Origin(NS, "router1")
        o_router1.clear()
        o_router1.add_edges([
            ("r1", "sw1", ["layer2", "cdp"]),
            ("r1", "n1", ["layer3"]),
            ], "router1")

        self.graph.compact(["host1", "switch1", "router1"])

        # Validate edges post-removal.
        self.assertItemsEqual(
            self.graph.get_edges("h1", ["layer2"]), [
                ("h1", "sw1", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["layer2"]), [
                ("sw1", "h1", {"layer2"}),
                ("sw1", "r1", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("r1", ["layer2"]), [
                ("r1", "sw1", {"layer2"}),
                ])

    def test_get_edges_host1(self):
        create_topology()

        self.assertItemsEqual(self.graph.get_edges("h1", layers=[]), [])
        self.assertItemsEqual(
            self.graph.get_edges("h1", ["layer2"]), [
                ("h1", "sw1", {"layer2"}),
                ("h1", "sw2", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("h1", ["layer3"]), [
                ("h1", "n1", {"layer3"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("h1", ["layer2", "layer3"]), [
                ("h1", "sw1", {"layer2"}),
                ("h1", "sw2", {"layer2"}),
                ("h1", "n1", {"layer3"}),
                ])

    def test_get_edges_switch1(self):
        create_topology()

        self.assertItemsEqual(self.graph.get_edges("sw1", layers=[]), [])
        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["cdp"]), [
                ("sw1", "r1", {"cdp"}),
                ("sw1", "r2", {"cdp"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["layer2"]), [
                ("sw1", "h1", {"layer2"}),
                ("sw1", "h2", {"layer2"}),
                ("sw1", "r1", {"layer2"}),
                ("sw1", "r2", {"layer2"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["layer3"]), [
                ("sw1", "n2", {"layer3"}),
                ])

        self.assertItemsEqual(
            self.graph.get_edges("sw1", ["cdp", "layer2", "layer3"]), [
                ("sw1", "h1", {"layer2"}),
                ("sw1", "h2", {"layer2"}),
                ("sw1", "r1", {"cdp", "layer2"}),
                ("sw1", "r2", {"cdp", "layer2"}),
                ("sw1", "n2", {"layer3"}),
                ])

    def test_get_layers(self):
        create_topology()
        self.assertEquals(
            self.graph.get_layers(),
            {"cdp", "layer2", "layer3"})

    def test_networkx_graph(self):
        create_topology()

        # 1 layer, 1 deep.
        g1 = self.graph.networkx_graph("h1", ["layer2"], depth=1)
        self.assertItemsEqual(g1.nodes(), ['sw1', 'h1', 'sw2'])
        self.assertItemsEqual(
            g1.edges(data=True),
            [('sw1', 'h1', {'layers': set(['layer2'])}),
             ('h1', 'sw2', {'layers': set(['layer2'])})])

        # 2 layers, 2 deep.
        g2 = self.graph.networkx_graph("h1", ["layer2", "cdp"], depth=2)
        self.assertItemsEqual(
            g2.nodes(),
            ['r1', 'r2', 'h2', 'h1', 'sw1', 'sw2'])

        self.assertItemsEqual(
            g2.edges(data=True),
            [('r1', 'sw1', {'layers': set(['cdp', 'layer2'])}),
             ('r1', 'sw2', {'layers': set(['cdp', 'layer2'])}),
             ('r2', 'sw1', {'layers': set(['cdp', 'layer2'])}),
             ('r2', 'sw2', {'layers': set(['cdp', 'layer2'])}),
             ('h2', 'sw1', {'layers': set(['layer2'])}),
             ('h2', 'sw2', {'layers': set(['layer2'])}),
             ('h1', 'sw1', {'layers': set(['layer2'])}),
             ('h1', 'sw2', {'layers': set(['layer2'])})])

        # N layers, N deep.
        g3 = self.graph.networkx_graph("h1", ["layer2", "layer3", "cdp"])
        self.assertItemsEqual(
            g3.nodes(),
            ['r1', 'r2', 'h2', 'h1', 'sw1', 'n1', 'n2', 'sw2'])

        self.assertItemsEqual(
            g3.edges(data=True),
            [('r1', 'sw1', {'layers': set(['cdp', 'layer2'])}),
             ('r1', 'n1', {'layers': set(['layer3'])}),
             ('r1', 'n2', {'layers': set(['layer3'])}),
             ('r1', 'sw2', {'layers': set(['cdp', 'layer2'])}),
             ('r2', 'sw1', {'layers': set(['cdp', 'layer2'])}),
             ('r2', 'n1', {'layers': set(['layer3'])}),
             ('r2', 'n2', {'layers': set(['layer3'])}),
             ('r2', 'sw2', {'layers': set(['cdp', 'layer2'])}),
             ('h2', 'sw1', {'layers': set(['layer2'])}),
             ('h2', 'n1', {'layers': set(['layer3'])}),
             ('h2', 'sw2', {'layers': set(['layer2'])}),
             ('h1', 'sw1', {'layers': set(['layer2'])}),
             ('h1', 'n1', {'layers': set(['layer3'])}),
             ('h1', 'sw2', {'layers': set(['layer2'])}),
             ('sw1', 'n2', {'layers': set(['layer3'])}),
             ('n2', 'sw2', {'layers': set(['layer3'])})])


def create_topology():
    graph.Origin(NS, "host1").add_edges([
        ("h1", "n1", ["layer3"]),
        ], "host1")

    graph.Origin(NS, "host2").add_edges([
        ("h2", "n1", ["layer3"]),
        ], "host2")

    graph.Origin(NS, "switch1").add_edges([
        ("sw1", "h1", ["layer2"]),
        ("sw1", "h2", ["layer2"]),
        ("sw1", "r1", ["layer2", "cdp"]),
        ("sw1", "r2", ["layer2", "cdp"]),
        ("sw1", "n2", ["layer3"]),
        ], "switch1")

    graph.Origin(NS, "switch2").add_edges([
        ("sw2", "h1", ["layer2"]),
        ("sw2", "h2", ["layer2"]),
        ("sw2", "r1", ["layer2", "cdp"]),
        ("sw2", "r2", ["layer2", "cdp"]),
        ("sw2", "n2", ["layer3"]),
        ], "switch2")

    graph.Origin(NS, "router1").add_edges([
        ("r1", "sw1", ["layer2", "cdp"]),
        ("r1", "sw2", ["layer2", "cdp"]),
        ("r1", "n1", ["layer3"]),
        ("r1", "n2", ["layer3"]),
        ], "router1")

    graph.Origin(NS, "router2").add_edges([
        ("r2", "sw1", ["layer2", "cdp"]),
        ("r2", "sw2", ["layer2", "cdp"]),
        ("r2", "n1", ["layer3"]),
        ("r2", "n2", ["layer3"]),
        ], "router2")
