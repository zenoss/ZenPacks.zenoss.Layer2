##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenTestCase.BaseTestCase import BaseTestCase


import functools

from zope.component import subscribers
import transaction

from Products.Five import zcml

from Products.ZenUtils.Utils import monkeypatch
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.guid.interfaces import IGUIDManager
from Products.ZenUtils.Utils import unused

from .create_fake_devices import get_device, connect


@monkeypatch('Products.Zuul')
def get_dmd():
    '''
    Retrieve the DMD object. Handle unit test connection oddities.
    This has to be monkeypatched on Products.Zuul instead of
    Products.Zuul.utils because it's already imported into Products.Zuul
    by the time this monkeypatch happens.
    '''
    try:
        # original is injected by the monkeypatch decorator.
        return original()

    except AttributeError:
        connections = transaction.get()._synchronizers.data.values()[:]
        for cxn in connections:
            app = cxn.root()['Application']
            if hasattr(app, 'zport'):
                return app.zport.dmd


def require_impact(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            import ZenPacks.zenoss.Impact
            unused(ZenPacks.zenoss.Impact)
        except ImportError:
            return

        return f(*args, **kwargs)

    return wrapper


def impacts_for(thing):
    """
    Return a two element tuple.

    First element is a list of object ids impacted by thing.
    Second element is a list of object ids impacting thing.
    """
    try:
        from ZenPacks.zenoss.Impact.impactd.interfaces import \
            IRelationshipDataProvider

    except ImportError:
        return ([], [])

    impacted_by = []
    impacting = []

    guid_manager = IGUIDManager(thing.getDmd())
    for subscriber in subscribers([thing], IRelationshipDataProvider):
        for edge in subscriber.getEdges():
            source = guid_manager.getObject(edge.source)
            impacted = guid_manager.getObject(edge.impacted)
            if source == thing:
                impacted_by.append(impacted.id)
            elif impacted == thing:
                impacting.append(source.id)

    return (impacted_by, impacting)


class TestImpact(BaseTestCase):
    _device = None

    def afterSetUp(self):
        super(TestImpact, self).afterSetUp()

        try:
            import ZenPacks.zenoss.DynamicView
            zcml.load_config('configure.zcml', ZenPacks.zenoss.DynamicView)
        except ImportError:
            pass

        try:
            import ZenPacks.zenoss.Impact
            zcml.load_config('meta.zcml', ZenPacks.zenoss.Impact)
            zcml.load_config('configure.zcml', ZenPacks.zenoss.Impact)
        except ImportError:
            pass

        import ZenPacks.zenoss.Layer2
        zcml.load_config('configure.zcml', ZenPacks.zenoss.Layer2)

    @require_impact
    def test_switches_impact_server_and_no_each_other(self):
        dmd = self.dmd
        a = get_device('a', dmd)
        b = get_device('b', dmd)
        s = get_device('s', dmd, '/Server/SSH/Linux')

        c = lambda a, b: connect(a, b, dmd, ['layer2'], update_catalog=True)
        c(a, b)
        c(a, s)
        c(b, s)

        impacts, impacted_by = impacts_for(s)
        self.assertTrue(len(impacts)==2)
        self.assertTrue(len(impacted_by)==0)

        impacts, impacted_by = impacts_for(a)
        self.assertNotIn('b', impacted_by)

        impacts, impacted_by = impacts_for(b)
        self.assertNotIn('a', impacted_by)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestImpact))
    return suite
