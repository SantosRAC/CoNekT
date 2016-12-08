from flask import url_for
from planet import db
from planet.models.relationships import SequenceFamilyAssociation, SequenceSequenceECCAssociation
from planet.models.gene_families import GeneFamily
from planet.models.species import Species
from planet.models.sequences import Sequence

from utils.jaccard import jaccard
from utils.benchmark import benchmark

import random
import json
import re
from sqlalchemy import and_

SQL_COLLATION = 'NOCASE' if db.engine.name == 'sqlite' else ''


class ExpressionNetworkMethod(db.Model):
    __tablename__ = 'expression_network_methods'
    id = db.Column(db.Integer, primary_key=True)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), index=True)
    description = db.Column(db.Text)
    edge_type = db.Column(db.Enum("rank", "weight", name='edge_type'))
    probe_count = db.Column(db.Integer)

    probes = db.relationship('ExpressionNetwork',
                             backref=db.backref('method', lazy='joined'),
                             lazy='dynamic',
                             cascade='all, delete-orphan')

    clustering_methods = db.relationship('CoexpressionClusteringMethod',
                                         backref='network_method',
                                         lazy='dynamic',
                                         cascade='all, delete-orphan')

    def __init__(self, species_id, description, edge_type="rank"):
        self.species_id = species_id
        self.description = description
        self.edge_type = edge_type

    def __repr__(self):
        return str(self.id) + ". " + self.description

    @staticmethod
    def update_count():
        """
        To avoid long count queries the number of networks for each method can be precalculated and stored in the
        database using this function
        """
        methods = ExpressionNetworkMethod.query.all()

        for m in methods:
            m.probe_count = m.probes.count()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(e)

    @staticmethod
    @benchmark
    def calculate_ecc(network_method_ids, gene_family_method_id):
        """
        Function to calculate the ECC scores in and between genes of different networks

        ORM free method for speed !

        :param network_method_ids: array of networks (using their internal id !) to compare
        :param gene_family_method_id: internal id of the type of family methods to be used for the comparison
        """

        network_families = {}
        sequence_network = {}
        sequence_network_method = {}
        sequence_family = {}
        family_sequence = {}

        # Get all the network information and store in dictionary
        for n in network_method_ids:
            current_network = db.engine.execute(db.select([ExpressionNetwork.__table__.c.sequence_id,
                                                           ExpressionNetwork.__table__.c.network,
                                                           ExpressionNetwork.__table__.c.method_id]).
                                                   where(ExpressionNetwork.__table__.c.method_id == n).
                                                   where(ExpressionNetwork.__table__.c.sequence_id != None)
                                                ).fetchall()

            for sequence, network, network_method_id in current_network:
                sequence_network[int(sequence)] = network
                sequence_network_method[int(sequence)] = int(network_method_id)

        # Get family data and store in dictionary
        current_families = db.engine.execute(db.select([SequenceFamilyAssociation.__table__.c.sequence_id,
                                                        SequenceFamilyAssociation.__table__.c.gene_family_id,
                                                        GeneFamily.__table__.c.method_id]).
                                             select_from(SequenceFamilyAssociation.__table__.join(GeneFamily.__table__)).
                                             where(GeneFamily.__table__.c.method_id == gene_family_method_id)
                                             ).fetchall()

        for sequence, family, method in current_families:
            sequence_family[int(sequence)] = int(family)

            if family not in family_sequence.keys():
                family_sequence[int(family)] = []

            family_sequence[int(family)].append(int(sequence))

        # Create a dict (key = network) with the families present in that network
        # Families that occur multiple times should be present multiple times as this is used
        # to set threshholds later !

        for sequence, network_method in sequence_network_method.items():
            # ignore sequences without a family, ideally this shouldn't happen
            if network_method not in network_families.keys():
                network_families[network_method] = []

            if sequence in sequence_family.keys():
                family = sequence_family[sequence]
                network_families[network_method].append(family)

        # Determine threshold and p-value
        # A background model will be computed for each combination of networks, an ECC score will need to be better
        # than 95 % of the randomly found values to be considered significant

        thresholds = {}
        print("Starting permutation tests")
        for n in network_method_ids:
            thresholds[n] = {}
            for m in network_method_ids:
                thresholds[n][m] = ExpressionNetworkMethod.__set_thresholds(network_families[n],
                                                                            network_families[m],
                                                                            max_size=30)

        # Data loaded start calculating ECCs
        new_ecc_scores = []

        for family, sequences in family_sequence.items():
            for i in range(len(sequences) - 1):
                query = sequences[i]
                for j in range(i+1, len(sequences)):
                    target = sequences[j]
                    if query in sequence_network.keys() and target in sequence_network.keys() and query != target:
                        ecc, significant = ExpressionNetworkMethod.__ecc(sequence_network[query],
                                                                         sequence_network[target],
                                                                         sequence_family,
                                                                         thresholds[sequence_network_method[query]][sequence_network_method[target]],
                                                                         family,
                                                                         max_size=30)
                        if significant:
                            new_ecc_scores.append({
                                'query_id': query,
                                'target_id': target,
                                'ecc': ecc,
                                'gene_family_method_id': gene_family_method_id,
                                'query_network_method_id': sequence_network_method[query],
                                'target_network_method_id': sequence_network_method[target],
                            })

                            # add reciprocal relation
                            new_ecc_scores.append({
                                'query_id': target,
                                'target_id': query,
                                'ecc': ecc,
                                'gene_family_method_id': gene_family_method_id,
                                'query_network_method_id': sequence_network_method[target],
                                'target_network_method_id': sequence_network_method[query],
                            })
                            if len(new_ecc_scores) > 400:
                                db.engine.execute(SequenceSequenceECCAssociation.__table__.insert(), new_ecc_scores)
                                new_ecc_scores = []

        db.engine.execute(SequenceSequenceECCAssociation.__table__.insert(), new_ecc_scores)

    @staticmethod
    def __ecc(q_network, t_network, families, thresholds, query_family, max_size=30):
        """
        Takes the networks neighborhoods (as stored in the databases), extracts the genes and find the families for
        each gene. Next the ECC score is calculated

        :param q_network: network for the query gene
        :param t_network: network for the target gene
        :param families: dictionary that links a sequence id (key) to a family id (value)
        :param thresholds:
        :param query_family: name of the input gene family
        :return: the ECC score for the two input neighborhoods given the families, a boolean flag if this is significant
        """
        q_data = json.loads(q_network)
        t_data = json.loads(t_network)

        q_genes = [t['gene_id'] for t in q_data if t['gene_id'] is not None]
        t_genes = [t['gene_id'] for t in t_data if t['gene_id'] is not None]

        q_families = [families[q] for q in q_genes if q in families.keys() and families[q] != query_family]
        t_families = [families[t] for t in t_genes if t in families.keys() and families[t] != query_family]

        # print("***\nQuery %d\n%s\n%s" % (query_family, ','.join([str(q) for q in q_families]), ','.join([str(t) for t in t_families])))

        if len(q_families) == 0 or len(t_families) == 0:
            return 0.0, False
        else:
            ecc = jaccard(q_families, t_families)

            q_size = len(set(q_families)) if len(set(q_families)) < max_size else max_size
            t_size = len(set(t_families)) if len(set(t_families)) < max_size else max_size

            t = thresholds[q_size-1][t_size-1]

            return ecc, ecc > t

    @staticmethod
    @benchmark
    def __set_thresholds(families_a, families_b, max_size=30, iterations=1000):
        """
        Empirically determine (permutation test) thresholds for ECC

        :param families_a: families of species_a (list of internal family ids)
        :param families_b: families of species_b (list of internal family ids)
        :param max_size: maximum number of families (default = 30)
        :param iterations: number of permutations done
        :return: matrix (list of lists) with the thresholds at various family sizes
        """
        thresholds = []

        for i in range(max_size):
            print("%d done" % i)
            new_threshholds = []
            for j in range(max_size):
                scores = []
                for iterations in range(iterations):
                    if i+1 < len(families_a) and j+1 < len(families_b):
                        i_fams = random.sample(families_a, i+1)
                        j_fams = random.sample(families_b, j+1)
                        scores.append(jaccard(i_fams, j_fams))
                    else:
                        # Cannot calculate threshold with these families, add 1
                        scores.append(1)

                scores = sorted(scores)
                # TODO (maybe?): cutoff is hard coded here, replace ?
                new_threshholds.append(scores[int(iterations*0.95)])
            thresholds.append(new_threshholds)

        return thresholds


