from planet import db
from planet.models.expression_networks import ExpressionNetwork
from planet.models.relationships import sequence_coexpression_cluster

import json


class CoexpressionClusteringMethod(db.Model):
    __tablename__ = 'coexpression_clustering_methods'
    id = db.Column(db.Integer, primary_key=True)
    network_method_id = db.Column(db.Integer, db.ForeignKey('expression_network_methods.id'))
    method = db.Column(db.Text)

    clusters = db.relationship('CoexpressionCluster', backref='method', lazy='dynamic')


class CoexpressionCluster(db.Model):
    __tablename__ = 'coexpression_clusters'
    id = db.Column(db.Integer, primary_key=True)
    method_id = db.Column(db.Integer, db.ForeignKey('coexpression_clustering_methods.id'))
    name = db.Column(db.String(50), unique=True, index=True)

    sequences = db.relationship('Sequence', secondary=sequence_coexpression_cluster, lazy='dynamic')

    @staticmethod
    def get_cluster(cluster_id):
        cluster = CoexpressionCluster.query.get(cluster_id)

        probes = [member.probe for member in cluster.members.all()]

        network = cluster.method.network_method.probes.filter(ExpressionNetwork.probe.in_(probes)).all()

        nodes = []
        edges = []

        existing_edges = []

        for node in network:
            nodes.append({"id": node.probe,
                          "name": node.probe,
                          "gene_id": int(node.sequence_id) if node.sequence_id is not None else None,
                          "gene_name": node.gene.name if node.sequence_id is not None else node.probe,
                          "depth": 0})

            links = json.loads(node.network)

            for link in links:
                # only add links that are in the cluster !
                if link["probe_name"] in probes and [node.probe, link["probe_name"]] not in existing_edges:
                    edges.append({"source": node.probe,
                                  "target": link["probe_name"],
                                  "depth": 0,
                                  "link_score": link["link_score"],
                                  "edge_type": cluster.method.network_method.edge_type})
                    existing_edges.append([node.probe, link["probe_name"]])
                    existing_edges.append([link["probe_name"], node.probe])

        return {"nodes": nodes, "edges": edges}
