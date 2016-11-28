#!/usr/bin/env zendmd
import contextlib
import sys
from ZenPacks.zenoss.Layer2.tests.test_suppression import Stresser
s = Stresser(dmd)


@contextlib.contextmanager
def e(*args, **kwargs):
    s.create_events(*args, **kwargs)
    try:
        yield
    finally:
        s.create_events(*args, clear=True, **kwargs)


def pause(msg):
    # return
    try:
        raw_input("    {}".format(msg))
    except KeyboardInterrupt:
        print
        sys.exit()


print "Configuring zProperties.."

print "  - no suppression: /Test/Layer2/Site-s1"
s1_switch_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s1/Switch")
s1_switch_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s1_switch_dc.setZenProperty("zL2SuppressIfPathsDown", False)
s1_switch_dc.setZenProperty("zL2PotentialRootCause", True)
s1_switch_dc.setZenProperty("zL2Gateways", [])

s1_host_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s1/Host")
s1_host_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s1_host_dc.setZenProperty("zL2SuppressIfPathsDown", False)
s1_host_dc.setZenProperty("zL2PotentialRootCause", False)
s1_host_dc.setZenProperty("zL2Gateways", [])

print "  - non-ping suppression: /Test/Layer2/Site-s2"
s2_switch_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s2/Switch")
s2_switch_dc.setZenProperty("zL2SuppressIfDeviceDown", True)
s2_switch_dc.setZenProperty("zL2SuppressPathsDown", False)
s2_switch_dc.setZenProperty("zL2PotentialRootCause", True)
s2_switch_dc.setZenProperty("zL2Gateways", [])

s2_host_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s2/Host")
s2_host_dc.setZenProperty("zL2SuppressIfDeviceDown", True)
s2_host_dc.setZenProperty("zL2SuppressPathsDown", False)
s2_host_dc.setZenProperty("zL2PotentialRootCause", False)
s2_host_dc.setZenProperty("zL2Gateways", [])

print "  - first-hop suppression: /Test/Layer2/Site-s3"
s3_switch_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s3/Switch")
s3_switch_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s3_switch_dc.setZenProperty("zL2SuppressIfPathsDown", True)
s3_switch_dc.setZenProperty("zL2PotentialRootCause", True)
s3_switch_dc.setZenProperty("zL2Gateways", [])

s3_host_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s3/Host")
s3_host_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s3_host_dc.setZenProperty("zL2SuppressIfPathsDown", True)
s3_host_dc.setZenProperty("zL2PotentialRootCause", False)
s3_host_dc.setZenProperty("zL2Gateways", [])

print "  - multi-hop suppression: /Test/Layer2/Site-s4"
s4_switch_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s4/Switch")
s4_switch_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s4_switch_dc.setZenProperty("zL2SuppressIfPathsDown", True)
s4_switch_dc.setZenProperty("zL2PotentialRootCause", True)
s4_switch_dc.setZenProperty("zL2Gateways", ["s4-gw-a", "s4-gw-b"])

s4_host_dc = dmd.Devices.getOrganizer("/Test/Layer2/Site-s4/Host")
s4_host_dc.setZenProperty("zL2SuppressIfDeviceDown", False)
s4_host_dc.setZenProperty("zL2SuppressIfPathsDown", True)
s4_host_dc.setZenProperty("zL2PotentialRootCause", False)
s4_host_dc.setZenProperty("zL2Gateways", ["s4-gw-a", "s4-gw-b"])

commit()

print
print "Sending events."

