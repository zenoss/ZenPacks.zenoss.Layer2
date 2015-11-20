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