class ExpressionNetwork(db.Model):
    __tablename__ = 'expression_networks'
    id = db.Column(db.Integer, primary_key=True)
    probe = db.Column(db.String(50, collation=SQL_COLLATION), index=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'), index=True)
    network = db.Column(db.Text)
    method_id = db.Column(db.Integer, db.ForeignKey('expression_network_methods.id'), index=True)

    def __init__(self, probe, sequence_id, network, method_id):
        self.probe = probe
        self.sequence_id = sequence_id
        self.network = network
        self.method_id = method_id

    @staticmethod
    def get_neighborhood(probe, depth=0):
        """
        Get the coexpression neighborhood for a specific probe

        :param probe: internal ID of the probe
        :param depth: how many steps away from the query you wish to expand the network
        :return: dict with nodes and edges
        """
        node = ExpressionNetwork.query.get(probe)
        links = json.loads(node.network)

        method_id = node.method_id
        edge_type = node.method.edge_type

        # add the initial node
        nodes = [{"id": node.probe,
                  "name": node.probe,
                  "probe_id": node.id,
                  "gene_id": int(node.sequence_id) if node.sequence_id is not None else None,
                  "gene_name": node.sequence.name if node.sequence_id is not None else node.probe,
                  "node_type": "query",
                  "depth": 0}]
        edges = []

        # lists necessary for doing deeper searches
        additional_nodes = []
        existing_edges = []
        existing_nodes = [node.probe]

        # add direct neighbors of the gene of interest

        for link in links:
            nodes.append(ExpressionNetwork.__process_link(link, depth=0))
            edges.append({"source": node.probe,
                          "target": link["probe_name"],
                          "profile_comparison":
                              url_for('expression_profile.expression_profile_compare_probes',
                                      probe_a=node.probe,
                                      probe_b=link["probe_name"],
                                      species_id=node.method.species.id),
                          "depth": 0,
                          "link_score": link["link_score"],
                          "link_pcc": link["link_pcc"] if "link_pcc" in link.keys() else None,
                          "edge_type": edge_type})
            additional_nodes.append(link["probe_name"])
            existing_edges.append([node.probe, link["probe_name"]])
            existing_edges.append([link["probe_name"], node.probe])
            existing_nodes.append(link["probe_name"])

        # iterate n times to add deeper links
        if len(additional_nodes) > 0:
            for i in range(1, depth+1):
                new_nodes = ExpressionNetwork.\
                    query.filter(and_(ExpressionNetwork.probe.in_(additional_nodes),
                                      ExpressionNetwork.method_id == method_id))
                next_nodes = []

                for new_node in new_nodes:
                    new_links = json.loads(new_node.network)

                    for link in new_links:
                        if link["probe_name"] not in existing_nodes:
                            nodes.append(ExpressionNetwork.__process_link(link, depth=depth))
                            existing_nodes.append(link["probe_name"])
                            next_nodes.append(link["probe_name"])

                        if [new_node.probe, link["probe_name"]] not in existing_edges:
                            edges.append({"source": new_node.probe,
                                          "target": link["probe_name"],
                                          "profile_comparison":
                                              url_for('expression_profile.expression_profile_compare_probes',
                                                      probe_a=new_node.probe,
                                                      probe_b=link["probe_name"],
                                                      species_id=node.method.species.id),
                                          "depth": i,
                                          "link_score": link["link_score"],
                                          "link_pcc": link["link_pcc"] if "link_pcc" in link.keys() else None,
                                          "edge_type": edge_type})
                            existing_edges.append([new_node.probe, link["probe_name"]])
                            existing_edges.append([link["probe_name"], new_node.probe])

                additional_nodes = next_nodes

        # Add links between the last set of nodes added
        new_nodes = []
        if len(additional_nodes) > 0:
            new_nodes = ExpressionNetwork.query.filter(and_(ExpressionNetwork.probe.in_(additional_nodes),
                                                            ExpressionNetwork.method_id == method_id))

        for new_node in new_nodes:
            new_links = json.loads(new_node.network)
            for link in new_links:
                if link["probe_name"] in existing_nodes:
                    if [new_node.probe, link["probe_name"]] not in existing_edges:
                        edges.append({"source": new_node.probe,
                                      "target": link["probe_name"],
                                      "profile_comparison":
                                          url_for('expression_profile.expression_profile_compare_probes',
                                                  probe_a=new_node.probe,
                                                  probe_b=link["probe_name"],
                                                  species_id=node.method.species.id),
                                      "depth": depth+1,
                                      "link_score": link["link_score"],
                                      "link_pcc": link["link_pcc"] if "link_pcc" in link.keys() else None,
                                      "edge_type": edge_type})
                        existing_edges.append([new_node.probe, link["probe_name"]])
                        existing_edges.append([link["probe_name"], new_node.probe])

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def get_custom_network(method_id, probes):
        nodes = []
        edges = []

        probes = ExpressionNetwork.query.filter(ExpressionNetwork.method_id == method_id).\
            filter(ExpressionNetwork.probe.in_(probes)).all()

        valid_nodes = []

        for p in probes:
            node = {"id": p.probe,
                    "name": p.probe,
                    "probe_id": p.id,
                    "gene_id": int(p.sequence_id) if p.sequence_id is not None else None,
                    "gene_name": p.sequence.name if p.sequence_id is not None else p.probe,
                    "node_type": "query",
                    "depth": 0}

            valid_nodes.append(p.probe)
            nodes.append(node)

        existing_edges = []

        for p in probes:
            source = p.probe
            neighborhood = json.loads(p.network)
            for n in neighborhood:
                if n["probe_name"] in valid_nodes:
                    if [source, n["probe_name"]] not in existing_edges:
                        edges.append({"source": source,
                                      "target": n["probe_name"],
                                      "profile_comparison":
                                          url_for('expression_profile.expression_profile_compare_probes',
                                                  probe_a=source,
                                                  probe_b=n["probe_name"],
                                                  species_id=p.method.species.id),
                                      "depth": 0,
                                      "link_score": n["link_score"],
                                      "link_pcc": n["link_pcc"] if "link_pcc" in n.keys() else None,
                                      "edge_type": p.method.edge_type})
                        existing_edges.append([source, n["probe_name"]])
                        existing_edges.append([n["probe_name"], source])

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def __process_link(linked_probe, depth):
        """
        Internal function that processes a linked probe (from the ExpressionNetwork.network field) to a data entry
        compatible with cytoscape.js

        :param linked_probe: hash with information from ExpressionNetwork.network field
        :return: a hash formatted for use as a node with cytoscape.js
        """
        if linked_probe["gene_id"] is not None:
            return {"id": linked_probe["probe_name"],
                    "name": linked_probe["probe_name"],
                    "gene_id": linked_probe["gene_id"],
                    "gene_name": linked_probe["gene_name"],
                    "node_type": "linked",
                    "depth": depth}
        else:
            return {"id": linked_probe["probe_name"],
                    "name": linked_probe["probe_name"],
                    "gene_id": None,
                    "gene_name": linked_probe["probe_name"],
                    "node_type": "linked",
                    "depth": depth}

    @staticmethod
    def read_expression_network_lstrap(network_file, species_id, description, score_type="rank", pcc_cutoff=0.7, limit=30):
        # build conversion table for sequences
        sequences = Sequence.query.filter_by(species_id=species_id).all()

        sequence_dict = {}  # key = sequence name uppercase, value internal id
        for s in sequences:
            sequence_dict[s.name.upper()] = s.id

        # Add network method first
        network_method = ExpressionNetworkMethod(species_id, description, score_type)

        db.session.add(network_method)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(e)

        network = {}

        with open(network_file) as fin:
            for line in fin:
                query, hits = line.strip().split(' ')
                query = query.replace(':', '')

                sequence = re.sub('\.\d$', '', query)

                network[query] = {
                    "probe": query,
                    "sequence_id": sequence_dict[sequence.upper()] if sequence.upper() in sequence_dict.keys() else None,
                    "linked_probes": [],
                    "total_count": 0,
                    "method_id": network_method.id
                }

                for i, h in enumerate(hits.split('\t')):
                    name, value = h.split('(')
                    value = float(value.replace(')', ''))
                    if value > pcc_cutoff:
                        network[query]["total_count"] += 1
                        if i < limit:
                            s = re.sub('\.\d$', '', name)
                            link = {"probe_name": name,
                                    "gene_name": s,
                                    "gene_id": sequence_dict[s.upper()] if s.upper() in sequence_dict.keys() else None,
                                    "link_score": i,
                                    "link_pcc": value}
                            network[query]["linked_probes"].append(link)

                network[query]["network"] = json.dumps(network[query]["linked_probes"])

            # add nodes in sets of 400 to avoid sending to much in a single query
        new_nodes = []
        for _, n in network.items():
            new_nodes.append(n)
            if len(new_nodes) > 400:
                db.engine.execute(ExpressionNetwork.__table__.insert(), new_nodes)
                new_nodes = []

        db.engine.execute(ExpressionNetwork.__table__.insert(), new_nodes)

        return network_method.id