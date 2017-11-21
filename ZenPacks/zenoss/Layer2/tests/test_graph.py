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
import time
import unittest

# zenpack imports
from ZenPacks.zenoss.Layer2.graph import get_graph
from ZenPacks.zenoss.Layer2.graph import MySQL


class TestGraph(unittest.TestCase):
    """Graph and Origin class tests."""

    def setUp(self):
        super(TestGraph, self).setUp()
        self.graph = get_graph()
        self.graph.clear()

    def tearDown(self):
        self.graph.clear()
        super(TestGraph, self).tearDown()

    def test_lastChange(self):
        # First provider behaves.
        provider1 = self.graph.get_provider("p1")
        self.assertIsNone(provider1.lastChange)
        provider1.update_edges([("s1", "t1", ["layer1"])], 1)
        self.assertEqual(provider1.lastChange, 1)

        # Second provider behaves as well as the first.
        provider2 = self.graph.get_provider("p2")
        self.assertIsNone(provider2.lastChange)
        provider2.update_edges([("s1", "t1", ["layer1"])], 2)
        self.assertEqual(provider2.lastChange, 2)

        # provider2 shouldn't interfere with provider1's lastChange.
        self.assertEqual(provider1.lastChange, 1)

        # Clearing provider2 should clear only its lastChange.
        provider2.clear()
        self.assertIsNone(provider2.lastChange)
        self.assertEqual(provider1.lastChange, 1)

    def test_clear_all_providers(self):
        provider1 = self.graph.get_provider("p1")
        provider1.update_edges([("s1", "t1", ["layer1"])], 1)
        provider2 = self.graph.get_provider("p2")
        provider2.update_edges([("s1", "t1", ["layer1"])], 2)

        # Clearing all providers should delete all provider data.
        provider1.clear()
        provider2.clear()
        self.assertEqual(self.graph.count_edges(), 0)
        self.assertEqual(self.graph.count_providers(), 0)

    def test_clear_graph(self):
        provider1 = self.graph.get_provider("p1")
        provider1.update_edges([("s1", "t1", ["layer1"])], 1)
        provider2 = self.graph.get_provider("p2")
        provider2.update_edges([("s1", "t1", ["layer1"])], 2)

        # Clearing the graph should delete all graph data.
        self.graph.clear()
        self.assertEqual(self.graph.count_layers(), 0)
        self.assertEqual(self.graph.count_edges(), 0)
        self.assertEqual(self.graph.count_providers(), 0)

    def test_remove_nodes(self):
        create_topology(self.graph)

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
        p_host1 = self.graph.get_provider("host1")
        p_host1.update_edges([
            ("h1", "n1", ["layer3"]),
            ], "host1")

        p_switch1 = self.graph.get_provider("switch1")
        p_switch1.update_edges([
            ("sw1", "h1", ["layer2"]),
            ("sw1", "r1", ["layer2", "cdp"]),
            ("sw1", "n2", ["layer3"]),
            ], "switch1")

        p_router1 = self.graph.get_provider("router1")
        p_router1.update_edges([
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
        create_topology(self.graph)

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
        create_topology(self.graph)

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
        create_topology(self.graph)
        self.assertEquals(
            self.graph.get_layers(),
            {"cdp", "layer2", "layer3"})

    def test_networkx_graph(self):
        create_topology(self.graph)

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


class TestMySQL(unittest.TestCase):
    def test_reconnect(self):
        db = MySQL()
        db.execute("SET SESSION wait_timeout=1")

        db.execute("DROP TABLE IF EXISTS l2_test")
        db.create_table(
            "l2_test", [
                ("id", "VARCHAR(36) NOT NULL UNIQUE PRIMARY KEY"),
                ("value", "VARCHAR(255) NOT NULL")])

        db.close()
        rows = db.executemany(
            "INSERT INTO l2_test (id, value) VALUES (%s, %s)", [
                ("959b8d02-3a54-4c93-a6d0-2a94d59f8f84", "first"),
                ("8474b0f2-9a0f-4f01-b809-c699d857e562", "second")])

        # executemany works after an explicit close.
        self.assertEqual(rows, ())

        time.sleep(1.1)
        rows = db.execute("SELECT * FROM l2_test")

        # query works after a server timeout.
        try:
            self.assertEqual(len(rows), 2)
        finally:
            db.close()


def create_topology(graph):
    graph.get_provider("host1").update_edges([
        ("h1", "n1", ["layer3"]),
        ], "host1")

    graph.get_provider("host2").update_edges([
        ("h2", "n1", ["layer3"]),
        ], "host2")

    graph.get_provider("switch1").update_edges([
        ("sw1", "h1", ["layer2"]),
        ("sw1", "h2", ["layer2"]),
        ("sw1", "r1", ["layer2", "cdp"]),
        ("sw1", "r2", ["layer2", "cdp"]),
        ("sw1", "n2", ["layer3"]),
        ], "switch1")

    graph.get_provider("switch2").update_edges([
        ("sw2", "h1", ["layer2"]),
        ("sw2", "h2", ["layer2"]),
        ("sw2", "r1", ["layer2", "cdp"]),
        ("sw2", "r2", ["layer2", "cdp"]),
        ("sw2", "n2", ["layer3"]),
        ], "switch2")

    graph.get_provider("router1").update_edges([
        ("r1", "sw1", ["layer2", "cdp"]),
        ("r1", "sw2", ["layer2", "cdp"]),
        ("r1", "n1", ["layer3"]),
        ("r1", "n2", ["layer3"]),
        ], "router1")

    graph.get_provider("router2").update_edges([
        ("r2", "sw1", ["layer2", "cdp"]),
        ("r2", "sw2", ["layer2", "cdp"]),
        ("r2", "n1", ["layer3"]),
        ("r2", "n2", ["layer3"]),
        ], "router2")
