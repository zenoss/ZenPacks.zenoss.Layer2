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


def main():
    simulate(
        agents={
            '127.0.0.1': {
                '.1.3.6.1.2.1.1.1.0': 'Host 1',
            },
            '127.0.0.2': {
                '.1.3.6.1.2.1.1.1.0': 'Host 2',
            },
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
