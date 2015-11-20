##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from collections import defaultdict
from itertools import chain


def contract_edges(nodes, links):
    '''
        Changes graph, so only nodes with important=True are left, and those
        which are unimportant but connect important nodes.
        Also unimportant nodes which connect the set of nodes which was already
        connected will removed.

        For details see docstrings of tests in .tests.test_edge_contraction
    '''
    contractor = EdgeContractor(nodes, links)
    return contractor.get_contracted_graph()


class EdgeContractor(object):
    def __init__(self, nodes, links):
        self.nodes = dict(enumerate(nodes))
        self.links = dict(enumerate(links))
        self.index_incidency()

    def index_incidency(self):
        '''
            On each node add outbound and inbound links indexes
        '''

        for i, link in self.links.iteritems():
            s = self.nodes[link['source']]
            t = self.nodes[link['target']]
            append_incident(s, i, 'outbound')
            append_incident(t, i, 'inbound')
            if not link['directed']:
                append_incident(t, i, 'outbound')
                append_incident(s, i, 'inbound')

    def get_adjacent(self, node_id, direction=None):
        ''' Returns ids of adjacent nodes '''

        if direction is None:
            return (
                self.get_adjacent(node_id, 'inbound')
                | self.get_adjacent(node_id, 'outbound')
            )

        if direction == 'both':
            return (
                self.get_adjacent(node_id, 'inbound')
                & self.get_adjacent(node_id, 'outbound')
            )

        ids = set()
        for e_id in self.nodes[node_id].get(direction, []):
            edge = self.links[e_id]
            ids.add(edge['source'])
            ids.add(edge['target'])

        try:
            ids.remove(node_id)
        except KeyError:
            pass
        return ids

    def has_important_neighbour(self, node_id):
        for i in self.get_adjacent(node_id):
            if self.nodes[i].get('important'):
                return True
        return False

    def get_nodes_to_join(self):
        ''' Return two adjacent unimportant nodes second of which
            is not a neighbour of important node.

            None if there are no such pair.
        '''
        for i, node in self.nodes.iteritems():
            if node.get('important'):
                continue
            i_hin = self.has_important_neighbour(i)
            for j in self.get_adjacent(i, 'both'):
                if self.nodes[j].get('important'):
                    continue
                j_hin = self.has_important_neighbour(j)
                if not i_hin or not j_hin:
                    if i_hin:
                        return (i, j)
                    else:
                        return (j, i)

    def del_link(self, i):
        s = self.links[i]['source']
        t = self.links[i]['target']
        try:
            self.nodes[s]['outbound'].remove(i)
        except ValueError:
            pass
        try:
            self.nodes[t]['inbound'].remove(i)
        except ValueError:
            pass
        if not self.links[i]['directed']:
            try:
                self.nodes[t]['outbound'].remove(i)
            except ValueError:
                pass
            try:
                self.nodes[s]['inbound'].remove(i)
            except ValueError:
                pass

        del self.links[i]

    def join_pair(self, i, j):
        ''' Merge node j onto i and update references

                x - i - j - y
            will become:
                x - i - y

        '''

        del self.nodes[j]  # remove unused node

        for li, l in self.links.items():
            # rereference
            if l['source'] == j:
                l['source'] = i
                append_incident(self.nodes[i], li, 'outbound')
            if l['target'] == j:
                l['target'] = i
                append_incident(self.nodes[i], li, 'inbound')

            # delete links that bound nothing
            if l['source'] == l['target']:
                self.del_link(li)

    def join_unimportant_groups(self):
        ''' Join two unimportant nodes
            one of which is not adjacent to important
        '''
        while True:
            pair = self.get_nodes_to_join()
            if not pair:
                break
            self.join_pair(*pair)

    def prune_leefs(self):
        ''' Remove unimportant nodes which are connected
            only to the one other node
        '''
        for i, node in self.nodes.items():
            if node.get('important'):
                continue

            inbound = node.get('inbound', [])
            outbound = node.get('outbound', [])
            remaining = len(set(inbound) | set(outbound))
            if remaining == 1:
                self.del_link((inbound + outbound)[0])
            if remaining <= 1:
                del self.nodes[i]

        for i, k in self.nodes.items():
            try:
                if (
                    k['inbound'] == k['outbound']
                    and len(k['inbound']) == 1
                    and not k['important']
                ):
                    self.del_link(k['inbound'][0])
                    del self.nodes[i]
            except KeyError:
                continue

    def remove_duplicates(self):
        ''' Remove unimportant nodes which
            connect things other nodes already connect
        '''
        already_connected = set()
        for i, node in self.nodes.items():
            if node.get('important'):
                continue
            adj = (
                frozenset(self.get_adjacent(i, 'inbound')),
                frozenset(self.get_adjacent(i, 'outbound'))
            )
            if adj in already_connected:
                for e_id in (
                    set(node.get('inbound', []))
                    | set(node.get('outbound', []))
                ):
                    self.del_link(e_id)
                del self.nodes[i]
            else:
                already_connected.add(adj)

    def _check_integrity(self):
        '''
            TODO: this is for debug, should not be in production,
            remove when unnecessary
        '''
        for e in self.links.values():
            assert e['source'] in self.nodes
            assert e['target'] in self.nodes

    def get_contracted_graph(self):
        ''' Convert nodes and links from dicts back to lists '''
        self.join_unimportant_groups()
        self.prune_leefs()
        self.remove_duplicates()

        new_nodes = []
        map_names = {}
        for i, (j, n) in enumerate(self.nodes.iteritems()):
            map_names[j] = i

            n.pop('inbound', None)
            n.pop('outbound', None)

            new_nodes.append(n)

        new_links = []
        already_linked = set()
        for l in self.links.values():
            s = map_names[l['source']]
            t = map_names[l['target']]
            if (s, t) not in already_linked:
                l['source'] = s
                l['target'] = t
                new_links.append(l)

            already_linked.add((s, t))

        return dict(
            links=new_links,
            nodes=new_nodes,
        )


def append_incident(d, v, direction):
    if direction in d:
        d[direction].append(v)
    else:
        d[direction] = [v]
