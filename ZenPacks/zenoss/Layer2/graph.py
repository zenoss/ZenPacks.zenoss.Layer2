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
import sys
import threading
import time
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
THREAD_LOCAL = threading.local()


def get_graph():
    """Return Graph singleton."""
    global THREAD_LOCAL

    if not hasattr(THREAD_LOCAL, "GRAPH"):
        THREAD_LOCAL.GRAPH = Graph()

    return THREAD_LOCAL.GRAPH


def get_provider(uuid):
    """Return Provider given its uuid."""
    graph = get_graph()
    return graph.get_provider(uuid)


def chunks(s, n):
    """Generate lists of size n from iterable s."""
    for chunk in (s[i:i + n] for i in range(0, len(s), n)):
        yield chunk


class Graph(object):
    """Undirected graph of edges from all providers.

    This class is used to read information from the graph, and perform
    global operations on the graph such as clear and compact. See the
    Provider class for adding information to the graph.

    """

    namespace = "l2_v2"

    def __init__(self):
        self.db = MySQL(onConnect=self.create_tables)

    def get_provider(self, uuid):
        return Provider(self, uuid)

    def get_table(self, table):
        return "{ns}_{table}".format(
            ns=self.namespace,
            table=table)

    @property
    def metadata_table(self):
        return self.get_table("metadata")

    @property
    def providers_table(self):
        return self.get_table("providers")

    @property
    def layers_table(self):
        return self.get_table("layers")

    @property
    def nodes_table(self):
        return self.get_table("nodes")

    @property
    def edges_table(self):
        return self.get_table("edges")

    @property
    def edges_view(self):
        return self.get_table("edges_view")

    def create_tables(self):
        self.db.create_table(
            table=self.metadata_table,
            columns=[
                ("name", "VARCHAR(255) NOT NULL UNIQUE PRIMARY KEY"),
                ("value", "LONGBLOB")])

        self.db.insert(
            table=self.metadata_table,
            ignore=True,
            values={
                "name": "lastOptimize",
                "value": "0"})

        self.db.create_table(
            table=self.providers_table,
            columns=[
                ("id", "INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY"),
                ("uuid", "CHAR(36) NOT NULL UNIQUE"),
                ("lastChange", "VARCHAR(255)")])

        self.db.create_table(
            table=self.nodes_table,
            columns=[
                ("id", "INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY"),
                ("node", "VARCHAR(1024) NOT NULL")],
            indexes=[
                ("UNIQUE INDEX", "node", ("node(767)",))])

        self.db.create_table(
            table=self.layers_table,
            columns=[
                ("id", "INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY"),
                ("layer", "VARCHAR(255) NOT NULL UNIQUE")])

        self.db.create_table(
            table=self.edges_table,
            columns=[
                ("provider_id", "INT UNSIGNED NOT NULL"),
                ("source_id", "INT UNSIGNED NOT NULL"),
                ("target_id", "INT UNSIGNED NOT NULL"),
                ("layer_id", "INT UNSIGNED NOT NULL")],
            indexes=[
                ("UNIQUE INDEX", "allColumns", ("provider_id", "source_id", "target_id", "layer_id")),
                ("INDEX", "sourceByLayer", ("source_id", "layer_id")),
                ("INDEX", "targetByLayer", ("target_id", "layer_id"))],
            foreign_keys=[
                ("provider_id", self.providers_table),
                ("source_id", self.nodes_table),
                ("target_id", self.nodes_table),
                ("layer_id", self.layers_table)])

        self.db.execute(
            "CREATE OR REPLACE VIEW {edges_view} AS "
            "SELECT"
            "    providers.uuid AS provider,"
            "    sources.node AS source,"
            "    targets.node AS target,"
            "    layers.layer AS layer"
            "  FROM {edges_table} AS edges"
            "    INNER JOIN {providers_table} providers"
            "            ON providers.id = edges.provider_id"
            "    INNER JOIN {nodes_table} sources"
            "            ON sources.id = edges.source_id"
            "    INNER JOIN {nodes_table} targets"
            "            ON targets.id = edges.target_id"
            "    INNER JOIN {layers_table} layers"
            "            ON layers.id = edges.layer_id".format(
                edges_view=self.edges_view,
                edges_table=self.edges_table,
                providers_table=self.providers_table,
                nodes_table=self.nodes_table,
                layers_table=self.layers_table))

    def get_node_ids(self, nodes=None):
        """Return map of node to node ID for specified nodes.

        Return map of all nodes if unspecified.

        """
        if nodes is None:
            rows = self.db.execute(
                "SELECT id, node FROM {table}".format(
                    table=self.nodes_table))
        elif nodes:
            rows = self.db.execute(
                "SELECT id, node FROM {table}"
                " WHERE node IN ({node_subs})".format(
                    table=self.nodes_table,
                    node_subs=",".join(["%s"] * len(nodes))),
                list(nodes))
        else:
            rows = []

        return {x[1]: x[0] for x in rows}

    def get_layers(self):
        """Return set of all layers in the graph."""
        rows = self.db.execute(
            "SELECT layer FROM {table} ORDER BY layer ASC".format(
                table=self.layers_table))

        return set(x[0] for x in rows)

    def get_layer_ids(self, layers=None):
        """Return map of layer to layer ID for specified layers.

        Return map of all layers if unspecified.

        """
        if layers is None:
            rows = self.db.execute(
                "SELECT id, layer FROM {table}".format(
                    table=self.layers_table))
        elif layers:
            rows = self.db.execute(
                "SELECT id, layer FROM {table}"
                " WHERE layer IN ({layer_subs})".format(
                    table=self.layers_table,
                    layer_subs=",".join(["%s"] * len(layers))),
                list(layers))
        else:
            rows = []

        return {x[1]: x[0] for x in rows}

    def get_edges(self, nodes, layers):
        """Return list of (source, target, layers) edge tuples.

        The source of each edge will be one of nodes. Only edges with one of
        the layers listed in the layers argument will be returned.

        """
        if not layers or not nodes:
            return []

        nodelist = nodes if isinstance(nodes, list) else list(nodes)
        layerlist = layers if isinstance(layers, list) else list(layers)

        return self.merge_layers(
            self.db.execute(
                "SELECT"
                "    (SELECT node FROM {nodes_table} WHERE id = edges.source_id) AS source,"
                "    (SELECT node FROM {nodes_table} WHERE id = edges.target_id) AS target,"
                "    (SELECT layer FROM {layers_table} WHERE id = edges.layer_id) AS layer"
                " FROM ("
                "   (SELECT source_id, target_id, layer_id"
                "      FROM {edges_table} AS edges"
                "     WHERE source_id IN (SELECT id FROM {nodes_table} WHERE node IN ({node_subs}))"
                "       AND layer_id IN (SELECT id FROM {layers_table} WHERE layer IN ({layer_subs})))"
                "   UNION"
                "   (SELECT source_id, target_id, layer_id"
                "      FROM {edges_table} AS edges"
                "     WHERE target_id IN (SELECT id FROM {nodes_table} WHERE node IN ({node_subs}))"
                "       AND layer_id IN (SELECT id FROM {layers_table} WHERE layer IN ({layer_subs})))"
                "   ) AS edges".format(
                    edges_table=self.edges_table,
                    nodes_table=self.nodes_table,
                    node_subs=",".join(["%s"] * len(nodes)),
                    layers_table=self.layers_table,
                    layer_subs=",".join(["%s"] * len(layers))),
                nodelist + layerlist + nodelist + layerlist),
            preferred_sources=nodes)

    def count_edges(self):
        """Return count of (source, target, layers) edges."""
        return len(
            self.merge_layers(
                self.db.execute(
                    "SELECT source_id, target_id, layer_id"
                    "  FROM {table}".format(
                        table=self.edges_table))))

    def count_providers(self):
        return self.db.execute(
            "SELECT COUNT(id) FROM {table}".format(
                table=self.providers_table))[0][0]

    def count_layers(self):
        return self.db.execute(
            "SELECT COUNT(id) FROM {table}".format(
                table=self.layers_table))[0][0]

    @staticmethod
    def merge_layers(edges, preferred_sources=None):
        """Return merged list of (source, target, layers).

        The edges input argument is expected to be a list of
        (source, target, layer) triples.

        Nodes listed in preferred_sources will become the source whether
        they're found to be a source or a target.

        """

        edge_layers = collections.defaultdict(set)

        for source, target, layer in edges:
            if preferred_sources:
                if source not in preferred_sources:
                    if target in preferred_sources:
                        source, target = target, source

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

            edges = self.get_edges(next_nodes, layers=layers)
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

        keep_table = self.get_table("providers_to_keep")

        self.db.create_table(
            table=keep_table,
            columns=[("uuid", "CHAR(36) NOT NULL UNIQUE")],
            temporary=True)

        self.db.bulk_insert(
            table=keep_table,
            columns=("uuid",),
            rows=[(x,) for x in providerUUIDs],
            ignore=True)

        # Deleting from providers cascades to edges.
        self.db.execute(
            "DELETE p FROM {providers_table} p"
            "    LEFT JOIN {keep_table} k ON k.uuid = p.uuid"
            "        WHERE k.uuid IS NULL".format(
                providers_table=self.providers_table,
                keep_table=keep_table))

        # Cleanup the temporary table.
        self.db.execute("DROP TEMPORARY TABLE {}".format(keep_table))

    def should_optimize(self, optimize_interval=0):
        """Return True if database should be optimized."""
        if optimize_interval <= 0:
            return False

        lastOptimize_results = self.db.execute(
            "SELECT value FROM {table} WHERE name = %s LIMIT 1".format(
                table=self.metadata_table),
            ("lastOptimize",))

        for lastOptimize, in lastOptimize_results:
            try:
                if int(lastOptimize) + optimize_interval < time.time():
                    return True
            except Exception:
                return True

        return False

    def optimize(self):
        """Optimize all layer2 tables in the database."""
        for table in ("metadata", "providers", "layers", "nodes", "edges"):
            self.db.execute(
                "OPTIMIZE TABLE {table}".format(
                    table=self.get_table(table)))

        self.db.execute(
            "UPDATE {table} SET value = %s WHERE name = %s".format(
                table=self.metadata_table),
            [str(int(time.time())), "lastOptimize"])

    def clear(self):
        """Clear all layer2 information from the database."""
        try:
            self.db.execute("TRUNCATE TABLE {}".format(self.edges_table))
        except Exception:
            pass

        for table in ("metadata", "providers", "layers", "nodes"):
            try:
                self.db.execute(
                    "DELETE FROM {table}".format(
                        table=self.get_table(table)))
            except Exception:
                pass

        # Tables require optimization after emptying.
        self.optimize()

    def migrate(self):
        """Migrate data from previous versions."""
        for old_table in ("l2_edges", "l2_providers", "l2_metadata"):
            if self.db.table_exists(old_table):
                self.db.execute(
                    "DROP TABLE IF EXISTS {table}".format(table=old_table))


