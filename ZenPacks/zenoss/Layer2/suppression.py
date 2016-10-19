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
import time
import types

from Products.ZenEvents import ZenEventClasses

from zenoss.protocols.protobufs.zep_pb2 import (
    STATUS_SUPPRESSED,
    SEVERITY_CLEAR, SEVERITY_CRITICAL,
    )

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI

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
        self.catalog = CatalogAPI(self.dmd.zport)
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

        device_entity = device.getPrimaryUrlPath()

        if event.eventClass == ZenEventClasses.Status_Ping:
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

        # Attempt to find root causes from layer-2 graph.
        return self.l2_root_causes(device, gateways)

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

        # Discovered upstream gateways.
        if not gateways and not settings.potential_rc:
            gateways = self.discover_gateways(device)

        self.gateways_cache.set(entity, gateways)
        return gateways

    def l2_root_causes(self, device, gateways):
        """Return set() of root caused Device instances for device.

        The device argument must be a Device instance, and gateways must
        be a list of gateways (Device instances).

        The returned set of gateways will be Device instances.

        """
        root_causes = set()

        for path in self.get_shortest_paths(device, gateways):
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

    def get_shortest_paths(self, device, gateways):
        """Return list of shortest paths from device to all gateways.

        Each generated path is a list of device primary URL paths. The
        source device will be the first element in the list, and one of
        targets will be the last element in the the list.

        """
        source_entity = self.to_entity(device)
        target_entities = [self.to_entity(x) for x in gateways]

        # First check to see if we already have the paths cached.
        cached_paths = self.get_paths(source_entity, target_entities)
        if cached_paths is not None:
            return cached_paths

        visited = collections.deque([source_entity])
        stack = collections.deque([self.get_neighbors(source_entity)])

        paths = collections.defaultdict(list)
        shortest_paths = {x: None for x in target_entities}

        def add_path(path, new):
            path_len = len(path)
            gateway = path[-1]
            shortest_path = shortest_paths.get(gateway)
            if not shortest_path or path_len < shortest_path:
                shortest_path = path_len
                shortest_paths[gateway] = shortest_path

            if path_len <= shortest_path:
                paths[gateway].append((new, path))

        while stack:
            neighbors = stack[-1]
            neighbor = next(neighbors, None)

            if not neighbor:
                # No neighbors left. Go back one hop.
                stack.pop()
                visited.pop()
                continue

            if neighbor in visited:
                # Already seen this neighbor. Try the next neighbor.
                continue

            spvs = shortest_paths.values()
            if all(spvs) and len(visited) >= max(spvs):
                # We have at least one path to all gateways, and they're
                # all shorter than the path we're on. Try the next
                # neighbor.
                continue

            cached_paths = self.get_paths(neighbor, target_entities)
            if cached_paths is not None:
                # We know shortest paths from this neighbor to all
                # gateways. Add them to paths, then try the next
                # neighbor.
                visited_path = tuple(visited)
                for cached_path in cached_paths:
                    add_path(visited_path + cached_path, new=False)

                continue

            if neighbor in target_entities:
                # This neighbor is one of the gateways. Add the path,
                # then continue to the next neighbor.
                add_path(tuple(visited) + (neighbor,), new=True)
                continue

            # Go down the path to neighbor.
            visited.append(neighbor)
            stack.append(self.get_neighbors(neighbor))

        paths_to_return = []
        paths_to_cache = collections.defaultdict(list)
        for gw_entity, gw_paths in paths.iteritems():
            for new, path in (x for x in gw_paths if len(x[1]) <= shortest_paths[gw_entity]):
                for partial_path in (path[x:] for x in xrange(len(path))):
                    paths_to_cache[(partial_path[0], gw_entity)].append(partial_path)
                    if not new:
                        break

                paths_to_return.append(path)

        for target_entity in target_entities:
            cache_key = (source_entity, target_entity)
            if cache_key not in paths_to_cache:
                paths_to_cache[cache_key].append([])

        self.paths_cache.update(paths_to_cache)
        return paths_to_return

    # -- Conversions ---------------------------------------------------------

    def to_obj(self, thing):
        """Return ZODB object from any kind of thing."""
        if isinstance(thing, types.StringTypes):
            if thing.startswith("/"):
                try:
                    return self.dmd.getObjByPath(thing)
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
                    return obj.getPrimaryUrlPath()
                else:
                    return None
        else:
            try:
                return thing.getPrimaryUrlPath()
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
            status = self.catalog.get_status(entity)
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

        This behaves as a standard read-through cache to the l2
        catalog's get_reverse_connected method. The only deviation is
        that results prefixed with a ! are stripped because we're only
        interested in MAC adderss or device neighbors.

        Cached entries expire after a certain amount of time. See
        neighbors_cache in the clear_caches method for how long.

        """
        neighbors = self.neighbors_cache.get(entity)
        if neighbors is None:
            neighbors = [
                x for x in self.catalog.get_reverse_connected(
                    entity_id=entity,
                    layers=self.layers)
                if not x.startswith("!")]

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
