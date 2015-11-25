/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

/*
 * This module:
 * - contains neighbor switch panel
 * - contains client MACs panel for interface component
 * - Hides link to Software panel
 * - Adds network map panel to device
 */

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
                },
                width: 140
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
                xtype: 'treepanel',
                viewName: 'macs',
                showToolbar: false,
                autoScroll: true,
                rootVisible: false,
                useArrows: true,
                bodyStyle: 'padding: 10px;',
                root: {
                    text: "Root node",
                    expanded: true,
                    children: []
                },
                viewConfig: {
                    enableTextSelection: true,
                },
                tbar: [{
                    text: 'Expand All',
                    scope: 'treepanel',
                    handler: function(){
                        var me = Ext.getCmp('macs_panel'),
                            toolbar = me.down('toolbar');

                        me.getEl().mask('Expanding tree...');
                        toolbar.disable();

                        me.expandAll(function() {
                            me.getEl().unmask();
                            toolbar.enable();
                        });
                    }
                },{
                    text: 'Collapse All',
                    scope: this,
                    handler: function() {
                        var me = Ext.getCmp('macs_panel');
                        var toolbar = me.down('toolbar');

                        toolbar.disable();
                        me.collapseAll(function() {
                            toolbar.enable();
                        });
                    }
                }]
            };

        if (!Ext.get('macs_panel')) {
            target.add(macs);
        }
        Ext.getCmp('macs_panel').getDockedItems()[0].hide();
        get_clientmacs(uid, function(config){
            target.layout.setActiveItem(cardid);
            data = target.layout.activeItem.getRootNode();

            if (data.childNodes){
                data.removeAll();
            }
            if (config){
                target.layout.activeItem.getDockedItems()[0].show();
                for (i in config){
                    data.insertChild(i, config[i]);
                }
            }
            else {
                Ext.getCmp('macs_panel').getEl().mask(_t('No Client MACs') , 'x-mask-msg-noicon');
            }
        });
    }
}]);

/* Panel Override */
Ext.onReady(function(){
    /* Hide Software component for all /Network devices, ZEN-17697 */
    DEVICE_ELEMENTS = "subselecttreepaneldeviceDetailNav"
     Ext.ComponentMgr.onAvailable(DEVICE_ELEMENTS, function(){
        var DEVICE_PANEL = Ext.getCmp(DEVICE_ELEMENTS);
        DEVICE_PANEL.on('afterrender', function() {
            var device_class = Zenoss.env.PARENT_CONTEXT;
            var tree = Ext.getCmp(DEVICE_PANEL.items.items[0].id);
            var items = tree.store.data.items;

            if (device_class.indexOf('/zport/dmd/Devices/Network/') == 0) {
                for (i in items){
                    if (items[i].data.id.match(/software*/)){
                        try {
                            tree.store.remove(items[i]);
                            tree.store.sync();
                        } catch(err){}
                    }
                }
            }
        });
    });


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

})();
