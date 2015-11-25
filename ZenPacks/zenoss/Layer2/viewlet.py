##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''

Vievlet that enables loading css registered in configure.zcml like this:

    <browser:viewlet
        name="css-network_map"
        paths="/++resource++ZenPacks_zenoss_Layer2/css/network_map.css"
        for="*"
        weight="20"
        manager="Products.ZenUI3.browser.interfaces.IJavaScriptSrcManager"
        class=".viewlet.StyleSrcBundleViewlet"
        permission="zope2.Public"
        />
'''

from zope.interface import implements

from Products.Five.viewlet.viewlet import ViewletBase
from Products.ZenUI3.browser.interfaces import IJavaScriptBundleViewlet
from Products.ZenUI3.browser.javascript import getVersionedPath

STYLE_TAG_SRC_TEMPLATE = "<link rel='stylesheet' type='text/css' href='%s' />\n"


class StyleSrcBundleViewlet(ViewletBase):
    implements(IJavaScriptBundleViewlet)

    # space delimited string of src paths
    paths = ''
    template = STYLE_TAG_SRC_TEMPLATE

    def can_render(self):
        return True

    def render(self):
        if not self.can_render():
            return ""
        vals = []
        if self.paths:
            for path in self.paths.split():
                vals.append(self.template % getVersionedPath(path))
        css = ''
        if vals:
            css = "".join(vals)
        return css
