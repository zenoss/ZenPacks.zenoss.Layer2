##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Multi-Origin Redis Undirected Graph.

This module contains a Redis implementation of an undirected graph. An
important feature of this implementation is that it allows many
uncoordinated "origins" of graph information. Data from the origins is
kept separate so that it can be cleared and replaced without damaging
any information provided by other origins. However, when the graph is
queried, the information from all origins is combined into a
comprehensive result.

The Origin class must be used to "write" to the graph, and the Graph
class must be used to read the graph.

The Redis keys and values look like this.

    # Each origin (i.e. abc) stores its checksum here. (HASHMAP)
    x:origins:
        abc: 2016-11-18 16:07:32
        xyz: 2016-11-17 09:12:07

    ---

    # Each origin (i.e. abc) stores all layers it originates here. (SET)
    x:origins:abc:layers
        - layer2
        - layer3
        - vlan51

    # All layers with tracking of originators. (HASHMAP)
    x:layers:
        layer2: [abc, xyz]
        layer3: [abc, xyz]
        vlan51: [abc]
        ciscoucs: [xyz]

    ---

    # Each origin (i.e. abc) stores all edges it originates here. (HASHMAP)
    x:origins:abc:edges
        /a/b/c:layer2: [/x/y/z]
        /x/y/z:layer2: [/a/b/c]

    # All edges with tracking of originators. (HASHMAP)
    x:edges:/a/b/c:layer2
        /x/y/z: [abc, xyz]

"""

# stdlib imports
import collections
import itertools
import json
import os

# third-party imports
import networkx
import redis

# default exports
__all__ = (
    "Graph",
    "Origin",
    )

# constants
ORIGINS_KEY = "origins"
LAYERS_KEY = "layers"
EDGES_KEY = "edges"

# module caches
REDIS = None


class Graph(object):
    """Undirected graph of edges from all origins.

    This class is used to read information from the graph, and perform
    global operations on the graph such as clear and compact. See the
    Origin class for adding  information to the graph.

    """

    def __init__(self, namespace):
        """Initialize a new Graph.

        The namespace argument is a mechanism for separating the graph's
        data from other Redis data in the same Redis database. Though
        you should really be using a separate Redis database for this.

        """
        self.namespace = namespace
        self.redis = discover_redis()

    def ns_key(self, *args):
        """Return a Redis key in this graph's namespace."""
        return "{}:{}".format(self.namespace, ":".join(args))

    def get_layers(self):
        """Return set of all layers in the graph."""
        return set(self.redis.hkeys(self.ns_key(LAYERS_KEY)))

    def get_edges(self, node, layers):
        """Return list of (source, target, layers) edge tupes.

        The source of each edge will be node. Only edges with one of the
        layers listed in the layers argument will be returned.

        """
        layers = sorted(layers)

        pipe = PipelineTracker(self.redis)
        for layer in layers:
            pipe(layer, "HKEYS", self.ns_key(EDGES_KEY, node, layer))

        edges = collections.defaultdict(set)
        for layer, targets in pipe.execute().iteritems():
            for target in targets:
                edges[(node, target)].add(layer)

        return [(s, t, l) for (s, t), l in edges.iteritems()]

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

    def clear(self):
        """Clear the Redis database: FLUSHDB."""
        self.redis.flushdb()

    def compact(self, origins):
        """Clear origins not listed in origins."""
        all_origins = set(self.redis.hkeys(self.ns_key(ORIGINS_KEY)))
        for garbage_origin in all_origins.difference(origins):
            Origin(self.namespace, garbage_origin).clear()


