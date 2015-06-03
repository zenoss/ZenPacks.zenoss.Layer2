/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

"use strict";

var render_form = function(panel) {
    var show_error = Zenoss.flares.Manager.error;

    var get_checked_layers = function () {
        // build a comma-separated list of checked layers
        var l = Ext.getCmp('layers_group').getValue();
        var layers = [];
        for(var k in l) {
            if(l[k]) layers.push(l[k]);
        };
        return layers.join(',');
    };

    var parse_hash = function(hash)
    {
      var res = {};
      var a = hash.split('&');
      for (var i in a)
      {
        var b = a[i].split('=');
        res[decodeURIComponent(b[0])] = decodeURIComponent(b[1]);
      }
      return res;
    }
    var format_hash = function(data) {
       var res = [];
        Object.keys(data).forEach(function(key) {
            res.push(
                encodeURIComponent(key) +
                '=' +
                encodeURIComponent(data[key])
            );
        });
        return res.join('&');
    };


    var refresh_map = function () {
        var params = sidebar.getValues();
        params.layers = get_checked_layers();

        // Updating URL
        var oldToken = Ext.History.getToken();
        var newToken = format_hash({
            root_id: params.root_id,
            depth: params.depth,
            layers: params.layers,
        });
        if (newToken !== oldToken) {
            Ext.History.add(newToken);
        };

        // graph.draw({});

        Ext.Ajax.request({
            url: '/zport/dmd/getJSONEdges',
            success: function (response, request) {
                var res = JSON.parse(response.responseText);
                if(res.error) {
                    return show_error(res.error);
                }
                graph.draw(res);
            },
            failure: function(error) {
                show_error(error);
            },
            params: params,
        });
    };

    var on_hash_change = function(hash) {
        console.log('hash change', hash);
        var params = parse_hash(hash);
        var layers = params.layers.split(',');
        var checkboxval = {}
        for(var i = 0; i < layers.length; i++) {
            checkboxval[layers[i] + '-inputEl'] = layers[i];
        };
        Ext.getCmp('layers_group').setValue(checkboxval);
        Ext.getCmp('sidebar_root_id').setValue(params.root_id);
        Ext.getCmp('sidebar_depth').setValue(params.depth);
        refresh_map();
    };

    Ext.History.init();
    Ext.History.on('change', on_hash_change);

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
                id: 'sidebar_root_id',
                fieldLabel: 'Device ID',
                name: 'root_id'
            },
            {
                id: 'sidebar_depth',
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
                text: 'Apply',
                name: 'refresh_button',
                xtype: 'button',
                handler: refresh_map,
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

    var context_menu = Ext.create('Ext.menu.Menu', {
        height: 58,
        width: 140,
        margin: '0 0 10 0',
        items: [{
            id: 'pin_down',
            xtype: 'menucheckitem',
            text: 'Pin down',
            handler: function() {
                context_menu.data.fixed = this.checked;
            }
        }, {
            text: 'Device info',
            handler: function() {
                console.log(context_menu);
                if(context_menu.data_path) {
                    Zenoss.inspector.show(
                        context_menu.data.path,
                        context_menu.node_x,
                        context_menu.node_y
                    );
                };
            },
        }]
     });

    var click_node = function(data, right, x, y) {
        if(right) {
            Ext.getCmp('pin_down').setChecked(data.fixed);
            context_menu.data = data;
            context_menu.node_x = x;
            context_menu.node_y = y;
            context_menu.showAt([x, y]);
            return;
        }
        Ext.getCmp('sidebar_root_id').setValue(data.path);
        refresh_map();
    };
    var graph = graph_renderer('#' + map.body.id, click_node);
    on_hash_change(Ext.History.getToken());
};
