##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from collections import defaultdict

JOIN_TO_SEGMENTS = False


def contract_edges(nodes, links):
    '''
        Changes graph, so only nodes with important=True are left, and those
        which are unimportant but connect important nodes.
        Also unimportant nodes which connect the set of nodes which was already
        connected will removed.

        For details see docstrings of tests in .tests.test_edge_contraction
    '''
    nodes = dict(enumerate(nodes))
    links = dict(enumerate(links))

    def append_incident(d, v):
        if 'incident' in d:
            d['incident'].append(v)
        else:
            d['incident'] = [v]

    for i, link in links.iteritems():
        # add links to incident edges
        s = nodes[link['source']]
        t = nodes[link['target']]
        append_incident(s, i)
        append_incident(t, i)

    def get_adjacent(node_id):
        ''' Returns ids of adjacent nodes '''
        ids = set()
        for e_id in nodes[node_id]['incident']:
            edge = links[e_id]
            ids.add(edge['source'])
            ids.add(edge['target'])

        try:
            ids.remove(node_id)
        except KeyError:
            pass
        return ids

    def has_important_neighbour(node_id):
        for i in get_adjacent(node_id):
            if nodes[i].get('important'):
                return True
        return False

    def get_nodes_to_join():
        ''' Return two adjacent unimportant nodes second of which
            is not a neighbour of important node.

            None if there are no such pair.
        '''
        for i, node in nodes.iteritems():
            if node.get('important'):
                continue
            i_hin = has_important_neighbour(i)
            for j in get_adjacent(i):
                if nodes[j].get('important'):
                    continue
                if JOIN_TO_SEGMENTS:
                    return (i, j)
                j_hin = has_important_neighbour(j)
                if not i_hin or not j_hin:
                    if i_hin:
                        return (i, j)
                    else:
                        return (j, i)

    def del_link(i):
        s = links[i]['source']
        t = links[i]['target']
        try:
            nodes[s]['incident'].remove(i)
        except ValueError:
            pass
        try:
            nodes[t]['incident'].remove(i)
        except ValueError:
            pass
        del links[i]

    def join_pair(i, j):
        for e_id in nodes[j]['incident']:
            # move all edges to i node
            e = links[e_id]
            if e['source'] == j:
                e['source'] = i
            if e['target'] == j:
                e['target'] = i

            if e_id not in nodes[i]['incident']:
                nodes[i]['incident'].append(e_id)

        del nodes[j]  # remove unused node
        for li, l in links.iteritems():
            if l['source'] == l['target']:
                del_link(li)
                break  # should it be only one?

    # join two unimportant nodes one of which are not adjacent to important
    while True:
        pair = get_nodes_to_join()
        if not pair:
            break
        join_pair(*pair)

    # remove unimportant nodes which are connected only to the one other node
    for i, node in nodes.items():
        if node.get('important'):
            continue
        if len(node['incident']) == 1:
            del_link(node['incident'][0])
        if len(node['incident']) < 2:
            del nodes[i]

    # remove unimportant nodes which connect things other nodes already connect
    if not JOIN_TO_SEGMENTS:
        already_connected = set()
        for i, node in nodes.items():
            if node.get('important'):
                continue
            adj = frozenset(get_adjacent(i))
            if adj in already_connected:
                # copy, because number of incidents will decrease
                # when link is removed
                for e_id in node['incident'][:]:
                    del_link(e_id)
                del nodes[i]
                continue
            already_connected.add(adj)

    # Convert nodes and links from dicts back to lists
    new_nodes = []
    map_names = {}
    for i, (j, n) in enumerate(nodes.iteritems()):
        map_names[j] = i
        try:
            del n['incident']
        except KeyError:
            pass
        new_nodes.append(n)

    new_links = []
    already_linked = set()
    for l in links.values():
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