class Origin(object):
    """Source of information for a graph.

    This class is used to add information such as edges to the graph.
    The Origin class is separate from Graph so that attribution of the
    graph's information can be retained. This is important because the
    use case is that an Origin is frequently replacing all edges it
    originated with all new edges. This needs to be done in a way that
    is non-destructive to information provided by other origins.

    """

    def __init__(self, namespace, key):
        """Initialize a new Origin.

        The namespace argument is a mechanism for separating the graph's
        data from other Redis data in the same Redis database. Though
        you should really be using a separate Redis database for this.

        The key argument is a unique identifier for the origin.

        """
        self.namespace = namespace
        self.key = key
        self.redis = discover_redis()

    def ns_key(self, *args):
        """Return a Redis key in this origin's graph namespace."""
        return "{}:{}".format(self.namespace, ":".join(args))

    def origin_key(self, *args):
        """Return a Redis key in this origin's namespace."""
        return "{}:{}:{}:{}".format(
            self.namespace,
            ORIGINS_KEY,
            self.key,
            ":".join(args))

    def get_checksum(self):
        """Return currently stored checksum for this origin."""
        return self.redis.hget(self.ns_key(ORIGINS_KEY), self.key)

    def set_checksum(self, checksum):
        return self.redis.hset(self.ns_key(ORIGINS_KEY), self.key, checksum)

    def add_edges(self, edges, checksum):
        """Add list of (source, target, layers) edge triples.

        The source and target of each edge must be strings, and layers
        must be a list, tuple, or set.

        The following Redis commands are used to add all edges. All read
        operations are pipelined together, then all write commands are
        pipelined together. This allows all edges to be added in only
        two round-trips to the Redis server.

        Redis commands:

            -- Get current NS layer values.
            --  (only for unique layers in <edges>)
            HMGET <ns>:LAYERS_KEY <layers>

            -- Get current NS edge values.
            --  (for each node/layer combination in <edges>)
            HMGET <ns>:EDGES_KEY:<source>:<layer> <targets>

            -- Update our checksum.
            --  (key is used for compaction)
            --  (value is used to avoid future unnecessary updates)
            HSET <ns>:ORIGINS_KEY <self.key> <checksum>

            -- Update NS layer values with <self.key> added to origins lists.
            HMSET <ns>:LAYERS_KEY <layers-map>

            -- Update NS edges values with <self.key> added to origins lists.
            HMSET <ns>:EDGES_KEY:<source>:<layer> <targets-map>

            -- Register our NS layers so they can be cleaned up later.
            SADD <ns>:ORIGINS_KEY:<self.key>:LAYERS_KEY <layers>

            -- Register our NS edges so they can be cleaned up later.
            --  (for each node/layer combination in <edges>)
            SADD <ns>:ORIGINS_KEY:<self.key>:EDGES_KEY:<source>:<layer> <targets>

            -- Register our origin edges keys so they can be cleaned up later.
            HMSET <ns>:ORIGINS_KEY:<self.key>:EDGES_KEY <edges-map>

        """
        all_layers = set()

        # tbsbl = targets by source by layer
        tbsbl = collections.defaultdict(        # sources
            lambda: collections.defaultdict(    # layers
                set))                           # targets

        for source, target, layers in edges:
            if not layers:
                # every edge needs at least one layer.
                continue

            all_layers.update(layers)
            for layer in layers:
                tbsbl[source][layer].add(target)
                tbsbl[target][layer].add(source)

        if not all_layers:
            # no edges, or no edges with at least one layer.
            self.set_checksum(checksum)
            return

        # perform all requests in one pipe
        pipe = PipelineTracker(self.redis)

        # request existing layer data
        pipe(
            "ns_layers_jsons",
            "HMGET", self.ns_key(LAYERS_KEY), *sorted(all_layers))

        # request existing edge data
        for source, layers in tbsbl.iteritems():
            for layer, targets in layers.iteritems():
                pipe(
                    (source, layer),
                    "HMGET",
                    self.ns_key(EDGES_KEY, source, layer),
                    *targets)

        # execute all requests at once
        results = pipe.execute()

        # perform all writes in one pipe
        pipe = PipelineTracker(self.redis)

        # update our checksum
        pipe(
            "set_checksum",
            "HSET", self.ns_key(ORIGINS_KEY), self.key, checksum)

        # merge our layers into NS layers
        ns_layers_map = {}
        ns_layers_jsons = results["ns_layers_jsons"]
        for i, ns_layer_json in enumerate(ns_layers_jsons):
            layer = sorted(all_layers)[i]
            if not ns_layer_json:
                ns_layers_map[layer] = [self.key]
            else:
                ns_layer_origins = from_json(ns_layer_json, [])
                if self.key not in ns_layer_origins:
                    ns_layer_origins.append(self.key)
                    ns_layers_map[layer] = ns_layer_origins

        if ns_layers_map:
            pipe(
                "merge_layers",
                "HMSET", self.ns_key(LAYERS_KEY), json_values(ns_layers_map))

        # record layer keys in our LAYERS_KEY set with one SADD
        pipe("add_layers", "SADD", self.origin_key(LAYERS_KEY), *all_layers)

        # merge our edges into NS edge data
        for source, layers in tbsbl.iteritems():
            for layer, targets in layers.iteritems():
                targets_map = {}
                targets_jsons = results[(source, layer)]
                for i, target_json in enumerate(targets_jsons):
                    target = sorted(targets)[i]
                    if not target_json:
                        targets_map[target] = [self.key]
                    else:
                        target_origins = from_json(target_json, [])
                        if self.key not in target_origins:
                            target_origins.append(self.key)
                            targets_map[target] = target_origins

                if targets_map:
                    pipe(
                        "merge_edges_{}_{}".format(source, layer),
                        "HMSET",
                        self.ns_key(EDGES_KEY, source, layer),
                        json_values(targets_map))

        pipe(
            "add_edges",
            "HMSET",
            self.origin_key(EDGES_KEY), {
                ":".join((source, layer)): json.dumps(list(targets_set))
                for source, source_data in tbsbl.items()
                for layer, targets_set in source_data.items()})

        # execute all writes at once
        pipe.execute()

    def clear(self):
        """Remove this origin and its data from the graph.

        Redis commands:

            -- Check if we're already an origin.
            HGET <ns>:ORIGINS_KEY:<self.key>

            -- Get set of layers we originated.
            SMEMBERS <ns>:ORIGINS_KEY:<self.key>:LAYERS_KEY

            -- Get map of <source>:<layer> to <targets> we originated.
            HGETALL <ns>:ORIGINS_KEY:<self.key>:EDGES_KEY

            -- Get NS layer values for layers we originated.
            HMGET <ns>:LAYERS_KEY <originated-layers>

            -- Get NS edge values for edges we originated.
            --  (for each <source>:<layer> to <targets> combination)
            HMGET <ns>:EDGES_KEY:<source>:<layer> <targets>

            -- Remove our checksum.
            HDEL <ns>:ORIGINS_KEY <self.key>

            -- Remove our layers and edges registrations. (in one DEL)
            DEL <ns>:ORIGINS_KEY:<self.key>:LAYERS_KEY
                <ns>:ORIGINS_KEY:<self.key>:EDGES_KEY

            -- Remove <self.key> from NS layers.
            HMSET <ns>:LAYERS_KEY <cleaned-layers-map>

            -- Remove <self.key> from NS edges.
            --  (for each <source>:<layer> combination)
            HMSET <ns>:EDGES_KEY:<source>:<target> <cleaned-targets-map>

        """
        # start 1st read pipeline
        pipe = self.redis.pipeline()
        pipe.hget(self.ns_key(ORIGINS_KEY), self.key)
        pipe.smembers(self.origin_key(LAYERS_KEY))
        pipe.hgetall(self.origin_key(EDGES_KEY))
        checksum, o_layers, o_edges_map = pipe.execute()

        # start 2nd read pipeline
        pipe = PipelineTracker(self.redis)

        if o_layers:
            pipe(
                "ns_layers_jsons",
                "HMGET", self.ns_key(LAYERS_KEY), *o_layers)

        for source_layer, targets_json in o_edges_map.iteritems():
            pipe(
                source_layer,
                "HMGET",
                self.ns_key(EDGES_KEY, source_layer),
                *from_json(targets_json, []))

        # execute 2nd read pipeline
        results = pipe.execute()

        # create layers_map with ourself removed from origins
        ns_layers_map = {}
        ns_layers_jsons = results.get("ns_layers_jsons", [])
        for i, layer in enumerate(o_layers):
            layer_origins = from_json(ns_layers_jsons[i], [])
            ns_layers_map[layer] = [
                x for x in layer_origins
                if x != self.key]

        # create edges_map with ourself removed from origins
        ns_edges_map = {}
        for i, (source_layer, targets_json) in enumerate(o_edges_map.iteritems()):
            ns_edges_map[source_layer] = {}
            targets = from_json(targets_json, [])
            targets_origin_jsons = results[source_layer]
            for j, target in enumerate(targets):
                target_origins = from_json(targets_origin_jsons[j], [])
                ns_edges_map[source_layer][target] = [
                    x for x in target_origins
                    if x != self.key]

        # start write pipeline
        pipe = PipelineTracker(self.redis)

        # delete ourself from the origins registry
        if checksum:
            pipe("delete_checksum", "HDEL", self.ns_key(ORIGINS_KEY), self.key)

        # delete our layers and edges keys
        keys_to_delete = []
        if o_layers:
            keys_to_delete.append(self.origin_key(LAYERS_KEY))

        if o_edges_map:
            keys_to_delete.append(self.origin_key(EDGES_KEY))

        if keys_to_delete:
            pipe("delete_keys", "DEL", *keys_to_delete)

        # remove ourself from layers
        hmclear(pipe, self.ns_key(LAYERS_KEY), ns_layers_map)

        # remove ourself from edges
        for source_layer, targets_map in ns_edges_map.iteritems():
            hmclear(pipe, self.ns_key(EDGES_KEY, source_layer), targets_map)

        # execute write pipeline
        pipe.execute()


