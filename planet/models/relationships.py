from planet import db


sequence_go = db.Table('sequence_go',
                       db.Column('id', db.Integer, primary_key=True),
                       db.Column('sequence_id', db.Integer, db.ForeignKey('sequences.id'), index=True),
                       db.Column('go_id', db.Integer, db.ForeignKey('go.id'), index=True)
                       )

sequence_interpro = db.Table('sequence_interpro',
                             db.Column('id', db.Integer, primary_key=True),
                             db.Column('sequence_id', db.Integer, db.ForeignKey('sequences.id'), index=True),
                             db.Column('interpro_id', db.Integer, db.ForeignKey('interpro.id'), index=True),
                             )

sequence_family = db.Table('sequence_family',
                           db.Column('id', db.Integer, primary_key=True),
                           db.Column('sequence_id', db.Integer, db.ForeignKey('sequences.id'), index=True),
                           db.Column('gene_family_id', db.Integer, db.ForeignKey('gene_families.id'), index=True)
                           )

sequence_coexpression_cluster = \
    db.Table('sequence_coexpression_cluster',
             db.Column('id', db.Integer, primary_key=True),
             db.Column('sequence_id', db.Integer, db.ForeignKey('sequences.id'), index=True),
             db.Column('coexpression_cluster_id', db.Integer, db.ForeignKey('coexpression_clusters.id'), index=True)
             )

sequence_xref = db.Table('sequence_xref',
                         db.Column('id', db.Integer, primary_key=True),
                         db.Column('sequence_id', db.Integer, db.ForeignKey('sequences.id'), index=True),
                         db.Column('xref_id', db.Integer, db.ForeignKey('xrefs.id'), index=True)
                         )

family_xref = db.Table('family_xref',
                       db.Column('id', db.Integer, primary_key=True),
                       db.Column('gene_family_id', db.Integer, db.ForeignKey('gene_families.id'), index=True),
                       db.Column('xref_id', db.Integer, db.ForeignKey('xrefs.id'), index=True)
                       )

class SequenceCoexpressionClusterAssociation(db.Model):
    __tablename__ = 'sequence_coexpression_cluster'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    probe = db.Column(db.String(50), index=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'))
    coexpression_cluster_id = db.Column(db.Integer, db.ForeignKey('coexpression_clusters.id'))


class SequenceFamilyAssociation(db.Model):
    __tablename__ = 'sequence_family'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'))
    gene_family_id = db.Column(db.Integer, db.ForeignKey('gene_families.id'))

    sequence = db.relationship('Sequence', lazy='joined')
    family = db.relationship('GeneFamily', lazy='joined')


class SequenceInterproAssociation(db.Model):
    __tablename__ = 'sequence_interpro'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'))
    interpro_id = db.Column(db.Integer, db.ForeignKey('interpro.id'))
    start = db.Column(db.Integer, default=None)
    stop = db.Column(db.Integer, default=None)

    domain = db.relationship('Interpro', lazy='select')


class SequenceGOAssociation(db.Model):
    __tablename__ = 'sequence_go'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequences.id'))
    go_id = db.Column(db.Integer, db.ForeignKey('go.id'))

    evidence = db.Column(db.Enum('EXP', 'IDA', 'IPI', 'IMP', 'IGI', 'IEP',
                                 'ISS', 'ISO', 'ISA', 'ISM', 'IGC', 'IBA', 'IBD', 'IKR', 'IRD', 'RCA',
                                 'TAS', 'NAS', 'IC', 'ND', 'IEA', name='evidence'))
    source = db.Column(db.Text)


class ClusterGOEnrichment(db.Model):
    __tablename__ = 'cluster_go_enrichment'

    id = db.Column(db.Integer, primary_key=True)
    cluster_id = db.Column(db.Integer, db.ForeignKey('coexpression_clusters.id'), index=True)
    go_id = db.Column(db.Integer, db.ForeignKey('go.id'), index=True)

    """
    Counts required to calculate the enrichment,
    store here for quick access
    """
    cluster_count = db.Column(db.Integer)
    cluster_size = db.Column(db.Integer)
    go_count = db.Column(db.Integer)
    go_size = db.Column(db.Integer)

    """
    Enrichment score (log-transformed), p-value and corrected p-value. Calculated using the hypergeometric
    distribution and applying FDR correction (aka. BH)
    """
    enrichment = db.Column(db.Float)
    p_value = db.Column(db.Float)
    corrected_p_value = db.Column(db.Float)


class ProbeGOEnrichment(db.Model):
    __tablename__ = 'probe_go_enrichment'

    id = db.Column(db.Integer, primary_key=True)
    probe_id = db.Column(db.Integer, db.ForeignKey('expression_network.id'), index=True)
    go_id = db.Column(db.Integer, db.ForeignKey('go.id'), index=True)

    """
    Counts required to calculate the enrichment,
    store here for quick access
    """
    cluster_count = db.Column(db.Integer)
    cluster_size = db.Column(db.Integer)
    go_count = db.Column(db.Integer)
    go_size = db.Column(db.Integer)

    """
    Enrichment score (log-transformed), p-value and corrected p-value. Calculated using the hypergeometric
    distribution and applying FDR correction (aka. BH)
    """
    enrichment = db.Column(db.Float)
    p_value = db.Column(db.Float)
    corrected_p_value = db.Column(db.Float)
