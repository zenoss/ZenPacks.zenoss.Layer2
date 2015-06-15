/*****************************************************************************
 * 
 * Copyright (C) Zenoss, Inc. 2015, all rights reserved.
 * 
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 * 
 ****************************************************************************/


(function () {

Ext.define('NetworkMapPanel', {
    extend: 'Ext.panel.Panel',
    alias: ['widget.network_map'],
    config: {
        title: 'Network map',
        html: 'Hey there!',
        viewName: 'network_map_view',
    },
    setContext: function(uid) {
        console.log('setting context', uid)
        // this._contextUid = uid;
        // this._setSwfContext(this._contextUid);
    },
});

Zenoss.nav.appendTo('Device', [{
    id: 'network_map',
    text: _t('Network map'),
    xtype: 'network_map',
    viewName: 'network_map_view',
}]);

Ext.onReady(function(){
    //render_form(Ext.getCmp('network_map'));
});

}());
