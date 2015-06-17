/*****************************************************************************
 * 
 * Copyright (C) Zenoss, Inc. 2015, all rights reserved.
 * 
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 * 
 ****************************************************************************/


Ext.onReady(function(){

Ext.define('NetworkMapPanel', {
    extend: 'Ext.panel.Panel',
    alias: ['widget.network_map'],
    layout: {
        type: 'fit',
    },
    config: {
        title: 'Network map',
        viewName: 'network_map_view',
    },
    onRender: function () {
        this.callParent();
        window.form_panel.render(this);
    },
    setContext: function(uid) {
        window.form_panel.change_root(uid);
    },
});

Zenoss.nav.appendTo('Device', [{
    id: 'network_map',
    text: _t('Network map'),
    xtype: 'network_map',
    viewName: 'network_map_view',
}]);

});
