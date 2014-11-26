/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

(function(){

var ZC = Ext.ns('Zenoss.component');
ZC.registerName('NeighborSwitch', _t('Neighbor Switch'), _t('Neighbor Switches'));


/* NeighborSwitch */
ZC.NeighborSwitchPanel = Ext.extend(ZC.ComponentGridPanel, {
    subComponentGridPanel: false,

    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            autoExpandColumn: 'name',
            componentType: 'NeighborSwitch',
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'severity'},
                {name: 'status'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'},
                {name: 'description'},
                {name: 'ip_address_device'},
                {name: 'device_port'},
                {name: 'native_vlan'},
                {name: 'location'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name')
            },{
                id: 'ip_address_device',
                dataIndex: 'ip_address_device',
                header: _t('IP Address'),
                renderer: function(v) {
                    // The value is returned in link format in details, but
                    // it should be rendered so that html is not escaped.
                    return v;
                }
            // },{
            //     id: 'description',
            //     dataIndex: 'description',
            //     header: _t('Description'),
            //     width: 150
            },{
                id: 'device_port',
                dataIndex: 'device_port',
                header: _t('Device Port'),
                width: 120
            },{
                id: 'native_vlan',
                dataIndex: 'native_vlan',
                header: _t('VLAN'),
                width: 50
            },{
                id: 'location',
                dataIndex: 'location',
                header: _t('Physical Location'),
                width: 150
            },{

                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                width: 60
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 60
            }]
        });
        ZC.NeighborSwitchPanel.superclass.constructor.call(this, config);
    }
});
Ext.reg('NeighborSwitchPanel', ZC.NeighborSwitchPanel);


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

            case 'CiscoEthernetInterface': return true;
            case 'CiscoInterface': return true;
            case 'CiscoPortChannel': return true;
            case 'CiscoVLAN': return true;

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
