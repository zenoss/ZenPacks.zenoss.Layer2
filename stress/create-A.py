#!/usr/bin/env zendmd
setLogLevel(20)
from ZenPacks.zenoss.Layer2.tests.test_suppression import Stresser
stresser = Stresser(dmd, starting_mac="01:77:00:00:00:00", starting_ip="127.177.0.0")
devices = stresser.from_counts(sites=4, rows=4, racks=4, hosts=16)
commit()

print
print 'Run "zenmapper run --clear" then "zenmapper run --force"'
