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
    var svg, drawing_space, bottom_layer, top_layer,
        controls, scale_display, center_button, force, tooltip;

    var arrow_path = function(x1, y1, x2, y2, width, r, directed, gizmo, end_faster) {
        var dx = x2 - x1; // direction of arrow
        var dy = y2 - y1;
        var l = Math.sqrt(dx * dx + dy * dy); // length of arrow
        var fx = dx / l; // forward vector
        var fy = dy / l;

        x2 -= fx * end_faster; // make it shorter, so arrow is not below node
        y2 -= fy * end_faster;
         
        var lx = -fy; // side vector
        var ly = fx;
         
        var line_rectangle = [
            (x1 + lx*width) + ',' + (y1 + ly*width),
            (x2 + lx*width) + ',' + (y2 + ly*width),
            (x2 - lx*width) + ',' + (y2 - ly*width),
            (x1 - lx*width) + ',' + (y1 - ly*width)
        ];
         
        var alx, aly, arx, ary;
        if (directed) {
            alx = x2 - fx*r*2 + lx*r;
            aly = y2 - fy*r*2 + ly*r;
            arx = x2 - fx*r*2 - lx*r;
            ary = y2 - fy*r*2 - ly*r;
        };
         
        var get_end_points = function () {
            // return list of end vertexes that for an arrow or just side of rectangle.
            if(directed) {            
                return [
                    'L' + (x2 - fx*r*2 + lx * width) + ',' + (y2 - fy*r*2 + ly * width),
                    'L' + (x2 - fx*r*2 + lx * r) + ',' + (y2 - fy*r*2 + ly * r),
                    'L' + x2 + ',' + y2,
                    'L' + (x2 - fx*r*2 - lx * r) + ',' + (y2 - fy*r*2 - ly * r),
                    'L' + (x2 - fx*r*2 - lx * width) + ',' + (y2 - fy*r*2 - ly * width),
                ];      
            } else {
                return [
                    'L' + line_rectangle[1],
                    'L' + line_rectangle[2],
                ];
     
            };
        };
         
        if (!gizmo) {
            return [
                'M' + x1 + ',' + y1,
                'L' + line_rectangle[0]
            ].concat(
                get_end_points(),
                [
                    'L' + line_rectangle[3],
                    'L' + x1 + ',' + y1,
                ]
            ).join(' ');
        };
         
        var cx = (x1 + x2) / 2;
        var cy = (y1 + y2) / 2;
        var h = Math.sqrt(r*r - width*width);
         
        var arc_rectangle = [
            (cx - fx*h + lx*width) + ',' + (cy - fy*h + ly*width),
            (cx + fx*h + lx*width) + ',' + (cy + fy*h + ly*width),
            (cx + fx*h - lx*width) + ',' + (cy + fy*h - ly*width),
            (cx - fx*h - lx*width) + ',' + (cy - fy*h - ly*width),
        ];
         
        if (gizmo === 'circle') {
            return [
                'M' + x1 + ',' + y1,
                'L' + line_rectangle[0],
                'L' + arc_rectangle[0],
                'A' + r + ',' + r + ' 0 0,0 ' + arc_rectangle[1],
            ].concat(
                get_end_points(),
                [
                    'L' + arc_rectangle[2],
                    'A' + r + ',' + r + ' 0 0,0 ' + arc_rectangle[3],
                    'L' + line_rectangle[3],
                    'L' + x1 + ',' + y1,
                ]
            ).join(' ');
        };
         
        if (gizmo === 'diamond') {
            return [
                'M' + x1 + ',' + y1,
                'L' + line_rectangle[0],
                'L' + arc_rectangle[0],
                'L' + (cx + lx * r) + ',' + (cy + ly*r),
                'L' + arc_rectangle[1],
            ].concat(
                get_end_points(),
                [
                    'L' + arc_rectangle[2],
                    'L' + (cx - lx * r) + ',' + (cy - ly*r),
                    'L' + arc_rectangle[3],
                    'L' + line_rectangle[3],
                    'L' + x1 + ',' + y1,
                ]
            ).join(' ');
        };
         
        throw 'Unknown gizmo value'
    };

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

            tooltip = d3.select("body").append("div")   
                .attr("class", "tooltip")               
                .style("opacity", 0);

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
                    .text('No map for selection.');
                return;
            };

            force
                .nodes(graph.nodes)
                .links(graph.links)
                .start();

            var link = bottom_layer.selectAll(".link")
                .data(graph.links);

            // append
            link.enter().append("path")
                .attr("class", "link")
                .on('mouseover', function(d) {
                    tooltip.html(d.layers.join('<br />'))
                        .style('left', d3.event.pageX + 'px')
                        .style('top', d3.event.pageY + 'px');
                    tooltip.transition()
                        .duration(200)
                        .style('opacity', 0.95);
                })
                .on('mouseout', function(d) {
                    tooltip.transition()
                        .duration(200)
                        .style('opacity', 0);
                });

            // update
            link.style('fill', function(d) {
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
                    "d": function (d) { 
                        return arrow_path(
                            d.source.x, d.source.y,
                            d.target.x, d.target.y,
                            0.7, 5, d.directed,
                            // if vlan (orange) - make gizmo diamond
                            ((d.color === 'orange') ? 'diamond' : 'circle'),
                            21
                        );
                    },
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
