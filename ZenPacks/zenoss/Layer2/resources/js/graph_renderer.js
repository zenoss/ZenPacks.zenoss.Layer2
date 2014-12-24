/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

"use strict";

window.graph_renderer = function(panel_selector) {
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

    var scale_display = svg.append('text')
        .attr('x', width)
        .attr('y', '1em')
        .attr('style', 'text-anchor: end;');

    var drawing_space = svg.append('g'),
        bottom_layer = drawing_space.append('g'),
        top_layer = drawing_space.append('g');

    var center =  function() {
            zoom.translate([0,0]);
            zoom.scale(1);
            zoom.event(drawing_space.transition().duration(500));
    };

    var set_repulsion = function (force, value) {
        // set repulsion value on force layout
        console.log(value);
        return force
            .linkDistance(+value)
            .chargeDistance(4 * value)
            .charge(-5 * value)
    };

    var force = set_repulsion(d3.layout.force(), 100)
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
            .attr("y", -16)
            .attr("width", 32)
            .attr("height", 32);

        node_enter.append("text")
            .attr("dx", 25)
            .attr("dy", ".35em");

        // update
        node.select('circle')
            .attr('fill', function(d) {
                return d.color;
            })
            .attr('stroke', function(d) {
                if(d.highlight) return 'SlateBlue';
                else return 'gray';
            })
            .attr('stroke-width',function(d) {
                if(d.highlight) return '3';
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
            link.attr("x1", function (d) { return d.source.x; })
                .attr("y1", function (d) { return d.source.y; })
                .attr("x2", function (d) { return d.target.x; })
                .attr("y2", function (d) { return d.target.y; });

            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });
        });

        center();
    };
    return {
        draw: draw_graph,
        center: center,
        set_repulsion: function(value) { set_repulsion(force, value).start() },
    };
};