if len(sys.argv) > 1 and sys.argv[2] == "function-test":
    s.create_marker_event("-- BEGIN: function-test --")

    # non-ping
    print "  - non-ping"
    s.create_marker_event("non-ping")
    with e(1, filt="s2-host"):                                          # s3 hosts noise
        pause("  0/256: <s2 hosts noise not suppressed>")
        with e(1, ping=True, filt="s2-host"):                           # s2 hosts down
            pause("  0/512: <s2 hosts down not suppressed>")
            with e(1, filt="s2-host"):                                  # s2 hosts noise
                pause("256/512: <s2 hosts noise suppressed>")
            pause("  0/256: <s2 hosts noise cleared>")
        pause("  0/  0: <s2 hosts down cleared>")

    # first-hop
    print "  - first-hop"
    s.create_marker_event("first-hop")
    with e(1, ping=True, filt="s3-rack", side="a"):                     # s3 racks half down
        pause("  0/ 16: <s3 racks (a) down not suppressed>")
        with e(1, ping=True, filt="s3-host"):                           # s3 hosts down
            pause("  0/272: <s3 hosts down not suppressed>")
            with e(1, ping=True, filt="s3-rack", side="b"):             # s3 racks all down
                pause("  0/288: <s3 racks (b) down not suppressed>")
                with e(1, ping=True, filt="s3-host"):                   # s3 hosts down
                    pause("256/288: <s3 hosts down suppressed>")
                pause("  0/ 32: <s3 hosts down cleared>")
            pause("  0/ 16: <s3 racks (b) down cleared>")
    pause("  0/  0: <s3 racks (a) down cleared>")

    # multi-hop
    print "  - multi-hop (rack)"
    s.create_marker_event("multi-hop (rack)")
    with e(1, ping=True, filt="s4-rack", side="a"):                     # s4 racks half down
        pause("  0/ 16: <s4 racks (a) down not suppressed>")
        with e(1, ping=True, filt="s4-host"):                           # s4 hosts down
            pause("  0/272: <s4 hosts down not suppressed>")
            with e(1, ping=True, filt="s4-rack", side="b"):             # s4 racks all down
                pause("  0/288: <s4 racks (b) down not suppressed>")
                with e(1, ping=True, filt="s4-host"):                   # s4 hosts down
                    pause("256/288: <s4 hosts down suppressed>")
                pause("  0/ 32: <s4 hosts down cleared>")
            pause("  0/ 16: <s4 racks (b) down cleared>")
    pause("  0/  0: <s4 racks (a) down cleared>")

    print "  - multi-hop (row)"
    s.create_marker_event("multi-hop (row)")
    with e(1, ping=True, filt="s4-row", side="a"):                      # s4 rows half down
        pause("  0/  4: <s4 rows (a) down not suppressed>")
        with e(1, ping=True, filt="s4-host"):                           # s4 hosts down
            pause("  0/260: <s4 hosts down not suppressed>")
            with e(1, ping=True, filt="s4-row", side="b"):              # s4 rows all down
                pause("  0/264: <s4 rows (b) down not suppressed>")
                with e(1, ping=True, filt="s4-host"):                   # s4 hosts down
                    pause("256/264: <s4 hosts down suppressed>")
                pause("  0/  8: <s4 hosts down cleared>")
            pause("  0/  4: <s4 rows (b) down cleared>")
    pause("  0/  0: <s4 rows (a) down cleared>")

    print "  - multi-hop (core)"
    s.create_marker_event("multi-hop (core)")
    with e(1, ping=True, filt="s4-core", side="a"):                     # s4 cores half down
        pause("  0/  1: <s4 cores (a) down not suppressed>")
        with e(1, ping=True, filt="s4-host"):                           # s4 hosts down
            pause("  0/257: <s4 hosts down not suppressed>")
            with e(1, ping=True, filt="s4-core", side="b"):             # s4 cores all down
                pause("  0/258: <s4 cores (b) down not suppressed>")
                with e(1, ping=True, filt="s4-host"):                   # s4 hosts down
                    pause("256/258: <s4 hosts down suppressed>")
                pause("  0/  2: <s4 hosts down cleared>")
            pause("  0/  1: <s4 cores (b) down cleared>")
    pause("  0/  0: <s4 cores (a) down cleared>")

    print "  - multi-hop (gw)"
    s.create_marker_event("multi-hop (gw)")
    with e(1, ping=True, filt="s4-gw", side="a"):                       # s4 gws half down
        pause("  0/  1: <s4 gws (a) down not suppressed>")
        with e(1, ping=True, filt="s4-host"):                           # s4 hosts down
            pause("  0/257: <s4 hosts down not suppressed>")
            with e(1, ping=True, filt="s4-gw", side="b"):               # s4 gws all down
                pause("  0/258: <s4 gws (b) down not suppressed>")
                with e(1, ping=True, filt="s4-host"):                   # s4 hosts down
                    pause("256/258: <s4 hosts down suppressed>")
                pause("  0/  2: <s4 hosts down cleared>")
            pause("  0/  1: <s4 gws (b) down cleared>")
    pause("  0/  0: <s4 gws (a) down cleared>")

    s.create_marker_event("-- END: function-test --")

    sys.exit()

