/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

(function(){

get_clientmacs = function(uid, callback) {
    router = Zenoss.remote.DeviceRouter;
    router.getInfo({uid:uid}, function(response){
        callback(response.data.get_clients_links);
    });
}

Zenoss.nav.appendTo('Component', [{
    id: 'clientmacs',
    text: _t('Clients MAC addresses'),
    xtype: 'ClientmacsPanel',
    filterNav: function(navpanel) {
         switch (navpanel.refOwner.componentType) {
            case 'IpInterface': return true;
            default: return false;
         }
    },
    action: function(node, target, combo) {
        var uid = combo.contextUid,
            cardid = 'macs_panel',
            macs = {
                id: cardid,
                xtype: 'panel',
                viewName: 'macs',
                showToolbar: false,
                bodyStyle: 'margin: 10px;'
            };
        if (!Ext.get('macs_panel')) {
            target.add(macs);
        }

        get_clientmacs(uid, function(config){
            target.layout.setActiveItem(cardid);
            target.layout.activeItem.body.update(config);
        });
    }
}]);

})();
