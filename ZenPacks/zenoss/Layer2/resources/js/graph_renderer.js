/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

"use strict";

window.graph_renderer = function(panel_selector, on_node_click) {
    var panel = d3.select(panel_selector);
    var width = panel[0][0].clientWidth;
    var height = panel[0][0].clientHeight;

    var display_scale = function (sc) {
        scale_display.text('Scale: ' + Math.round(sc * 100) + '%');
    };

    var zoom = d3.behavior.zoom()
        .scaleExtent([0.2, 2])
        .on('zoom', function () {
            var tr = d3.event.translate,
                sc = d3.event.scale,
                transform = 'translate(' + tr + ')scale(' + sc + ')';
            display_scale(sc);
            drawing_space.attr("transform", transform);
        });

    var svg = panel.append("svg")
        .attr("width", width)
        .attr("height", height)
        .call(zoom);

    var drawing_space = svg.append('g'),
        bottom_layer = drawing_space.append('g'),
        top_layer = drawing_space.append('g');

    var controls = panel.append('div')
        .attr('id', 'controls_panel');

    var scale_display = controls.append('div');

    var center = function() {
            display_scale(1);
            zoom.translate([0,0]);
            zoom.scale(1);
            zoom.event(drawing_space.transition().duration(500));
    };

    var center_button = controls.append('button')
        .text('Center')
        .on('click', center);


    var force = d3.layout.force()
        .linkDistance(100)
        .chargeDistance(400)
        .charge(-500)
        .gravity(0.05)
        .size([svg.attr('width'), svg.attr('height')]);

    force.drag().on("dragstart", function() {
          // to disallow panning during drag
          d3.event.sourceEvent.stopPropagation();
    });


    var draw_graph = function (graph) {
        panel.selectAll('.message').remove(); //remove old messages
        svg.style('display', 'block');
        if (typeof graph.nodes == 'undefined' || graph.nodes.length == 0) {
            // Draw message - no data

            svg.style('display', 'none');
            panel.append('p')
                .attr('class', 'message')
                .text('No data. (See "Page Tips" for help).');
            return;
        };

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
            .on('click', function(d) {
                if (d3.event.defaultPrevented) return; // No click when drag!
                on_node_click(d)
            })
            .call(force.drag);

        node_enter.append("circle").attr('r', 8);

        node_enter.append("image")
            .attr("x", -16)
            .attr("y", -16)
            .attr("width", 32)
            .attr("height", 32);

        node_enter.append("text")
            .attr("dx", 25)
            .attr("dy", ".35em");

        // update
        node.select('circle')
            .attr('class', function(d) {
                if(d.highlight) return 'highlighted ' + d.color;
                return d.color;
            })
            .attr('r', function(d) {
                if(d.highlight) return 25; else return 21;
            });
        node.select('image')
            .attr("xlink:href", function(d) { return d.image; });
        node.select('text')
            .text(function (d) { return d.name.slice(0, 20) + ((d.name.length > 20) ? ' ...' : ''); });

        // remove
        node.exit().remove();

        // animation:
        force.on("tick", function () {
            link.attr({
                "x1": function (d) { return d.source.x; },
                "y1": function (d) { return d.source.y; },
                "x2": function (d) { return d.target.x; },
                "y2": function (d) { return d.target.y; },
            });

            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });
        });

        center();
    };

    var draw_legend = function (panel) {
        var legend = panel.append("svg")
            .attr("width", 90)
            .attr("height", 130);

        var node = legend.selectAll(".node")
            .data([
                { color: 'severity_critical', name: 'Critical' },
                { color: 'severity_error', name: 'Error' },
                { color: 'severity_warning', name: 'Warning' },
                { color: 'severity_info', name: 'Info' },
                { color: 'severity_debug', name: 'Debug' },
                { color: 'severity_none', name: 'Map root', highlight: true },
            ]);

        // append
        var node_enter = node.enter().append("g")
            .attr("class", "node")

        node_enter.append("circle").attr('r', 8);

        node_enter.append("text")
            .attr("dx", 25)
            .attr("dy", ".35em");

        // update

        node.attr("transform", function (d, i) {
            return 'translate(10, ' + (i + 1) * 20 + ')';
        })
        node.select('circle')
            .attr('class', function(d) {
                if(d.highlight) return 'highlighted ' + d.color;
                return d.color;
            })

        node.select('text')
            .text(function (d) { return d.name });

        // remove
        node.exit().remove();
    };
    draw_legend(controls);

    return {
        draw: draw_graph,
    };
};
