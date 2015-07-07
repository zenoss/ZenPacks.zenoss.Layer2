import json

from ZenPacks.zenoss.Layer2.connections_catalog import CatalogAPI
from ZenPacks.zenoss.Layer2.connections_provider import Connection
from transaction import commit


def main():
    print '''
    Possible actions:
        dump - dumps connections catalog content
        load - loads connections from file to catalog
        clear - clears catalog
    '''
    action = raw_input('action > ')
    {
        'dump': dump,
        'load': load,
        'clear': clear,
    }[action]()


def clear():
    cat = CatalogAPI(zport)
    cat.clear()
    commit()


def dump():
    cat = CatalogAPI(zport)
    res = []
    for i in cat.search():
        res.append(dict(
            (f, getattr(i, f)) for f in cat.fields.keys()
        ))
    filename = raw_input('filename (empty for stdout) > ')
    if filename:
        with open(filename, 'w') as f:
            json.dump(res, f, indent=4)
    else:
        print json.dumps(res, indent=4)


def load():
    filename = raw_input('filename > ')
    print 'Importing', filename
    with open(filename) as f:
        cat = CatalogAPI(zport)
        for connection in json.load(f):
            cat.add_connection(Connection(**connection))
    commit()

if __name__ == '__main__':
    main()
