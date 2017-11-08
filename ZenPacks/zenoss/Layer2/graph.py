##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Multi-Provider MySQL Undirected Graph."""

# stdlib imports
import collections
import itertools
import warnings

# third-party imports
import MySQLdb
import MySQLdb.constants.CR
import networkx

# default exports
__all__ = (
    "get_graph",
    "get_provider",
    )

# Ignore "table already exists" warnings.
warnings.filterwarnings("ignore", category=MySQLdb.Warning)

# module caches
GRAPH = None


def get_graph():
    """Return Graph singleton."""
    global GRAPH

    if GRAPH is None:
        GRAPH = Graph()

    return GRAPH


def get_provider(uuid):
    """Return Provider given its uuid."""
    graph = get_graph()
    return graph.get_provider(uuid)


class Graph(object):
    """Undirected graph of edges from all providers.

    This class is used to read information from the graph, and perform
    global operations on the graph such as clear and compact. See the
    Provider class for adding information to the graph.

    """

    namespace = "l2"

    def __init__(self):
        self.db = MySQL(onConnect=self.create_tables)

    def get_provider(self, uuid):
        return Provider(self, uuid)

    def get_table(self, table):
        return "{ns}_{table}".format(
            ns=self.namespace,
            table=table)

    def create_tables(self):
        self.db.create_table(
            table=self.get_table("providers"),
            columns=[
                ("providerUUID", "VARCHAR(36) NOT NULL UNIQUE PRIMARY KEY"),
                ("lastChange", "BIGINT NOT NULL")])

        self.db.create_table(
            table=self.get_table("edges"),
            columns=[
                ("providerUUID", "VARCHAR(36) NOT NULL"),
                ("source", "VARCHAR(1024) NOT NULL"),
                ("target", "VARCHAR(1024) NOT NULL"),
                ("layer", "VARCHAR(255) NOT NULL")],
            indexes=[
                ("providerUUID", ("providerUUID",)),
                ("sourceByLayer", ("source", "layer")),
                ("targetByLayer", ("target", "layer")),
                ("layer", ("layer",))])

    def get_layers(self):
        """Return set of all layers in the graph."""
        rows = self.db.execute(
            "SELECT DISTINCT layer FROM {table} ORDER BY layer ASC".format(
                table=self.get_table("edges")))

        return set(x[0] for x in rows)

    def get_edges(self, node, layers):
        """Return list of (source, target, layers) edge tuples.

        The source of each edge will be node. Only edges with one of the
        layers listed in the layers argument will be returned.

        """
        if not layers:
            return []

        return self.merge_layers(
            self.db.execute(
                "SELECT DISTINCT source, target, layer FROM {table}"
                " WHERE (source = %s OR target = %s)"
                "   AND layer IN ({layer_subs})".format(
                    table=self.get_table("edges"),
                    layer_subs=",".join("%s" for x in layers)),
                [node, node] + list(layers)),
            preferred_source=node)

    def count_edges(self):
        """Return count of (source, target, layers) edges."""
        return len(
            self.merge_layers(
                self.db.execute(
                    "SELECT DISTINCT source, target, layer"
                    "  FROM {table}".format(
                        table=self.get_table("edges")))))

    def count_providers(self):
        return self.db.execute(
            "SELECT COUNT(providerUUID) FROM {table}".format(
                table=self.get_table("providers")))[0][0]

    def count_layers(self):
        return self.db.execute(
            "SELECT COUNT(DISTINCT layer) FROM {table}".format(
                table=self.get_table("edges")))[0][0]

    def merge_layers(self, edges, preferred_source=None):
        """Return merged list of (source, target, layers).

        The edges input argument is expected to be a list of
        (source, target, layer) triples.

        If the preferred_source parameter is specified, it will become the
        source in the merged list of edge triples whether it was the source or
        target.

        """

        edge_layers = collections.defaultdict(set)

        for source, target, layer in edges:
            if target == preferred_source:
                source, target = target, source
            elif source != preferred_source:
                source, target = tuple(sorted((source, target)))

            edge_layers[(source, target)].add(layer)

        return [(k[0], k[1], v) for k, v in edge_layers.iteritems()]

    def networkx_graph(self, root, layers, depth=None):
        """Return a NetworkX Graph.

        NetworkX is a third-party graph library that makes all sorts of
        useful graph operations available.

        The graph will begin being seeded at the specified "root" node.
        Only edges that have one of the layers listed in "layers" will
        be followed. Only nodes "depth" hops away from "root" or less
        will be present in the graph, and only the edges necessary to
        reach those nodes will be present in the graph.

        If "depth" is None, the subgraph of nodes reachable from "root"
        will be returned.

        The most important performance consideration when calling this
        method is how many nodes are expected to be in the graph. There
        will be N HKEYS calls made to Redis for each node where N is the
        length of "layers". The N HKEYS calls for each node are
        pipelined, so there will only be 1 round trip to Redis for each
        node.

        """
        nxg = networkx.Graph()
        seen_nodes = set()
        next_nodes = set([root])
        for current_depth in itertools.count(start=1):
            if depth is not None and current_depth > depth:
                # Stopping due to traversal depth.
                break

            if not next_nodes:
                # No more hops to explore.
                break

            edges = itertools.chain.from_iterable(
                self.get_edges(n, layers=layers) for n in next_nodes)

            next_nodes = set()
            for source, target, edge_layers in edges:
                if source not in seen_nodes:
                    seen_nodes.add(source)

                if target not in seen_nodes:
                    next_nodes.add(target)

                nxg.add_edge(source, target, layers=edge_layers)

        return nxg

    def compact(self, providerUUIDs):
        """Clear provider data not listed in providerUUIDs."""
        if not providerUUIDs:
            self.clear()

        for table in ("edges", "providers"):
            self.db.execute(
                "DELETE FROM {table}"
                " WHERE providerUUID NOT IN ({layer_subs})".format(
                    table=self.get_table(table),
                    layer_subs=",".join("%s" for x in providerUUIDs)),
                list(providerUUIDs))

    def clear(self):
        """Clear all layer2 information from the database."""
        for table in ("edges", "providers"):
            self.db.execute(
                "TRUNCATE TABLE {table}".format(
                    table=self.get_table(table)))


