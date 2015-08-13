from flask import Blueprint, redirect, url_for, render_template, Response

from planet.models.expression_networks import ExpressionNetworkMethod, ExpressionNetwork

import json

expression_network = Blueprint('expression_network', __name__)

@expression_network.route('/')
def expression_network_overview():
    networks = ExpressionNetworkMethod.query.all()

    return render_template("expression_network.html", networks=networks)

def __process_link(link):

    output = {}
    if link["gene_id"] is not None:
        output = {"data": {"id": link["probe_name"],
                               "name": link["probe_name"],
                               "gene_link": url_for('sequence.sequence_view', sequence_id=link["gene_id"]),
                               "gene_name": link["gene_name"],
                               "node_type": "linked"}}
    else:
        output = {"data": {"id": link["probe_name"],
                               "name": link["probe_name"],
                               "gene_link": url_for('sequence.sequence_view', sequence_id=""),
                               "gene_name": link["gene_name"],
                               "node_type": "linked"}}

    return output

@expression_network.route('/json/<node_id>')
@expression_network.route('/json/<node_id>/<int:depth>')
def expression_network_json(node_id, depth=0):
    node = ExpressionNetwork.query.get(node_id)
    links = json.loads(node.network)

    method_id = node.method_id

    # add the initial node
    nodes = [{"data": {"id": node.probe,
                       "name": node.probe,
                       "gene_link": url_for('sequence.sequence_view', sequence_id=node.gene_id),
                       "gene_name": node.gene.name,
                       "node_type": "query"}}]
    edges = []

    # two variables necessary for doing deeper searches
    additional_nodes = []
    existing_edges = []
    existing_nodes = [node.probe]

    for link in links:
        nodes.append(__process_link(link))
        edges.append({"data": {"source": node.probe, "target": link["probe_name"], "depth": 0}})
        additional_nodes.append(link["probe_name"])
        existing_edges.append([node.probe, link["probe_name"]])
        existing_edges.append([link["probe_name"], node.probe])
        existing_nodes.append(link["probe_name"])

    # iterate n times to add deeper links

    for i in range(1, depth+1):
        next_nodes = []
        for additional_node in additional_nodes:
            new_node = ExpressionNetwork.query.filter_by(probe=additional_node, method_id=method_id).first()
            new_links = json.loads(new_node.network)

            for link in new_links:
                if link["probe_name"] not in existing_nodes:
                    nodes.append(__process_link(link))

                if [[new_node.probe, link["probe_name"]]] not in existing_nodes:
                    edges.append({"data": {"source": new_node.probe, "target": link["probe_name"], "depth": i}})
                    existing_edges.append([new_node.probe, link["probe_name"]])
                    existing_edges.append([link["probe_name"], new_node.probe])
                    existing_nodes.append(link["probe_name"])
                    next_nodes.append(link["probe_name"])

        additional_nodes = next_nodes

    return json.dumps({"nodes": nodes, "edges": edges})


@expression_network.route('/view/<node_id>')
@expression_network.route('/view/<node_id>/<int:depth>')
def expression_network_view(node_id, depth=0):
    node = ExpressionNetwork.query.get(node_id)
    return render_template("expression_graph.html", node=node, depth=depth)