/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

"use strict";

var render_form = function(panel) {
    var show_error = Zenoss.flares.Manager.error;

    var load_filters = function () {
        var fs = Ext.getCmp('filter_select');
        var data = window.filter_type_options[this.value];
        fs.store.loadData(data);
        fs.reset();
    };

    var refresh_map = function () {
        Ext.Ajax.request({
            url: '/zport/dmd/getJSONEdges',
            success: function (response, request) {
                var res = JSON.parse(response.responseText);  
                if(res.error) {
                    return show_error(res.error);
                }
                graph.draw(res);
            },
            failure: show_error,
            params: sidebar.getValues()
        });
    };

    var sidebar = Ext.create('Ext.form.Panel', {
        id: 'network_map_form',
        width: 300,
        bodyPadding: 10,
        frame: true,
        defaultType: 'textfield',
        layout : {
            type: 'vbox',
            padding: 5,
            align: 'stretch',
        },
        items: [
            {
                fieldLabel: 'Device ID',
                name: 'root_id'
            },
            {
                fieldLabel: 'Depth',
                name: 'depth',
                xtype: 'numberfield',
                value: 2,
                maxValue: 10,
                minValue: 1,
            },
            {
                fieldLabel: 'Filter by',
                name: 'filter_type_select',
                id: 'filter_type_select',
                xtype: 'combo',
                forceSelection: true,
                queryMode: 'local',
                store: Ext.create('Ext.data.Store', {
                    fields: ['id', 'label'],
                    data: [
                        {'id': 'Device Class', 'label': 'Device Class'},
                        {'id': 'Location', 'label': 'Location'},
                        {'id': 'Group', 'label': 'Group'},
                        {'id': 'System', 'label': 'System'},
                    ],
                }),
                displayField: 'label',
                valueField: 'id',
                listeners: {
                    select: load_filters,
                },
            },
            {
                fieldLabel: 'Filter',
                name: 'filter',
                id: 'filter_select',
                xtype: 'combo',
                forceSelection: true,
                queryMode: 'local',
                store: Ext.create('Ext.data.Store', {
                    fields: ['data', 'label'],
                    data: [
                        {data: '/zport/dmd/Devices/', label: '/'},
                    ],
                }),
                displayField: 'label',
                valueField: 'data',
            },
            {
                fieldLabel: 'Repulsion',
                name: 'repulsion',
                xtype: 'slider',
                value: 100,
                increment: 10,
                minValue: 10,
                maxValue: 500,
                listeners: {
                    change: function () {
                        graph.set_repulsion(this.getValue());
                    },
                },
            },
            {
                xtype: 'panel',
                title: 'Layers',
                flex: 1,
                overflowY: 'scroll',
                frame: true,
                items: [
                    {
                        xtype: 'checkboxgroup',
                        id: 'layers_group',
                        columns: 1,
                        items: window.filter_type_options['Layers'],
                    },
                ],
            },
            {
                text: 'Refresh map',
                name: 'refresh_button',
                xtype: 'button',
                handler: refresh_map,
            },
            {
                text: 'Center map',
                name: 'center_button',
                xtype: 'button',
                handler: function() {
                    graph.center()
                },
            },
        ],
    });

    console.log(window.filter_type_options['Layers'])

    var map = Ext.create('Ext.panel.Panel', {
        flex: 1,
    });

    var hbox_center_panel = Ext.create('Ext.panel.Panel', {
        layout: {
            type: 'hbox',
            pack: 'start',
            align: 'stretch'
        },
    });
    hbox_center_panel.add(sidebar);
    hbox_center_panel.add(map);
    hbox_center_panel.doLayout();

    panel.removeAll();
    panel.add(hbox_center_panel);
    panel.doLayout();
    
    var graph = graph_renderer('#' + map.body.id);
};
