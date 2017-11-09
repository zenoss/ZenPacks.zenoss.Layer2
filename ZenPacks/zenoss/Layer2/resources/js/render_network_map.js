/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, 2015 all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

/*
 * This file contains code to render network map panel and it's controls, and to
 * query backend for network map graph. When map graph is received
 * it uses graph_renderer.js to actually render network map.
 */

"use strict";

(function(){
    window.form_panel = {};

    var show_error = Zenoss.flares.Manager.error,
        show_warning = Zenoss.flares.Manager.warning;

    var get_checked_layers = function () {
        // build a comma-separated list of checked layers
        var records = Ext.getCmp('layers_group').getView().getChecked(),
            layers = [];

        Ext.Array.each(records, function(rec){
            layers.push(rec.get('value'));
        });

        return layers.join(',');
    };

    var format_layers_data = function(checked_data) {
        var vlans = [],
            vxlans = [],
            obj = {},
            res = {
                "text": ".",
                "expanded": true,
                "children": []
            };

        Ext.Array.each(layers_options, function(rec){
            obj = {
                "text": rec.boxLabel,
                "value": rec.inputValue,
                "id": rec.id,
                "leaf": true,
                "checked": (checked_data.indexOf(rec.inputValue) > -1 || checked_data == '')
            }

            if (rec.boxLabel.indexOf('vlan') == 0) {
                obj.text = obj.text.replace(/vlan/gi, '');
                obj.checked = (checked_data == '') ? false : obj.checked,
                vlans.push(obj);
            } else if (rec.boxLabel.indexOf('vxlan') == 0) {
                obj.checked = (checked_data == '') ? false : obj.checked,
                obj.text = obj.text.replace(/vxlan/gi, '');
                vxlans.push(obj);
            } else {
                res.children.push(obj);
            }
        });

        if (vlans.length)
            res.children.push({
                "text": "VLANs",
                "children": vlans
            });

        if (vxlans.length)
            res.children.push({
                "text": "VXLANs",
                "children": vxlans
            });

        return res;
    }

    var navigate_node = function(data, blank) {
        if(
            (data.path.indexOf('/zport/dmd/Devices/') == 0) ||
            (data.path.indexOf('/zport/dmd/Networks/') == 0)
        ) {
            window.open(data.path, blank);
        } else {
            if(data.path.indexOf('/zport/dmd/IPv6Networks/') == 0) {
                window.open(
                    '/zport/dmd/networks#ipv6networks:' +
                    data.path.replace(/\//g, '.'),
                    blank
                );
            }
        };
    };

    var click_node = function(data, right, x, y) {
        if(right) {
            show_context_menu(data, x, y, refresh_map);
        } else {
            navigate_node(data);
        };
    };

    var layers_options;
    var on_layers_loaded = function (callback) {
        if (typeof layers_options === 'undefined') {
            Ext.Ajax.request({
                url: '/zport/dmd/getNetworkLayersList',
                success: function (response, request) {
                    layers_options = JSON.parse(response.responseText);
                    callback();
                },
                failure: function(error) {
                    show_error(error);
                }
            });
        } else {
            callback(); // we already have the data
        };
    };

    var choose_colors = function(graph) {
        // * Choose colors for graph
        var i, layers, color;
        for(i = 0; i<graph.links.length; i++) {
            layers = graph.links[i].color;
            graph.links[i].layers = layers;

            color = 'gray';
            if (layers.indexOf('layer3') > -1) color = 'blue';
            if (layers.indexOf('layer2') > -1) color = 'green';
            for(var j=0; j<layers.length; j++) {
                if(layers[j].indexOf('vlan') == 0) color = 'orange';
            }
            graph.links[i].color = color;
        };
    };

    var refresh_map = function () {
        var params = sidebar.getValues();

        if (!params.root_id) return;

        params.layers = get_checked_layers();

        Ext.Ajax.request({
            url: '/zport/dmd/getJSONEdges',
            timeout: 180000,
            success: function (response, request) {
                var res = JSON.parse(response.responseText);
                if(res.error) {
                    return show_error(res.error);
                }
                var graph = graph_renderer('#' + map.body.id, click_node);
                choose_colors(res);
                graph.draw(res);
            },
            failure: function(error) {
                if(error.statusText) {
                    show_error(error.statusText);
                } else {
                    show_error(error);
                }
            },
            params: params,
        });
    };

    var get_scope = function() {
        if (location.pathname.endswith("/dmd/networkMap")) {
            return "global";
        } else if (location.hash.startswith("#deviceDetailNav:network_map")) {
            return "device";
        }
    };

    var set_sidebar_from_hash = function(hash) {
        if (hash === null) hash = "";

        var layers = [];

        var parts = hash.split('&');
        for (var i in parts) {
            var kv = parts[i].split('=');
            var k = decodeURIComponent(kv[0]);

            if (kv[1] !== undefined) {
                var v = decodeURIComponent(kv[1]);
            } else {
                continue;
            }

            switch (k) {
                case "root_id":
                    Ext.getCmp("sidebar_root_id").setValue(v);
                    break;
                case "layers":
                    layers = v.split(',');
                    break;
                case "depth":
                    Ext.getCmp("sidebar_depth").setValue(v);
                    break;
                case "macs":
                    Ext.getCmp("sidebar_macs").setValue(v);
                    break;
                case "dangling":
                    Ext.getCmp("sidebar_dangling").setValue(v);
                    break;
            }
        }

        on_layers_loaded(function () {
            Ext.getCmp('layers_group').store.setRootNode(format_layers_data(layers));
        });
    }

    var get_hash_from_sidebar = function() {
        var scope = get_scope();
        var hash_parts = null;

        if (scope == "global") {
            var hash_parts = [];
        } else if (scope == "device") {
            var hash_parts = ['deviceDetailNav:network_map'];
        } else {
            return;
        }

        var sidebar_data = Ext.getCmp("network_map_form").getValues();

        var params = {
            root_id: sidebar_data.root_id,
            depth: sidebar_data.depth,
            layers: get_checked_layers(),
            macs: sidebar_data.macs,
            dangling: sidebar_data.dangling
        };

        Object.keys(params).forEach(function(key) {
            if (params[key] !== undefined) {
                hash_parts.push(
                    encodeURIComponent(key) +
                    '=' +
                    encodeURIComponent(params[key])
                );
            }
        });

        return hash_parts.join('&');
    };

    var on_hash_change = function(hash) {
        var scope = get_scope();
        if (!scope) return;

        set_sidebar_from_hash(hash);
        refresh_map();
    };

    var apply = function(params) {
        var hash = get_hash_from_sidebar();
        if (hash) Ext.History.add(hash);
    }

    window.form_panel.change_root = function(new_id) {
        var sidebar_root_id = Ext.getCmp('sidebar_root_id');

        if (sidebar_root_id.getValue() != new_id) {
            sidebar_root_id.setValue(new_id);
            Ext.History.add(get_hash_from_sidebar());
        }
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
                id: 'sidebar_root_id_label',
                name: 'root_id_label',
                value: 'Root device or component',
                xtype: 'displayfield'
            }, {
                id: 'sidebar_root_id',
                fieldLabel: 'Device ID',
                name: 'root_id',
                xtype: 'combo',
                valueField: 'name',
                displayField: 'name',
                store: new Ext.data.DirectStore({
                    directFn: Zenoss.remote.DeviceRouter.getDeviceUuidsByName,
                    root: 'data',
                    model: 'Zenoss.model.BasicUUID',
                    remoteFilter: true
                }),
                minChars: 3,
                typeAhead: false,
                hideLabel: true,
                hideTrigger: true,
                listConfig: {
                    loadingText: 'Searching...',
                    emptyText: 'No matching devices found.',
                },
                pageSize: 10
            }, {
                id: 'sidebar_depth',
                fieldLabel: 'Maximum hops from root',
                labelWidth: 180,
                name: 'depth',
                xtype: 'numberfield',
                value: 3,
                maxValue: 15,
                minValue: 1
            }, {
                id: 'sidebar_macs',
                fieldLabel: 'Show MAC addresses',
                labelWidth: 180,
                name: 'macs',
                xtype: 'checkbox',
                checked: false
            }, {
                id: 'sidebar_dangling',
                fieldLabel: 'Show dangling connectors',
                labelWidth: 180,
                name: 'dangling',
                xtype: 'checkbox',
                checked: false
            }, {
                xtype: 'treepanel',
                id: 'layers_group',
                store: new Ext.data.TreeStore({
                    proxy: {
                        type: 'memory'
                    },
                    root: format_layers_data([]),
                    folderSort: true,
                    model: new Ext.define('Layer', {
                        extend: 'Ext.data.Model',
                        fields: [
                            {name: 'id', type: 'string'},
                            {name: 'text', type: 'string'},
                            {name: 'value', type: 'string'}
                        ]
                    })
                }),
                title: 'Layers',
                flex: 1,
                overflowY: 'scroll',
                frame: true,
                rootVisible: false,
                displayField: 'text',
                useArrows: true
            }, {
                text: 'Apply',
                name: 'refresh_button',
                xtype: 'button',
                handler: apply
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

    window.form_panel.render = function(panel) {
        Ext.History.init();
        Ext.History.on('change', on_hash_change);

        hbox_center_panel.add(sidebar);
        hbox_center_panel.add(map);
        hbox_center_panel.doLayout();

        panel.removeAll();
        panel.add(hbox_center_panel);
        panel.doLayout();

        on_hash_change(Ext.History.getToken());
    };
    var show_context_menu = (function () {
        var obj = {};
        return (function (data, x, y, refresh_map) {
            var is_device = ((data.path) &&
                (data.path.indexOf('/zport/dmd/Devices/') == 0)
            );
            var navigatable = ((data.path) && (data.path.indexOf('/') == 0));

            var pin_down = Ext.create('Ext.menu.CheckItem', {
                text: 'Pin Down',
                handler: function() {
                    obj.data.fixed = this.checked;
                }
            });
            var show_inspector = function () {
                if((obj.data.path) && (obj.data.path.indexOf('/zport/dmd/Devices/') == 0)) {
                    Zenoss.inspector.show(obj.data.path, obj.x, obj.y);
                };
            };

            var get_tooltip_listeners = function (text) {
                return {
                    render: function(c) {
                        Ext.create('Ext.tip.ToolTip', {
                            target: c.getEl(),
                            html: text
                        })
                    }
                };
            };

            var device_info = Ext.create('Ext.menu.Item', {
                text: 'Device Info',
                handler: show_inspector,
                listeners: get_tooltip_listeners(is_device ?
                    'Show device info.' :
                    "Can't show device info because this is not a device."
                )
            });
            var change_root_menu = Ext.create('Ext.menu.Item', {
                text: 'Put Map Root Here',
                handler: function () {
                    window.form_panel.change_root(obj.data.path);
                },
                listeners: get_tooltip_listeners(navigatable ?
                    'Rebuild network map starting from this node.' :
                    'Currently it is impossible to navigate to this node.'
                )
            });
            var open_in_new_tab = Ext.create('Ext.menu.Item', {
                text: 'Open Node in New Tab',
                handler: function () {
                    navigate_node(obj.data, '_blank');
                },
            });

            var menu = Ext.create('Ext.menu.Menu', {
                width: 140,
                items: [
                    pin_down,
                    change_root_menu,
                    device_info,
                    open_in_new_tab,
                ]
            });

            obj.data = data;
            obj.x = x;
            obj.y = y;
            obj.refresh_map = refresh_map;

            pin_down.setChecked(data.fixed & 1);

            device_info.setDisabled(!is_device);

            change_root_menu.setDisabled(!navigatable);

            menu.showAt([x, y]);
        });
    })();

})();
