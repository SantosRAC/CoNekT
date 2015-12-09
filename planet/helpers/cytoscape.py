from flask import url_for

from planet.models.relationships import SequenceFamilyAssociation, SequenceInterproAssociation

from sqlalchemy.orm import joinedload

from utils.color import string_to_hex_color, string_to_shape, family_to_shape_and_color
from utils.benchmark import benchmark

from copy import deepcopy


class CytoscapeHelper:

    @staticmethod
    def parse_network(network):
        """
        Parses a network generated by the ExpressionNetwork and CoexpressionCluster model, adding basic information
        and exporting the whole thing to a cytoscape.js compatible

        :param network: internal id of the network
        :return: Network fully compatible with Cytoscape.js
        """
        output = {"nodes": [], "edges": []}

        for n in network["nodes"]:
            output["nodes"].append({"data": n})

        for e in network["edges"]:
            output["edges"].append({"data": e})

        # add basic colors and shapes to nodes and url to gene pages

        for n in output["nodes"]:
            if n["data"]["gene_id"] is not None:
                n["data"]["gene_link"] = url_for("sequence.sequence_view", sequence_id=n["data"]["gene_id"])

            n["data"]["profile_link"] = url_for("expression_profile.expression_profile_find", probe=n["data"]["id"])
            n["data"]["color"] = "#CCC"
            n["data"]["shape"] = "ellipse"

        for e in output["edges"]:
            e["data"]["color"] = "#888"

        return output

    @staticmethod
    def add_family_data_nodes(network, family_method_id):
        """
        Colors a cytoscape compatible network (dict) based on gene family

        :param network: dict containing the network
        :param family_method_id: desired type/method used to construct the families

        :return: Cytoscape.js compatible network with colors and shapes based on gene families included
        """
        completed_network = deepcopy(network)

        sequence_ids = []
        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                sequence_ids.append(node["data"]["gene_id"])

        sequence_families = SequenceFamilyAssociation.query.\
            filter(SequenceFamilyAssociation.sequence_id.in_(sequence_ids)).\
            options(joinedload('family.clade')).\
            filter(SequenceFamilyAssociation.family.has(method_id=family_method_id)).all()

        families = {}

        for s in sequence_families:
            families[s.sequence_id] = {}
            families[s.sequence_id]["name"] = s.family.name
            families[s.sequence_id]["id"] = s.gene_family_id
            if s.family.clade is not None:
                families[s.sequence_id]["clade"] = s.family.clade.name
                families[s.sequence_id]["clade_count"] = s.family.clade.species_count
            else:
                families[s.sequence_id]["clade"] = "None"
                families[s.sequence_id]["clade_count"] = 0

        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys() \
                    and node["data"]["gene_id"] in families.keys():
                node["data"]["family_name"] = families[node["data"]["gene_id"]]["name"]
                node["data"]["family_id"] = families[node["data"]["gene_id"]]["id"]
                node["data"]["family_color"] = string_to_hex_color(families[node["data"]["gene_id"]]["name"])
                node["data"]["family_shape"] = string_to_shape(families[node["data"]["gene_id"]]["name"])
                node["data"]["family_clade"] = families[node["data"]["gene_id"]]["clade"]
                node["data"]["family_clade_count"] = families[node["data"]["gene_id"]]["clade_count"]
            else:
                node["data"]["family_name"] = None
                node["data"]["family_id"] = None
                node["data"]["family_color"] = "#CCC"
                node["data"]["family_shape"] = "rectangle"
                node["data"]["family_clade"] = "None"
                node["data"]["family_clade_count"] = 1

        return completed_network

    @staticmethod
    def add_lc_data_nodes(network, family_method_id):
        """
        Colors a cytoscape compatible network (dict) based on gene family

        :param network: dict containing the network
        :param family_method_id: desired type/method used to construct the families

        :return: Cytoscape.js compatible network with colors and shapes based on gene families included
        """
        completed_network = deepcopy(network)

        sequence_ids = []
        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                sequence_ids.append(node["data"]["gene_id"])


        sequence_families = SequenceFamilyAssociation.query.\
            filter(SequenceFamilyAssociation.sequence_id.in_(sequence_ids)).\
            options(joinedload('family.clade')).all()

        sequence_interpro = SequenceInterproAssociation.query.\
            filter(SequenceInterproAssociation.sequence_id.in_(sequence_ids)).all()

        ###gene2labels: [sequenceID] = [[PLAZA].[interpro]]
        gene2labels = {}
        for s in sequence_families:
            gene2labels[s.sequence_id] = [[s.family.name],[]]

        for s in sequence_interpro:
            if s.sequence_id in gene2labels:
                gene2labels[s.sequence_id][1] += [s.domain.label]
            else:
                gene2labels[s.sequence_id][1] = [[], [s.domain.label]]


        ###shapes_colors: [family] = [shape.color]
        gene_to_shape_and_color = family_to_shape_and_color(gene2labels)

        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                if node["data"]["gene_id"] in gene_to_shape_and_color:
                    node["data"]["lc_color"] = gene_to_shape_and_color[node["data"]["gene_id"]][1]
                    node["data"]["lc_shape"] = gene_to_shape_and_color[node["data"]["gene_id"]][0]
        return completed_network


    @staticmethod
    def add_depth_data_nodes(network):
        """
        Colors a cytoscape compatible network (dict) based on edge depth

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with depth information for nodes added
        """
        colored_network = deepcopy(network)

        colors = ["#3CE500", "#B7D800", "#CB7300", "#BF0003"]

        for node in colored_network["nodes"]:
            if "data" in node.keys() and "depth" in node["data"].keys():
                node["data"]["depth_color"] = colors[node["data"]["depth"]]

        return colored_network

    @staticmethod
    def add_connection_data_nodes(network):
        """
        A data to cytoscape compatible network's nodes based on the number of edges that node possesses

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with connectivity information for nodes added
        """
        colored_network = deepcopy(network)

        for node in colored_network["nodes"]:
            if "data" in node.keys() and "id" in node["data"].keys():
                probe = node["data"]["id"]
                neighbors = 0
                for edge in colored_network["edges"]:
                    if "data" in edge.keys() and "source" in edge["data"].keys() and "target" in edge["data"].keys():
                        if probe == edge["data"]["source"] or probe == edge["data"]["target"]:
                            neighbors += 1

                node["data"]["neighbors"] = neighbors

        return colored_network

    @staticmethod
    def add_depth_data_edges(network):
        """
        Colors a cytoscape compatible network (dict) based on edge depth

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with depth information for edges added
        """
        colored_network = deepcopy(network)

        colors = ["#3CE500", "#B7D800", "#CB7300", "#BF0003"]

        for edge in colored_network["edges"]:
            if "data" in edge.keys() and "depth" in edge["data"].keys():
                edge["data"]["depth_color"] = colors[edge["data"]["depth"]]

        return colored_network
