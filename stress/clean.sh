#!/bin/sh
# echo "Clearing zredis.."
# zredis stop
# rm -f /opt/zenoss/var/zredis.rdb
# zredis start

# echo "Clearing RabbitMQ.."
# sudo rabbitmqctl delete_vhost /zenoss
# sudo rabbitmqctl add_vhost /zenoss
# sudo rabbitmqctl set_permissions -p /zenoss zenoss '.*' '.*' '.*'

# echo "Clearing zeneventserver.."
# zeneventserver stop
# zeneventserver-create-db --dbtype=mysql --force
# zeneventserver start

# echo "Rebuilding Layer2 catalog.."
# zenmapper run --force

# sudo rabbitmqctl -p /zenoss list_queues

# read -p "<enter> if queue is empty, <ctrl-c> otherwise."
# ./create-events.py performance-test
# sudo rabbitmqctl -p /zenoss list_queues
# zeneventd run 2>&1 | tee zeneventd.run