class Provider(object):
    """Provider of information for a graph."""

    def __init__(self, graph, uuid):
        self.graph = graph
        self.uuid = uuid

        # Loaded from database.
        self._db_lastChange = None

    @property
    def lastChange(self):
        if self._db_lastChange is None:
            self.load_properties()

        return self._db_lastChange

    def load_properties(self):
        rows = self.graph.db.execute(
            "SELECT lastChange FROM {table} WHERE providerUUID = %s".format(
                table=self.graph.get_table("providers")),
            self.uuid)

        if rows:
            self._db_lastChange = rows[0][0]
        else:
            self._db_lastChange = None

    def update_properties(self, properties):
        for k, v in properties.iteritems():
            setattr(self, "_db_{}".format(k), v)

    def update_edges(self, edges, lastChange):
        """Update list of (source, target, layers) edge triples."""
        rows = set()

        for source, target, layers in edges:
            if not (source and target and layers):
                continue

            source, target = tuple(sorted((source, target)))

            for layer in layers:
                rows.add((self.uuid, source, target, layer))

        self.graph.db.execute(
            "DELETE FROM {table} WHERE providerUUID = %s".format(
                table=self.graph.get_table("edges")),
            self.uuid)

        # Convert back to a list for the insert.
        rows = list(rows)

        self.graph.db.insert(
            table=self.graph.get_table("edges"),
            columns=("providerUUID", "source", "target", "layer"),
            rows=rows)

        self.graph.db.insert(
            table=self.graph.get_table("providers"),
            columns=("providerUUID", "lastChange"),
            rows=[(self.uuid, lastChange)])

        self.update_properties({"lastChange": lastChange})

    def clear(self):
        """Remove this provider's data from the graph."""
        for table in ("edges", "providers"):
            self.graph.db.execute(
                "DELETE FROM {table} WHERE providerUUID = %s".format(
                    table=self.graph.get_table(table)),
                self.uuid)

        self.update_properties({"lastChange": None})


class MySQL(object):
    """Consolidated handling of direct MySQL interaction."""

    # We must try reconnecting up to 3 times for errors that can be fixed by
    # reconnecting. This is because the first attempt may fail with a
    # SERVER_GONE the first time, a SERVER_LOST the second, and succeed on
    # the third attempt.
    RECONNECT_ATTEMPTS = 3

    RECONNECT_ERRORS = (
        MySQLdb.constants.CR.SERVER_GONE_ERROR,
        MySQLdb.constants.CR.SERVER_LOST,
        )

    def __init__(self, onConnect=None):
        self.onConnect = onConnect
        self.connection = None

    def connect(self):
        if self.connection and self.connection.open:
            return

        from Products.ZenUtils.GlobalConfig import getGlobalConfiguration

        global_config = getGlobalConfiguration()
        connect_kwargs = {
            "host": global_config.get("zodb-host", "127.0.0.1"),
            "port": int(global_config.get("zodb-port", 3306)),
            "db": global_config.get("zodb-db", "zodb"),
            "user": global_config.get("zodb-user", "zenoss"),
            "passwd": global_config.get("zodb-password", "zenoss"),
        }

        self.connection = MySQLdb.connect(**connect_kwargs)
        self.connection.autocommit(True)

        if callable(self.onConnect):
            self.onConnect()

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass

    def execute(self, statement, params=None):
        return self.with_retry("execute", statement, params)

    def executemany(self, statement, rows):
        if not rows:
            return []

        return self.with_retry("executemany", statement, rows)

    def with_retry(self, fn_name, *args, **kwargs):
        """Execute fn_name with args and kwargs. Retry when appropriate.

        fn_name is expected to be either execute or executemany.

        The operation will only be retried up to three time if either the
        SERVER_LOST or SERVER_GONE_ERROR are encountered. These are the errors
        seen when the remote server disconnects a client that has been idle
        longer than "wait_timeout" seconds.

        """
        results = []

        for attempt in range(1, MySQL.RECONNECT_ATTEMPTS + 1):
            self.connect()
            cursor = self.connection.cursor()

            try:
                getattr(cursor, fn_name)(*args, **kwargs)
            except MySQLdb.OperationalError as e:
                if e.args[0] in MySQL.RECONNECT_ERRORS:
                    if attempt < MySQL.RECONNECT_ATTEMPTS:
                        self.close()
                        continue

                raise
            else:
                results = cursor.fetchall()
                break
            finally:
                cursor.close()

        return results

    def create_table(self, table, columns, indexes=None):
        create_definitions = ["{} {}".format(x[0], x[1]) for x in columns]
        if indexes:
            create_definitions.extend([
                "INDEX {} ({})".format(x[0], ",".join(x[1])) for x in indexes])

        self.execute(
            "CREATE TABLE IF NOT EXISTS {table} ({create_definitions})".format(
                table=table,
                create_definitions=",".join(create_definitions)))

    def insert(self, table, columns, rows):
        self.executemany(
            "INSERT IGNORE INTO {table} ({columns}) "
            "VALUES ({substitutions})".format(
                table=table,
                columns=",".join(columns),
                substitutions=",".join(["%s"] * len(columns))),
            rows)
