/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2014, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/

var render_network_map = function(panel_selector) {
    var panel = d3.select(panel_selector);
    var width = panel[0][0].clientWidth;
    var height = panel[0][0].clientHeight;
    var svg = panel.append("svg")
        .attr("width", width)
        .attr("height", height)
        .style('border', 'solid black 1px');

    var force = d3.layout.force()
        .gravity(0.05)
        .distance(100)
        .charge(-200)
        .size([width, height]);


    var draw_graph = function (graph) {
        force
            .nodes(graph.nodes)
            .links(graph.links)
            .start();

        var link = svg.selectAll(".link")
            .data(graph.links)
            .enter().append("line")
            .attr("class", "link");

        var node = svg.selectAll(".node")
            .data(graph.nodes)
            .enter().append("g")
            .attr("class", "node")
            .call(force.drag);

        node.append("circle")
            .attr('r', 8)
            .style('display', function(d) { if(d.image) return 'none'; else return 'block'; });

        node.append("image")
          .attr("xlink:href", function(d) { return d.image })
          .attr("x", -16)
          .attr("y", -18)
          .attr("width", 32)
          .attr("height", 32);

        node.append("text")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(function (d) {
            return d.name;
        });

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


    d3.json('/zport/dmd/getJSONEdges?root_id=10.87.100.1', function(error, json) {
        if(error) return console.error(error);
        draw_graph(json);
    });
};
