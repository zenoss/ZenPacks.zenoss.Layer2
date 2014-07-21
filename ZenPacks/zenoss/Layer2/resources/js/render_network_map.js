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
    var form = d3.select(control_form_selector);

    var parse_get_query = function () {
        var query = window.location.hash.substring(1);
        var res = {};
        query.split("&").forEach(function(val) {
            var pair = val.split('=');
            res[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
        });
        if(!res['filter_type_selec']) res['filter_type_select'] = 'Device Class';
        if(!res['depth']) res['depth'] = 2;
        if(!res['root_id']) res['root_id'] = '';
        load_filters('Device Class');
        return res;
    };
    var serialize_get_query = function (data) {
        return Object.keys(data).map(function(key) {
            return [key, data[key]].map(encodeURIComponent).join("=");
        }).join("&");
    };

    var filter_label = form.select('#filter_label');
    var filter_select = form.select('#filter_select');

    var load_filters = function(filter_type) {
        filter_label.text(filter_type + ' filter: ');
        var options = window.filter_type_options[filter_type];
        var element_options = filter_select[0][0].options;
        element_options.length = 0;
        for(var i = 0; i < options.length; i++) {
            element_options[element_options.length] = new Option(options[i].label, options[i].data);
        };
    };

    var filter_type_select = form.select('#filter_type_select')
        .on('change', function() {
            load_filters(this.value);
        });

    var show_error = Zenoss.flares.Manager.error;
    var update_view = function() {
        console.log('updating view');
        d3.json('/zport/dmd/getJSONEdges?' + window.location.hash.slice(1), function(error, json) {
            if(error) return show_error(error);
            if(json.error) return show_error(json.error);
            draw_graph(json);
        });
        var params = parse_get_query();
        var elements = form[0][0].elements
        elements['root_id'].value = params['root_id'];
        elements['depth'].value = params['depth'];
        elements['filter_select'].value = params['filter'];
        elements['filter_type_select'].value = params['filter_type_select'];
        elements['repulsion'].value = params['repulsion'];
    };

    var get_form_data = function () {
        var elements = form[0][0].elements
        return serialize_get_query({
            'root_id': elements['root_id'].value,
            'depth': elements['depth'].value,
            'filter': elements['filter_select'].value,
            'filter_type_select': elements['filter_type_select'].value,
            'repulsion': elements['repulsion'].value
        });
    };
    window.addEventListener("hashchange", update_view);
    update_view();

    var refresh_map = function() {
        window.location.hash = '#' + get_form_data();
    };
    var refresh_button = form.select('#refresh_button')
        .on('click', refresh_map);
    form.selectAll('input[type=text]')
        .on('keydown', function() {
            if(d3.event.keyCode == 13) refresh_map();
        });

    var set_repulsion = function (force, value) {
        return force
            .linkDistance(+value)
            .chargeDistance(4 * value)
            .charge(-5 * value);
    };
    var repulsion = form.select('#repulsion')
        .on('input', function () {
            set_repulsion(force, this.value).start();
        });

    var scale_display = form.select('#scale_display');

    var panel = d3.select(panel_selector);
    var width = panel[0][0].clientWidth;
    var height = panel[0][0].clientHeight;

    var zoom = d3.behavior.zoom()
        .scaleExtent([0.2, 2])
        .on('zoom', function () {
            var tr = d3.event.translate,
                sc = d3.event.scale,
                transform = 'translate(' + tr + ')scale(' + sc + ')';
            scale_display.text('Scale: ' + Math.round(sc * 100) + '%');
            drawing_space.attr("transform", transform);
        });

    var svg = panel.append("svg")
        .attr("width", width)
        .attr("height", height)
        .call(zoom);

    var drawing_space = svg.append('g'),
        bottom_layer = drawing_space.append('g'),
        top_layer = drawing_space.append('g');

    var center_button = form.select('#center_button')
        .on('click', function() {
            console.log('centering');
            zoom.translate([0,0]);
            zoom.scale(1);
            zoom.event(drawing_space.transition().duration(500));
        });

    var force = set_repulsion(d3.layout.force(), repulsion[0][0].value)
        .gravity(0.05)
        .size([width, height]);

    force.drag().on("dragstart", function() {
          // to disallow panning during drag
          d3.event.sourceEvent.stopPropagation();
    });

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
            .attr("xlink:href", function(d) {
              return d.image;
            });
        node.select('text')
            .text(function (d) {
                return d.name;
            });

        // remove
        node.exit().remove();

        force.on("tick", function () {
            link.attr("x1", function (d) {
                return d.source.x;
            })
                .attr("y1", function (d) {
                return d.source.y;
            })
                .attr("x2", function (d) {
                return d.target.x;
            })
                .attr("y2", function (d) {
                return d.target.y;
            });

            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });
        });
    };
};
