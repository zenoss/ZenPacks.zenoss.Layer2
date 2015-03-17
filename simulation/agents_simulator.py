######################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################

from twisted.internet import reactor, udp
from twistedsnmp import agent, agentprotocol, bisectoidstore

from bridge_oids import get_host_oids

def main():
    simulate(
        agents={
            '127.0.0.1': get_host_oids('localhost'),
            '127.87.100.1': get_host_oids('Lol' * 5),
        },
        port=1611
    )


def simulate(agents, port=161):
    def start():
        for ip, oids in agents.iteritems():
            print '%s:%s' % (ip, port)
            p = udp.Port(
                port,
                agentprotocol.AgentProtocol(
                    snmpVersion='v2c',
                    agent=agent.Agent(
                        dataStore=bisectoidstore.BisectOIDStore(
                            OIDs=oids,
                        ),
                    ),
                    community=None, # accept all communities
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