class PipelineTracker(object):
    """Convenience wrapper around a Redis pipeline.

    * Results can are accessible by key instead of index.
    * Pipelines with no commands don't round-trip to Redis.
    * Pipelines with a single command don't incur pipeline overhead.
    * Pipelines with zero commands have no overhead.

    """

    def __init__(self, redis):
        """Initialize a PipelineTracker."""
        self.redis = redis
        self.command_counter = 0
        self.command_indexes = {}
        self.command_tuples = []

    def __call__(self, key, command, *args):
        """Add command to pipeline by key."""
        self.command_tuples.append((command, args))
        self.command_indexes[key] = self.command_counter
        self.command_counter += 1

    def execute(self):
        """Return map of key to result after executing pipeline."""
        if self.command_counter == 1:
            for command, args in self.command_tuples:
                results = [self.dispatch(self.redis, command, args)]

        elif self.command_counter > 1:
            pipeline = self.redis.pipeline()
            for command, args in self.command_tuples:
                self.dispatch(pipeline, command, args)

            results = pipeline.execute()

        return {
            key: results[idx]
            for key, idx in self.command_indexes.iteritems()}

    def dispatch(self, dispatcher, command, args):
        """Correctly dispatch command to the dispatcher.

        This method exists solely to consolidate special command
        parameter handling into a single place. For now it looks like we
        only need special handling for HMSET because we want to use a
        dict as its second argument.

        """
        if command == "HMSET":
            return dispatcher.hmset(*args)
        else:
            return dispatcher.execute_command(command, *args)


