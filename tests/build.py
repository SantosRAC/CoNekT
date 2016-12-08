#!/usr/bin/env python3
import json

from flask_testing import TestCase

from planet import create_app, db


class BuildTest(TestCase):
    """
    BuildCase to check if the build functions work as planned
        * a DB will be created and filled with dummy data
        * an app will be spawned with the testing config, DO NOT run this against a database that is in use !!
        * the DB will be cleared !
    """

    def create_app(self):
        """
        Creates the app using the tests config (tests/config.py)

        :return: flask app with settings from tests/config.py
        """
        app = create_app('tests.config')
        return app

    def setUp(self):
        """
        Creates a database and fills it with sufficient dummy data to run the tests.
        """
        db.create_all()

        from planet.models.species import Species
        from planet.models.sequences import Sequence

        from planet.models.xrefs import XRef
        from planet.models.go import GO
        from planet.models.interpro import Interpro
        from planet.models.expression.profiles import ExpressionProfile
        from planet.models.expression.networks import ExpressionNetwork, ExpressionNetworkMethod
        from planet.models.expression.coexpression_clusters import CoexpressionClusteringMethod
        from planet.models.expression.specificity import ExpressionSpecificityMethod
        from planet.models.gene_families import GeneFamily, GeneFamilyMethod
        from planet.models.clades import Clade

        Species.add('mmu', 'Marek mutwiliana')
        s = Species.query.first()

        Sequence.add_from_fasta('./tests/data/mamut.cds.fasta', s.id)
        XRef.add_xref_genes_from_file(s.id, './tests/data/mamut.xref.txt')
        GO.add_from_obo('./tests/data/test_go.obo')
        GO.add_go_from_tab('./tests/data/functional_data/mamut.go.txt', s.id, source="Fake UnitTest Data")

        Interpro.add_from_xml('./tests/data/test_interpro.xml')
        Interpro.add_interpro_from_interproscan('./tests/data/functional_data/mamut.interpro.txt', s.id)

        ExpressionProfile.add_profile_from_lstrap('./tests/data/expression/mamut.tpm.matrix.txt',
                                                  './tests/data/expression/mamut.expression_annotation.txt',
                                                  s.id,
                                                  order_color_file='./tests/data/expression/mamut.expression_order_color.txt')

        ExpressionNetwork.read_expression_network_lstrap('./tests/data/expression/mamut.pcc.txt',
                                                         s.id,
                                                         'Fake UnitTest Network')

        test_network = ExpressionNetworkMethod.query.first()

        CoexpressionClusteringMethod.add_lstrap_coexpression_clusters('./tests/data/expression/mamut.mcl_clusters.txt',
                                                                      'Test cluster',
                                                                      test_network.id,
                                                                      min_size=1)

        ExpressionSpecificityMethod.calculate_specificities(s.id, s.name + " condition specific profiles", False)

        GeneFamily.add_families_from_mcl('./tests/data/comparative_data/mamut.families.mcl.txt', 'Fake Families')

        GeneFamilyMethod.update_count()

        Clade.add_clades_from_json({"Marek mutwiliana": {"species": ["mmu"], "tree": None}})
        Clade.update_clades()
        Clade.update_clades_interpro()

    def tearDown(self):
        """
        Removes test database again, so the next test can start with a clean slate
        """
        db.session.remove()
        db.drop_all()

    def test_build(self):
        from planet.models.sequences import Sequence
        from planet.models.species import Species

        s = Species.query.first()

        test_sequence = Sequence.query.filter_by(name='Gene01').first()

        test_xref = test_sequence.xrefs[0]

        test_go = test_sequence.go_labels.first()
        test_go_association = test_sequence.go_associations.filter_by(evidence=None).first()
        test_interpro = test_sequence.interpro_domains.filter_by(label='IPR000001').first()

        test_profile = test_sequence.expression_profiles.first()
        test_profile_data = json.loads(test_profile.profile)

        test_network_nodes = test_sequence.network_nodes.first()
        test_network_data = json.loads(test_network_nodes.network)

        test_cluster = test_sequence.coexpression_clusters.first()
        cluster_sequence = test_cluster.sequences.filter_by(name='Gene01').first()

        test_family = test_sequence.families.first()

        self.assertEqual(len(s.sequences.all()), 3)                        # Check if all genes are added

        self.assertEqual(test_sequence.name, 'Gene01')
        self.assertEqual(test_sequence.species_id, s.id)

        self.assertEqual(test_sequence.aliases, 'BRCA2')                # Check if alias is added and correct
        self.assertTrue('www.ensembl.org' in test_xref.url)             # Check if url is added
        self.assertEqual(test_xref.platform, 'Ensembl')                 # Check if platform is added
        self.assertEqual(test_xref.name, 'BRCA2')                       # Check if platform is added

        self.assertEqual(test_go.label, 'GO:0000003')                   # Check if go is added
        self.assertEqual(test_go.description, '"Third label"')          # Check if go description is parsed
        self.assertEqual(test_go_association.go.label, 'GO:0000001')    # Check if go parent is added

        self.assertEqual(test_interpro.label, 'IPR000001')              # Check if Interpro domain is added
        self.assertTrue('Kringle' in test_interpro.description)         # Check if description is added
        self.assertEqual(test_interpro.species_counts['mmu'], 1)        # Check if species profiles are generated

        self.assertEqual(test_profile.sequence.name, 'Gene01')          # Check if profile is linked with gene
        self.assertEqual(test_profile.probe, 'Gene01')                  # Check if probe is set
        self.assertTrue("order" in test_profile_data.keys())            # Check if profile data contains order
        self.assertTrue("data" in test_profile_data.keys())             # Check if profile data contains data
        self.assertTrue("colors" in test_profile_data.keys())           # Check if profile data contains colors

        self.assertEqual(test_network_data[0]["gene_name"], "Gene02")   # Check if network contains required fields
        self.assertEqual(test_network_data[0]["probe_name"], "Gene02")  # Check if network contains required fields
        self.assertEqual(test_network_data[0]["link_pcc"], 0.71)        # Check if network contains required fields
        self.assertEqual(test_network_data[0]["link_score"], 0)         # Check if network contains required fields

        self.assertNotEqual(cluster_sequence, None)                     # Check if gene is in cluster

        self.assertEqual(test_profile.specificities.first().condition, 'Tissue 03')         # Check if SPM worked
        self.assertAlmostEqual(test_profile.specificities.first().score, 0.62, places=2)    # Check if SPM score is correct
        self.assertAlmostEqual(test_profile.specificities.first().entropy, 1.58, places=2)  # Check if entropy is correct
        self.assertAlmostEqual(test_profile.specificities.first().tau, 0.11, places=2)      # Check if tau is correct

        self.assertEqual(len(test_family.sequences.all()), 2)           # Check if gene family contains 2 genes