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

    var get_checked_layers = function () {
        // build a comma-separated list of checked layers
        var l = Ext.getCmp('layers_group').getValue();
        var layers = [];
        for(var k in l) {
            if(l[k]) layers.push(l[k]);
        };
        return layers.join(',');
    };

    var refresh_map = function () {
        var params = sidebar.getValues();
        params.layers = get_checked_layers();

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
            params: params,
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
                        items: window.layers_options,
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