def discover_redis():
    """Return a StrictRedis appropriate for the environment."""
    global REDIS
    if not REDIS:
        REDIS = redis.StrictRedis.from_url(discover_redis_url())

    return REDIS


def discover_redis_url():
    """Return a Redis URL appropriate for the environment."""
    if os.environ.get("CONTROLPLANE"):
        # Zenoss 5 running under serviced.
        return "redis://localhost:6379/1"

    # Zenoss 4: User has specified Redis URL via environment variable.
    env_redis_url = os.environ.get("REDIS_URL")
    if env_redis_url:
        return env_redis_url

    # Zenoss 4: Assume Redis is running on localhost:16379.
    return "redis://localhost:16379/1"


def json_values(mapping):
    """Return mapping with JSON-encoded values."""
    return {k: json.dumps(v) for k, v in mapping.iteritems()}


def from_json(json_string, default=None):
    """Return Python object from JSON string or default if not possible."""
    try:
        return json.loads(json_string)
    except Exception:
        return default


def hmclear(pipe, key, mapping):
    """HMSET key with non-empty values in mapping. HDEL the rest.

    This is used when clearing origins because we want to delete hashmap
    keys in cases where there are no longer any origins providing the
    key.

    The pipe argument must be a PipelineTracker. Zero or one HMSET and
    HDEL commands will be added to the pipe, but it won't be executed.
    It is the caller's responsibility to execute the pipe.

    """
    to_hmset, to_hdel = {}, []
    for k, v in mapping.iteritems():
        if v:
            to_hmset[k] = json.dumps(v)
        else:
            to_hdel.append(k)

    if to_hmset:
        pipe("remove_from_{}".format(key), "HMSET", key, to_hmset)

    if to_hdel:
        pipe("delete_from_{}".format(key), "HDEL", key, *to_hdel)
