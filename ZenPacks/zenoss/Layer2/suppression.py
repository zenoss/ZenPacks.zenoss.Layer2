##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Event suppression.

Entry point for event suppression. The expected usage is as follows.

    from ZenPacks.zenoss.Layer2 import suppression
    suppressor = suppression.get_suppressor()

    # Assuming "event" is an EventSummaryProxy.
    suppressor.process_event(event)

    # Assuming the event was suppressed.
    event.eventState == STATUS_SUPPRESSED (2)
    event.rootCauses == "gw-a,gw-b"

"""

import collections
import datetime
import time
import types
import sys

from Products.ZenEvents.ZenEventClasses import Status_Ping
from Products.ZenUtils.Utils import convToUnits

from zenoss.protocols.protobufs.zep_pb2 import (
    STATUS_SUPPRESSED,
    SEVERITY_CLEAR, SEVERITY_CRITICAL,
    )

try:
    from networkx import shortest_simple_paths
except ImportError:
    # The networkx version shipped with Zenoss 4 (1.3) doesn't have
    # shortest_simple_paths. So we have a compatible copy of the algorithm
    # locally.
    from .nx.simple_paths import shortest_simple_paths

from . import connections

import logging
LOG = logging.getLogger("zen.Layer2")

from metrology import Metrology
s_meter = Metrology.meter("events-suppressed")

# Default exports.
__all__ = [
    "get_suppressor",
    ]


# Make status checks clearer.
UP, DOWN = True, False

# Make toggle checks clearer.
ENABLED, DISABLED = True, False

# Singleton to keep state for callers who can't keep their own state.
SUPPRESSOR = None

Settings = collections.namedtuple(
    "Settings", [
        "enabled",
        "paths",
        "potential_rc",
        "device",
        ])


def get_suppressor(dmd):
    """Return the global Suppressor singleton."""
    global SUPPRESSOR
    if not SUPPRESSOR:
        SUPPRESSOR = Suppressor(dmd)

    return SUPPRESSOR


class Suppressor(object):
    """Supressor singleton. Get instance using get_suppressor(dmd)."""

    def __init__(self, dmd):
        self.dmd = dmd
        self.layers = ["layer2"]
        self.clear_caches()

    def process_event(self, event):
        """Set event.eventState and event.rootCauses.

        The event argument is expected to be an EventSummaryProxy as is
        passed into the apply method of ZEP (Pre|Post)EventPlugin
        methods.

        The event.eventState value will be set to 2 (suppressed) if the
        event is found to require suppression. It will not be set or
        changed otherwise.

        The event.rootCauses value will always be set to a comma-
        delimited string of device ids that were found to be the root
        caused of the event if event.eventState is set to 2. Otherwise,
        event.rootCauses will not be set.

        """
        device, settings = self.get_device_and_settings(event.device)
        if not device or not settings.enabled:
            return

        device_entity = device.getPrimaryId()

        if event.eventClass == Status_Ping and not event.component:
            if event.severity == SEVERITY_CRITICAL:
                # Ping down. Cache DOWN status.
                self.set_status(device_entity, DOWN)

                # Ping down events get the L2 root cause treatment.
                if settings.paths:
                    root_causes = self.root_causes(device, settings)
                    if root_causes:
                        event.eventState = STATUS_SUPPRESSED
                        event.rootCauses = ",".join(sorted(x.id for x in root_causes))
                        s_meter.mark()

            elif event.severity == SEVERITY_CLEAR:
                # Ping clear. Cache UP status. No suppression necessary
                self.set_status(device_entity, UP)

        # Suppress non-ping events if the device is known to be down.
        elif event.severity > SEVERITY_CLEAR and settings.device is ENABLED:
            if self.get_status(device_entity) is DOWN:
                event.eventState = STATUS_SUPPRESSED
                event.rootCauses = event.device
                s_meter.mark()

    def root_causes(self, device, settings):
        """Return a set() of root cause Device instances.

        The device argument must be a Device instance, and settings must
        be a Settings instance for the device.

        """
        gateways = self.get_gateways(device, settings)
        if not gateways or device in gateways:
            return set()

        # At least one gateway, and all gateways are down? This is a
        # shortcut that allows us to avoid more expensive path walking.
        gateway_entities = [self.to_entity(x) for x in gateways]
        gateway_statuses = [self.get_status(x) for x in gateway_entities]
        if gateway_statuses and UP not in gateway_statuses:
            return set(gateways)

        if any(x._v_multihop for x in gateways):
            # Attempt to find root causes from layer-2 graph.
            return self.l2_root_causes(device, gateways)
        else:
            # The shortcut above was enough to find single-hop root causes.
            return set()

    def get_gateways(self, device, settings):
        """Return a list of gateways (Device instances) for device.

        The device argument must be a Device instance, and settings must
        be a Settings instance for the device.

        If zL2Gateways is set to valid device ids, the devices for those
        ids will be returned. If zL2Gateways is not set, the layer2
        connectivity information in Redis will be used to attempt to
        automatically identify the gateways.

        """
        entity = self.to_entity(device)

        # First check to see if we already have the gateways cached.
        cached_gateways = self.gateways_cache.get(entity)
        if cached_gateways is not None:
            return cached_gateways

        # User configured gateways.
        gateways = device.get_l2_gateways()
        for gateway in gateways:
            # root_causes uses this flag for a significant optimization
            gateway._v_multihop = True

        # Discovered upstream gateways.
        if not gateways and not settings.potential_rc:
            gateways = self.discover_gateways(device)
            for gateway in gateways:
                # root_causes uses this flag for a significant optimization
                gateway._v_multihop = False

        self.gateways_cache.set(entity, gateways)
        return gateways

    def l2_root_causes(self, device, gateways):
        """Return set() of root caused Device instances for device.

        The device argument must be a Device instance, and gateways must
        be a list of gateways (Device instances).

        The returned set of gateways will be Device instances.

        """
        root_causes = set()

        for gateway in gateways:
            for path in self.get_shortest_paths(device, gateway):
                for entity in reversed(path[1:]):
                    if not entity.startswith("/"):
                        # Don't bother checking non-object entities.
                        continue

                    if self.get_status(entity) is DOWN:
                        # Found the closest-to-gateway failure on this path.
                        root_causes.add(entity)
                        break
                else:
                    return set()

        return set(self.to_objs(root_causes))

    # -- Graph Algorithms ----------------------------------------------------

    def discover_gateways(self, device):
        """Return list of gateways for device.

        Each gateway in the list is a Device object. An empty list
        indicates that no devices are known to be connected to device.

        """
        entity = self.to_entity(device)
        visited = collections.deque([entity])
        stack = collections.deque([self.get_neighbors(entity)])

        gateways = []

        while stack:
            neighbors = stack[-1]
            neighbor = next(neighbors, None)
            if not neighbor:
                stack.pop()
                visited.pop()
                continue

            if neighbor in visited:
                continue

            if neighbor.startswith("/"):
                neighbor_obj = self.to_obj(neighbor)
                if neighbor_obj:
                    gateways.append(neighbor_obj)

                continue

            visited.append(neighbor)
            stack.append(self.get_neighbors(neighbor))

        return gateways

    def get_shortest_paths(self, device, gateway):
        """Return list of shortest paths from device to gateway.

        Each path in the list is a list containing entity IDs. The first
        element of the list will be device.getPrimaryId(), and the last will
        be gateway.getPrimaryId().
        
        * Node IDs beginning with a / are a Device.getPrimaryId()
        * Node IDs beginning with a !/ are a DeviceComponent.getPrimaryId()
        * Remaining node IDs are MAC addresses.
        
        An empty list is returned if not paths from device to gateway exist.

        """
        device_entity = self.to_entity(device)
        gateway_entity = self.to_entity(gateway)
        cache_key = (device_entity, gateway_entity)

        cached_paths = self.paths_cache.get(cache_key)
        if cached_paths is not None:
            return cached_paths

        g = self.get_graph(gateway_entity)

        # No paths if the device or gateway isn't in the gateway's graph.
        if device_entity not in g or gateway_entity not in g:
            return []

        shortest_path = None
        shortest_paths = []

        for path in shortest_simple_paths(g, device_entity, gateway_entity):
            path_len = len(path)
            if not shortest_path or path_len <= shortest_path:
                # Interested in all paths the same length as the shortest.
                shortest_path = path_len
                shortest_paths.append(path)
            else:
                # Not interested in paths longer than the shortest.
                break

        self.paths_cache.set(cache_key, shortest_paths)

        return shortest_paths

    # -- Conversions ---------------------------------------------------------

    def to_obj(self, thing):
        """Return ZODB object from any kind of thing."""
        if isinstance(thing, types.StringTypes):
            if thing.startswith("/"):
                try:
                    return self.dmd.getObjByPath(str(thing))
                except Exception:
                    return None
            else:
                return self.dmd.Devices.findDeviceByIdExact(thing)
        else:
            return thing

    def to_objs(self, things):
        """Generate objects for things with missing objects removed."""
        for thing in things:
            obj = self.to_obj(thing)
            if obj:
                yield obj

    def to_entity(self, thing):
        """Return entity (primary URL path) from any kind of thing."""
        if isinstance(thing, types.StringTypes):
            if thing.startswith("/"):
                return thing
            else:
                obj = self.dmd.Devices.findDeviceByIdExact(thing)
                if obj:
                    return obj.getPrimaryId()
                else:
                    return None
        else:
            try:
                return thing.getPrimaryId()
            except AttributeError:
                return None

    # -- Caches --------------------------------------------------------------

    def clear_caches(self):
        """Clear status, neighbors, and paths caches."""
        self.status_cache = ExpiringCache(50)
        self.settings_cache = ExpiringCache(600)
        self.gateways_cache = ExpiringCache(600)
        self.neighbors_cache = ExpiringCache(3300)
        self.paths_cache = ExpiringCache(3300)
        self.graphs_cache = ExpiringCache(3300)

    def get_device_and_settings(self, device_id):
        """Return (device, settings) tuple.

        settings will always be a Settings object. device will be the
        ZODB Device object for device_id if any kind of suppression is
        enabled for the device, otherwise device will be None.

        This is a read-through cache to L2 zProperties. The values will
        be returned from the cache if they haven't expired. They will be
        read from the device and added to the cache otherwise.

        This cache exists to avoid having to load the device, and its
        zL2* zProperty values for every processed event in cases where
        event suppression isn't even enabled.

        """
        device = None
        settings = self.settings_cache.get(device_id)
        if settings is None:
            device = self.to_obj(device_id)
            if device:
                if_paths = device.getProperty("zL2SuppressIfPathsDown")
                if_device = device.getProperty("zL2SuppressIfDeviceDown")
                potential_rc = device.getProperty("zL2PotentialRootCause")

                settings = Settings(
                    enabled=(if_paths or if_device),
                    paths=if_paths,
                    potential_rc=potential_rc,
                    device=if_device)
            else:
                settings = Settings(
                    enabled=False,
                    paths=False,
                    potential_rc=False,
                    device=False)

            self.settings_cache.set(device_id, settings)

        if settings.enabled and not device:
            device = self.to_obj(device_id)

        return device, settings

    def get_status(self, entity):
        """Return the status of entity: True if up, False if down.

        This behaves as a simple read-through cache to the l2 catalog's
        get_status method.

        Cached entries expire after a certain amount of time. See
        status_cache in the clear_caches method for how long.

        """
        status = self.status_cache.get(entity)
        if status is None:
            status = connections.get_status(self.dmd, entity)
            self.set_status(entity, bool(status))

        return status

    def set_status(self, entity, status, asof=None):
        """Set status of entity: True if up, False if down.

        This method is used to warm the status_cache when our caller
        learns about the current status of entities. The complementary
        method, get_status, is a read-through cache. So use of
        set_status is never necessary. It's just an optimization.

        Set the status of entity in status_cache. Entries in this cache
        expire after a certain amount of time. See status_cache in the
        clear_caches method for how long.

        """
        self.status_cache.set(
            key=entity,
            value=status,
            asof=asof,
            set_fn=self.status_set_fn)

    @staticmethod
    def status_set_fn(old_time, old_value, new_time, new_value):
        """Custom set function for status_cache.

        Always sets new_value if we don't have any value currently
        cached. Otherwise only set new value if new time is newer than
        old time.

        """
        if old_time is None or old_time <= 0:
            return (time.time(), new_value)
        elif new_time > old_time:
            return (new_time, new_value)

        return (old_time, old_value)

    def get_neighbors(self, entity):
        """Return iterator of neighbors for entity.

        This behaves as a standard read-through cache to
        connections.get_neighbors().

        Cached entries expire after a certain amount of time. See
        neighbors_cache in the clear_caches method for how long.

        """
        neighbors = self.neighbors_cache.get(entity)
        if neighbors is None:
            neighbors = connections.get_neighbors(entity, self.layers)
            self.neighbors_cache.set(entity, neighbors)

        return iter(neighbors)

    def get_paths(self, source_entity, target_entities):
        """Return list of cached paths from source to targets.

        This is not a read-through cache. None is returned if at least
        one path from source_entity to each of target_entities doesn't
        exist in the cache.

        An empty list return indicates a negative cache. It means that
        the topology was walked from source_entity to target_entities,
        and there were no paths found.

        """
        paths = []
        for target_entity in target_entities:
            target_paths = self.paths_cache.get((source_entity, target_entity))
            if target_paths is None:
                break
            else:
                paths.extend(target_paths)
        else:
            return paths

    def get_graph(self, entity):
        """Return full networkx.Graph starting at entity.

        This behaves as a read-through cache to connections.networkx_graph().
        
        Cached entries expire after a certain amount of time. See
        gateways_cache in the clear_caches method for how long.

        """
        # Maybe a graph is already cached for entity.
        cached_graph = self.graphs_cache.get(entity)
        if cached_graph:
            return cached_graph

        # Maybe entity exists in a graph cached for a different entity.
        for g in self.graphs_cache.values():
            if g and entity in g:
                return g

        # I don't know how big these graphs can get. So it's important to
        # log when we're building graphs, how long it takes, and how much
        # memory caching them is going to consume.
        start = datetime.datetime.now()
        g = connections.networkx_graph(entity, ["layer2"])
        elapsed = datetime.datetime.now() - start

        if g is None:
            nodes = 0
            size = 0
        else:
            nodes = len(g)
            size = sys.getsizeof(g.node) + sys.getsizeof(g.edge)

        LOG.info(
            "cached network graph for %s (%s nodes: %s in %s)",
            entity,
            nodes,
            convToUnits(number=size, divby=1024.0, unitstr="B"),
            elapsed)

        self.graphs_cache.set(entity, g)
        return g


class ExpiringCache(object):
    """Cache where entries expire after a defined duration."""

    def __init__(self, seconds):
        """Initialize cache. Set seconds to seconds before expiration."""
        self.seconds = seconds
        self.data = {}
        self.last_cleanse = time.time()

    def update(self, d, asof=None, set_fn=None):
        """Update the cache from a dict of keys and values.

        Specify asof as a time.time()-style timestamp to update as of
        a certain time. Specify set_fn to customize how each key will
        be updated based on old and new timestamps and values.

        """
        if asof is None:
            asof = time.time()

        for key, value in d.iteritems():
            self.set(key, value, asof=asof, set_fn=set_fn)

    def set(self, key, value, asof=None, set_fn=None):
        """Set key to value in cache.

        Specify asof as a time.time()-style timestamp to update as of
        a certain time. Specify set_fn to customize how each key will
        be updated based on old and new timestamps and values.

        """
        if asof is None:
            asof = time.time()

        old = self.data.get(key, (None, None))

        if set_fn:
            new = set_fn(old[0], old[1], asof, value)
        else:
            new = (asof, value)

        if new != old:
            self.data[key] = new

    def get(self, key, default=None):
        """Return current value of key from cache."""
        now = time.time()
        self.cleanse(now)

        try:
            added, value = self.data[key]
            if added + self.seconds < now:
                self.invalidate(key)
                return default
            else:
                return value
        except KeyError:
            return default

    def invalidate(self, key):
        """Remove key from cache."""
        try:
            del self.data[key]
        except Exception:
            pass

    def cleanse(self, asof):
        """Remove all expired entries from cache."""
        if self.last_cleanse + self.seconds < asof:
            self.last_cleanse = asof
            for key, (added, _) in self.data.items():
                if added + self.seconds < asof:
                    self.invalidate(key)

    def values(self):
        """Generate all values in cache."""
        for key in self.data.iterkeys():
            yield self.get(key)