if len(sys.argv) > 1 and sys.argv[2] == "performance-test":
    for run in range(2):
        # no suppression
        print "  - unsuppressed: ",
        for bit in range(3):
            print "{}.. ".format(bit),
            s.create_events(1, filt="s4-gw-", ping=True, clear=True)
            s.create_events(1, filt="s4-core-", ping=True, clear=True)
            s.create_events(1, filt="s4-row-", ping=True, clear=True)
            s.create_events(1, filt="s4-rack-", ping=True, clear=True)
            s.create_events(1, filt="s1-host-", ping=True)
            s.create_marker_event("counter:none:start")
            s.create_events(15, filt="s1-host-")
            s.create_marker_event("counter:none:end")
        print "clear."
        s.create_events(1, filt="s1-host-", ping=True, clear=True)
        s.create_events(1, filt="s1-host-", clear=True)

        # non-ping suppression
        print "  - non-ping: ",
        for bit in range(3):
            print "{}.. ".format(bit),
            s.create_events(1, filt="s4-gw-", ping=True, clear=True)
            s.create_events(1, filt="s4-core-", ping=True, clear=True)
            s.create_events(1, filt="s4-row-", ping=True, clear=True)
            s.create_events(1, filt="s4-rack-", ping=True, clear=True)
            s.create_events(1, filt="s4-host-", ping=True)
            s.create_marker_event("counter:nonping:start")
            s.create_events(15, filt="s2-host-")
            s.create_marker_event("counter:nonping:end")
        print "clear."
        s.create_events(1, filt="s2-host-", ping=True, clear=True)
        s.create_events(1, filt="s2-host-", clear=True)

        # first-hop suppression
        print "  - first-hop: ",
        for bit in range(3):
            print "{}.. ".format(bit),
            s.create_events(1, filt="s4-gw-", ping=True, clear=True)
            s.create_events(1, filt="s4-core-", ping=True, clear=True)
            s.create_events(1, filt="s4-row-", ping=True, clear=True)
            s.create_events(1, filt="s4-rack-", ping=True)
            s.create_events(1, filt="s4-host-", ping=True, clear=True)
            s.create_marker_event("counter:firsthop:start")
            s.create_events(15, filt="s3-host-", ping=True)
            s.create_marker_event("counter:firsthop:end")
        print "clear."
        s.create_events(1, filt="s3-rack-", ping=True, clear=True)
        s.create_events(1, filt="s3-host-", ping=True, clear=True)

        # multi-hop suppression
        print "  - multi-hop: ",
        for bit in range(3):
            print "{}.. ".format(bit),
            s.create_events(1, filt="s4-gw-", ping=True, clear=True)
            s.create_events(1, filt="s4-core-", ping=True)
            s.create_events(1, filt="s4-row-", ping=True, clear=True)
            s.create_events(1, filt="s4-rack-", ping=True, clear=True)
            s.create_events(1, filt="s4-host-", ping=True, clear=True)
            s.create_marker_event("counter:multihop:start")
            s.create_events(50, filt="s4-host-", ping=True)
            s.create_marker_event("counter:multihop:end")
        print "clear."
        s.create_events(1, filt="s4-core-", ping=True, clear=True)
        s.create_events(1, filt="s4-host-", ping=True, clear=True)

    sys.exit()


if len(sys.argv) > 1 and sys.argv[2] == "paths-test":
    s.create_marker_event("-- BEGIN: paths-test --")
    s.create_events(1)
    s.create_events(1, ping=True, filt="s4-core")
    s.create_events(4, ping=True, filt="s4-host")
    s.create_events(1, ping=True, filt="s4-host", clear=True)
    s.create_events(1, ping=True, filt="s4-core", clear=True)
    s.create_events(1, clear=True)
    s.create_marker_event("-- END: paths-test --")
    sys.exit()

if len(sys.argv) > 1 and sys.argv[2] == "disabled-test":
    for prop in ("zL2SuppressIfDeviceDown", "zL2SuppressIfPathsDown"):
        dmd.Devices.setZenProperty(prop, False)
        for dc in dmd.Devices.getOverriddenObjects(prop):
            dc.deleteZenProperty(prop)

    commit()

    s.create_marker_event("-- BEGIN: disabled-test --")
    for run in range(4):
        s.create_events(1, ping=True)
        s.create_events(1, ping=False)
        s.create_events(1, ping=False, clear=True)
        s.create_events(1, ping=True, clear=True)

    s.create_marker_event("-- END: disabled-test --")
    sys.exit()
