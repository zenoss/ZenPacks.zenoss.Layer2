######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################
import sys

from twisted.internet import pollreactor
pollreactor.install()  # to use more than 1024 sockets
from twisted.internet import reactor, udp
from twistedsnmp import agent, agentprotocol, bisectoidstore

from bridge_oids import Network, binary_tree_topology


def main():
    '''
        Create network topology, and then
        print zenbatchdump for modeling those topology,
        if dump is a first argument
        else start simulation.
    '''
    network = Network(binary_tree_topology(deepness=14))
    if len(sys.argv) > 1 and sys.argv[1] == 'dump':
        print network.get_batchdump()
        return
    simulate(
        agents=network.get_oids(),
        port=1611
    )


def simulate(agents, port=161):
    def start():
        for n, (ip, oids) in enumerate(agents.iteritems()):
            print '%s) %s:%s' % (n, ip, port)
            p = udp.Port(
                port,
                agentprotocol.AgentProtocol(
                    snmpVersion='v2c',
                    agent=agent.Agent(
                        dataStore=bisectoidstore.BisectOIDStore(
                            OIDs=oids,
                        ),
                    ),
                    community=None,  # accept all communities
                ),
                ip,
                8192,
                reactor
            )
            p.startListening()
        print 'are simulated.'

    reactor.callWhenRunning(start)
    reactor.run()


if __name__ == '__main__':
    main()