class Provider(object):
    """Provider of information for a graph."""

    def __init__(self, graph, uuid):
        self.graph = graph
        self.uuid = uuid

        # Loaded from database.
        self.id = None
        self.lastChange = None

    def save(self, lastChange):
        """Save provider to database. Return provider.id or None."""
        if self.id is not None and lastChange == self.lastChange:
            return

        self.graph.db.execute(
            "INSERT INTO {table} (uuid, lastChange) VALUES (%s, %s)"
            "  ON DUPLICATE KEY UPDATE"
            "    id=LAST_INSERT_ID(id),"
            "    lastChange=%s".format(
                table=self.graph.providers_table),
            [self.uuid, lastChange, lastChange])

        rows = self.graph.db.execute("SELECT LAST_INSERT_ID()")

        if rows:
            self.lastChange = lastChange
            self.id = rows[0][0]

            return self.id

    def load(self):
        """Load provider from database. Return provider.id or None."""
        if self.id is not None:
            return self.id

        rows = self.graph.db.execute(
            "SELECT id, lastChange FROM {table} WHERE uuid = %s".format(
                table=self.graph.providers_table),
            self.uuid)

        if rows:
            self.id = rows[0][0]
            self.lastChange = rows[0][1]

        return self.id

    def update_properties(self, properties):
        for k, v in properties.iteritems():
            setattr(self, "_db_{}".format(k), v)

    def get_existing_state(self):
        state = {"rows": set(), "node_ids": {}, "layer_ids": {}}

        if self.id is None:
            return state

        rows = self.graph.db.execute(
            "SELECT"
            "    sources.node AS source,"
            "    edges.source_id AS source_id,"
            "    targets.node AS target,"
            "    edges.target_id AS target_id,"
            "    layers.layer AS layer,"
            "    edges.layer_id AS layer_id"
            "  FROM {providers_table} AS providers"
            "    INNER JOIN {edges_table} AS edges ON edges.provider_id = providers.id"
            "    INNER JOIN {nodes_table} AS sources ON edges.source_id = sources.id"
            "    INNER JOIN {nodes_table} AS targets ON edges.target_id = targets.id"
            "    INNER JOIN {layers_table} AS layers on edges.layer_id = layers.id"
            " WHERE providers.uuid = %s".format(
                providers_table=self.graph.providers_table,
                edges_table=self.graph.edges_table,
                nodes_table=self.graph.nodes_table,
                layers_table=self.graph.layers_table),
            self.uuid)

        for s, sid, t, tid, l, lid in rows:
            state["rows"].add((s, t, l))
            state["node_ids"].setdefault(s, sid)
            state["node_ids"].setdefault(t, tid)
            state["layer_ids"].setdefault(l, lid)

        return state

    def update_edges(self, edges, lastChange):
        """Update list of (source, target, layers) edge triples."""
        rows, layers, nodes = set(), set(), set()

        for s, t, ls in edges:
            if not (s and t and ls):
                continue

            # Sort nodes to avoid logically duplicate undirected edges.
            s, t = tuple(sorted((s, t)))

            nodes.update((s, t))
            layers.update(ls)

            for l in ls:
                rows.add((s, t, l))

        # Ensure we have a provider ID.
        self.save(lastChange)

        # Current state of this provider's edges in the database.
        state = self.get_existing_state()

        # Create any nodes that don't already exist.
        new_nodes = nodes.difference(state["node_ids"])
        if new_nodes:
            self.graph.db.bulk_insert(
                table=self.graph.nodes_table,
                columns=("node",),
                rows=[(x,) for x in new_nodes],
                ignore=True)

            # Merge new node ID mappings into state to complete map.
            state["node_ids"].update(self.graph.get_node_ids(new_nodes))

        # Create any layers that don't already exist.
        new_layers = layers.difference(state["layer_ids"])
        if new_layers:
            self.graph.db.bulk_insert(
                table=self.graph.layers_table,
                columns=("layer",),
                rows=[(x,) for x in new_layers],
                ignore=True)

            # Merge new layer ID mappings into state to complete map.
            state["layer_ids"].update(self.graph.get_layer_ids(new_layers))

        # Delete old edges.
        old_rows = state["rows"].difference(rows)
        if old_rows:
            delete_table = self.graph.get_table("edges_to_delete")

            # Delete in chunks to avoid edges table deadlocks.
            for i, old_rows_chunk in enumerate(chunks(list(old_rows), 1000)):
                # Create a temporary table filled with edges to delete.
                self.graph.db.create_table(
                    table=delete_table,
                    columns=[
                        ("source_id", "INT UNSIGNED NOT NULL"),
                        ("target_id", "INT UNSIGNED NOT NULL"),
                        ("layer_id", "INT UNSIGNED NOT NULL")],
                    temporary=True)

                self.graph.db.bulk_insert(
                    table=delete_table,
                    columns=("source_id", "target_id", "layer_id"),
                    rows=[(
                        state["node_ids"][x[0]],
                        state["node_ids"][x[1]],
                        state["layer_ids"][x[2]],
                        ) for x in old_rows_chunk],
                    ignore=True)

                # Delete all edges that exist in the temporary table.
                self.graph.db.execute(
                    "DELETE FROM e USING {edges_table} e"
                    " INNER JOIN {delete_table} d ON ("
                    "   e.source_id = d.source_id AND"
                    "   e.target_id = d.target_id AND"
                    "   e.layer_id = d.layer_id)".format(
                        edges_table=self.graph.edges_table,
                        delete_table=delete_table))

                # Cleanup the temporary table.
                self.graph.db.execute("DROP TEMPORARY TABLE {}".format(delete_table))

        # Insert new edges.
        new_rows = rows.difference(state["rows"])
        if new_rows:
            self.graph.db.bulk_insert(
                table=self.graph.edges_table,
                columns=("provider_id", "source_id", "target_id", "layer_id"),
                rows=[(
                    self.id,
                    state["node_ids"][x[0]],
                    state["node_ids"][x[1]],
                    state["layer_ids"][x[2]],
                    ) for x in new_rows],
                ignore=True)

    def clear(self):
        """Remove this provider's data from the graph."""
        self.graph.db.execute(
            "DELETE FROM {table} WHERE uuid = %s".format(
                table=self.graph.providers_table),
            self.uuid)

        # Delete from providers cascades to edges.

        self.id = None
        self.lastChange = None


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

        # Using "localhost" as the MySQL host can cause the mysql library to
        # connect using the UNIX domain socket instead of the network. By
        # replacing localhost with 127.0.0.1 we force the network to be used.
        if connect_kwargs["host"] == "localhost":
            connect_kwargs["host"] = "127.0.0.1"

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

        # We chunk large rows into multiple queries to avoid exceeding the
        # server's max_allowed_packet configuration. We don't know what the
        # configuration is here, but it's been 64MB in Zenoss for a while.
        chunks = [[]]

        for row in rows:
            if sys.getsizeof(chunks[-1]) > 10485760:
                chunks.append([])

            chunks[-1].append(row)

        for chunk in chunks:
            self.with_retry("executemany", statement, chunk)

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
                # Fetching results after executemany will fail.
                if fn_name != "executemany":
                    results = cursor.fetchall()

                break
            finally:
                cursor.close()

        return results

    def table_exists(self, table):
        """Return True if table exists, False if not."""
        rows = self.execute(
            "SELECT COUNT(*) FROM information_schema.tables"
            " WHERE table_name = %s",
            params=[table])

        if rows and rows[0][0] > 0:
            return True

        return False

    def create_table(
            self,
            table,
            columns,
            indexes=None,
            foreign_keys=None,
            temporary=False):
        """Create database table."""
        create_definitions = ["{} {}".format(x[0], x[1]) for x in columns]
        if indexes:
            create_definitions.extend([
                "{} {} ({})".format(x[0], x[1], ",".join(x[2])) for x in indexes])

        if foreign_keys:
            create_definitions.extend([
                "FOREIGN KEY ({}) REFERENCES {}(id) ON DELETE CASCADE".format(
                    x[0], x[1]) for x in foreign_keys])

        self.execute(
            "CREATE {type} IF NOT EXISTS {table} ({create_definitions})".format(
                type="TEMPORARY TABLE" if temporary else "TABLE",
                table=table,
                create_definitions=",".join(create_definitions)))

    def insert(self, table=None, values=None, ignore=False):
        """Insert row of values into table. Return None."""
        if not (table and values):
            return

        columns, params = zip(*values.iteritems())
        self.execute(
            "INSERT{ignore} INTO {table} ({columns}) "
            "VALUES ({substitutions})".format(
                ignore=" IGNORE" if ignore else "",
                table=table,
                columns=",".join(columns),
                substitutions=",".join(["%s"] * len(columns))),
            list(params))

    def bulk_insert(self, table=None, columns=None, rows=None, ignore=False):
        """Bulk INSERT IGNORE rows for columns into table. Return None."""
        if not (table and columns and rows):
            return

        # It's important that "values" below be lowercase. MySQLdb 1.2.3 and
        # earlier have a bug that prevents the bulk insert optimization from
        # working if VALUES isn't lowercase.
        #
        # https://github.com/farcepest/MySQLdb1/commit/6fc719b4b1a6f51a7717680c491be241c160c97b
        self.executemany(
            "INSERT{ignore} INTO {table} ({columns}) "
            "values ({substitutions})".format(
                ignore=" IGNORE" if ignore else "",
                table=table,
                columns=",".join(columns),
                substitutions=",".join(["%s"] * len(columns))),
            rows)
