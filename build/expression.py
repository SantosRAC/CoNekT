import json

from build.parser.planet.expression_plot import Parser as ExpressionPlotParser
from build.parser.planet.expression_network import Parser as NetworkParser
from planet import db
from planet.models.sequences import Sequence
from planet.models.expression_profiles import ExpressionProfile


def parse_expression_plot(plotfile, conversion):
    plot = ExpressionPlotParser()
    plot.read_plot(plotfile, conversion)

    sequences = Sequence.query.all()

    sequence_dict = {}
    for s in sequences:
        sequence_dict[s.name.upper()] = s

    for probe, profile in plot.profiles.items():

        gene_id = plot.probe_list[probe].upper()

        output = {"order": plot.conditions,
                  "data": profile}

        if gene_id in sequence_dict.keys():
            db.session.add(ExpressionProfile(probe, sequence_dict[gene_id].id, json.dumps(output)))
        else:
            db.session.add(ExpressionProfile(probe, None, json.dumps(output)))

    try:
        db.session.commit()
    except:
        db.session.rollback()


def parse_expression_network(network_file, species, description):

    network_parser = NetworkParser()
    network_parser.read_expression_network(network_file)

    print(json.dumps(network_parser.network["267637_at"], sort_keys=True, indent=4, separators=(',', ': ')))


