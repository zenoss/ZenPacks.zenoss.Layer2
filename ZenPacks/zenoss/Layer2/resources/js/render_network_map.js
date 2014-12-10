/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

"use strict";

var render_network_map = function(panel_selector, control_form_selector) {
    ////////////////////////////////////////////////////////
    // Library (function without external dependencies):  //
    ////////////////////////////////////////////////////////

    d3.selection.prototype.onReturn = function(callback) {
        return this.on('keydown', function() {
            if(d3.event.keyCode == 13) callback();
        });
    };

    var parse_get_query = function (query) {
        // Gets string in GET query format ('key=value&key=value') and returns 
        // an object with attributes set accordingly to values. 
        // If some keys are not set in query - sets for them default values.
        var res = {};
        query.split("&").forEach(function(val) {
            var pair = val.split('=');
            res[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
        });
        if(!res['filter_type_selec']) res['filter_type_select'] = 'Device Class';
        if(!res['depth']) res['depth'] = 2;
        if(!res['root_id']) res['root_id'] = '';
        return res;
    };

    var serialize_get_query = function (data) {
        // Return get query string build from attributes of data object.
        return Object.keys(data).map(function(key) {
            return [key, data[key]].map(encodeURIComponent).join("=");
        }).join("&");
    };

    var get_form_data = function (form) {
        // Return get query based on form values
        var elements = form.elements;
        return serialize_get_query({
            'root_id': elements['root_id'].value,
            'depth': elements['depth'].value,
            'filter': elements['filter_select'].value,
            'filter_type_select': elements['filter_type_select'].value,
            'repulsion': elements['repulsion'].value
        });
    };


    var set_repulsion = function (force, value) {
        // set repulsion value on force layout
        return force
            .linkDistance(+value)
            .chargeDistance(4 * value)
            .charge(-5 * value);
    };

    ////////////////////
    // Binding to UI: //
    ////////////////////

    var form = d3.select(control_form_selector);

    var filter_label = form.select('#filter_label'); 
    var filter_select = form.select('#filter_select');
    var filter_type_select = form.select('#filter_type_select');
    var refresh_button = form.select('#refresh_button');
    var center_button = form.select('#center_button');
    var scale_display = form.select('#scale_display');
    var repulsion = form.select('#repulsion');

    var get_svg = function() {
        var panel = d3.select(panel_selector);
        var width = panel[0][0].clientWidth;
        var height = panel[0][0].clientHeight;

        var svg = panel.append("svg")
            .attr("width", width)
            .attr("height", height);
        return svg;
    }

    var show_error = Zenoss.flares.Manager.error;

    var get_hash = function () {
        return window.location.hash.substring(1);
    };
    var set_hash = function (value) {
        window.location.hash = '#' + value;
    };
    var display_scale = function (sc) {
        scale_display.text('Scale: ' + Math.round(sc * 100) + '%');
    };

    var get_filter_options_by_type = function (filter_type) {
        return window.filter_type_options[filter_type];
    };

    var load_filters = function(filter_type) {
        // Load filter options for given type
        filter_label.text(filter_type + ' filter: ');
        var options = get_filter_options_by_type(filter_type);
        var element_options = filter_select[0][0].options;
        element_options.length = 0;
        for(var i = 0; i < options.length; i++) {
            element_options[element_options.length] = new Option(options[i].label, options[i].data);
        };
    };

    var updating = false;
    var update_view = function() {
        // Sets form fields and redraws graph according to hash state
        if(updating) return;
        updating = true;

        // get new data and redraw map
        var hash = get_hash();
        d3.json('/zport/dmd/getJSONEdges?' + hash, function(error, json) {
            updating = false;
            if(error) return show_error(error);
            if(json.error) return show_error(json.error); 
            draw_graph(json);
        });

        // update form
        var params = parse_get_query(hash);
        var elements = form[0][0].elements;
        elements['root_id'].value = params['root_id'];
        elements['depth'].value = params['depth'];
        elements['filter_select'].value = params['filter'];
        elements['filter_type_select'].value = params['filter_type_select'];
        load_filters(params['filter_type_select']);
        elements['repulsion'].value = params['repulsion'];
    };

    /////////////////
    // Events:     //
    /////////////////

    filter_type_select.on('change', function() {
        load_filters(this.value);
    });
    window.addEventListener("hashchange", update_view);
    update_view();

    var refresh_map = function() {
        set_hash(get_form_data(form[0][0]));
        update_view();
    };
    refresh_button.on('click', refresh_map);
    form.selectAll('input[type=text]').onReturn(refresh_map);
    form.selectAll('input[type=number]').onReturn(refresh_map);

    repulsion.on('input', function () {
        set_repulsion(force, this.value).start();
    });


    var zoom = d3.behavior.zoom()
        .scaleExtent([0.2, 2])
        .on('zoom', function () {
            var tr = d3.event.translate,
                sc = d3.event.scale,
                transform = 'translate(' + tr + ')scale(' + sc + ')';
            display_scale(sc);
            drawing_space.attr("transform", transform);
        });

    var svg = get_svg().call(zoom);
    var drawing_space = svg.append('g'),
        bottom_layer = drawing_space.append('g'),
        top_layer = drawing_space.append('g');

    center_button.on('click', function() {
            zoom.translate([0,0]);
            zoom.scale(1);
            zoom.event(drawing_space.transition().duration(500));
    });

    var force = set_repulsion(d3.layout.force(), repulsion[0][0].value)
        .gravity(0.05)
        .size([svg.attr('width'), svg.attr('height')]);

    force.drag().on("dragstart", function() {
          // to disallow panning during drag
          d3.event.sourceEvent.stopPropagation();
    });


    ///////////////////
    // Graph drawing //
    ///////////////////
    var draw_graph = function (graph) {
        force
            .nodes(graph.nodes)
            .links(graph.links)
            .start();

        var link = bottom_layer.selectAll(".link")
            .data(graph.links);

        // append
        link.enter().append("line")
            .attr("class", "link");

        // update
        link.style('stroke', function(d) {
            return d.color || '#ccc'
        });

        // remove
        link.exit().remove();


        var node = top_layer.selectAll(".node")
            .data(graph.nodes);

        // append
        var node_enter = node.enter().append("g")
            .attr("class", "node")
            .call(force.drag);

        node_enter.append("circle").attr('r', 8);

        node_enter.append("image")
            .attr("x", -16)
            .attr("y", -18)
            .attr("width", 32)
            .attr("height", 32);

        node_enter.append("text")
            .attr("dx", 12)
            .attr("dy", ".35em");

        // update
        node.select('circle')
            .style('display', function(d) {
                if(d.highlight) return 'block';
                if(d.image) return 'none'; else return 'block';
            })
            .attr('fill', function(d) {
                if(d.highlight) return 'Aquamarine';
            })
            .attr('r', function(d) {
                if(d.highlight) return 20; else return 8;
            });
        node.select('image')
            .attr("xlink:href", function(d) { return d.image; });
        node.select('text')
            .text(function (d) { return d.name.slice(0, 20) + ((d.name.length > 20) ? ' ...' : ''); });

        // remove
        node.exit().remove();

        // animation:
        force.on("tick", function () {
            link.attr("x1", function (d) { return d.source.x; })
                .attr("y1", function (d) { return d.source.y; })
                .attr("x2", function (d) { return d.target.x; })
                .attr("y2", function (d) { return d.target.y; });

            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });
        });
    };
};
