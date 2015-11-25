/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

/*
 * This file contains code that renders network map as directed graph using d3.js
 *
 * Usage:
 *
 * var graph = graph_renderer('#panel_id', on_node_click);
 * graph.draw(topology);
 * 
 */

"use strict";

(function () {

    var init_called = false;
    var svg, drawing_space, bottom_layer, top_layer, controls, scale_display, center_button, force;

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

        var center = function() {
                display_scale(1);
                zoom.translate([0,0]);
                zoom.scale(1);
                zoom.event(drawing_space.transition().duration(500));
        };

        var init = function () {
            if(init_called) return; // call this only once
            init_called = true;

            svg = panel.append("svg")
                .attr("width", width)
                .attr("height", height)
                .call(zoom);


            // http://bl.ocks.org/d3noob/5141278
            svg.append("svg:defs").selectAll("marker")
                .data(["end"])      // Different link/path types can be defined here
              .enter().append("svg:marker")    // This section adds in the arrows
                .attr("id", String)
                .attr("refX", 31)
                .attr("refY", 5)
                .attr("markerWidth", 31)
                .attr("markerHeight", 10)
                .attr("orient", "auto")
              .append("svg:path")
                .attr("d", "M0,0L10,5L0,10L0,0");


            drawing_space = svg.append('g'),
                bottom_layer = drawing_space.append('g'),
                top_layer = drawing_space.append('g');

            controls = panel.append('div')
                .attr('id', 'controls_panel');

            scale_display = controls.append('div');

            center_button = controls.append('button')
                .text('Center')
                .on('click', center);

            force = d3.layout.force()
                .linkDistance(100)
                .chargeDistance(400)
                .charge(-500)
                .gravity(0.05)
                .size([svg.attr('width'), svg.attr('height')]);

            force.drag().on("dragstart", function() {
                  // to disallow panning during drag
                  d3.event.sourceEvent.stopPropagation();
                  force.stop();
            })
            .on('drag', function(d) {
                d.x += d3.event.dx;
                d.y += d3.event.dy;
            })
            .on('dragend', function(d) {
                d.fixed = true;
                force.resume();
            });
            draw_legend(controls);
        };


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
                .attr("marker-end", function(d) {
                    if(d.directed) 
                        return "url(#end)"
                    else
                        return "none"
                })
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
                .on('contextmenu', function (d) {
                    if (d3.event.defaultPrevented) return; // No click when drag!
                    on_node_click(d, true, d3.event.clientX, d3.event.clientY) // right click

                    d3.event.preventDefault(); // Do not show context menu.
                })
                .call(force.drag);

            node_enter.append("circle").attr('r', 8);

            node_enter.append("image")
                .attr("x", -16)
                .attr("y", -16)
                .attr("width", 32)
                .attr("height", 32);

            var node_text = node_enter.append('g');
            node_text.append("text")
                .attr("class", "display-short")
                .attr("dx", 25)
                .attr("dy", ".35em");

            node_text.append("text")
                .attr("class", "display-full")
                .attr("dx", 25)
                .attr("dy", ".35em");

            // update
            node.select('circle')
                .attr('class', function(d) {
                    if(d.highlight) return 'highlighted ' + d.color;
                    return d.color;
                })
                .attr('r', 21);

            node.select('image')
                .attr("xlink:href", function(d) { return d.image; });

            node.select('text.display-short')
                .text(function (d) {
                    return (
                        d.name.slice(0, 20) +
                        ((d.name.length > 20) ? ' ...' : '')
                    );
                });
            node.select('text.display-full')
                .text(function (d) { return d.name; });

            // remove
            node.exit().remove();

            // animation:
            var tick = function () {
                link.attr({
                    "x1": function (d) { return d.source.x; },
                    "y1": function (d) { return d.source.y; },
                    "x2": function (d) { return d.target.x; },
                    "y2": function (d) { return d.target.y; },
                });

                node.attr("transform", function (d) {
                    return "translate(" + d.x + "," + d.y + ")";
                });
            };
            force.on("tick", tick);

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

        init();
        return {
            draw: draw_graph,
        };
    };
})();
