from flask import g, Blueprint, flash, redirect, url_for, render_template, request
from sqlalchemy.sql import or_, and_

from planet.models.sequences import Sequence
from planet.models.go import GO
from planet.models.interpro import Interpro
from planet.models.gene_families import GeneFamily
from planet.models.expression_profiles import ExpressionProfile

from planet.forms.search import BasicSearchForm

search = Blueprint('search', __name__)


@search.route('/keyword/<keyword>')
def search_single_keyword(keyword):
    sequences = Sequence.query.with_entities(Sequence.id, Sequence.name).filter_by(name=keyword).all()

    go = GO.query.filter(or_(GO.description.like("%"+keyword+"%"),
                             GO.name.like("%"+keyword+"%"),
                             GO.label == keyword)).all()

    interpro = Interpro.query.filter(or_(Interpro.description.like("%"+keyword+"%"),
                                         Interpro.label == keyword)).all()

    families = GeneFamily.query.filter_by(name=keyword).all()
    profiles = ExpressionProfile.query.filter_by(probe=keyword).all()

    return render_template("search_results.html", keyword=keyword,
                           sequences=sequences,
                           go=go,
                           interpro=interpro,
                           families=families,
                           profiles=profiles)


def search_string(term_string):
    terms = term_string.split()

    sequences = Sequence.query.filter(Sequence.name.in_(terms)).all()

    go = GO.query.filter(or_(and_(*[GO.description.like("%"+term+"%") for term in terms]),
                             and_(*[GO.name.like("%"+term+"%") for term in terms]),
                             GO.label.in_(terms))).all()

    interpro = Interpro.query.filter(or_(and_(*[Interpro.description.like("%"+term+"%") for term in terms]),
                                         Interpro.label.in_(terms))).all()

    families = GeneFamily.query.filter(GeneFamily.name.in_(terms)).all()
    profiles = ExpressionProfile.query.filter(ExpressionProfile.probe.in_(terms)).all()

    return {"go": go,
            "interpro": interpro,
            "sequences": sequences,
            "families": families,
            "profiles": profiles}


@search.route('/', methods=['GET', 'POST'])
def simple():
    if not g.search_form.validate_on_submit():
        flash("Empty search term", "warning")
        return redirect(url_for('main.screen'))
    else:
        results = search_string(g.search_form.terms.data)

        return render_template("search_results.html", keyword=g.search_form.terms.data,
                               go=results["go"],
                               interpro=results["interpro"],
                               sequences=results["sequences"],
                               families=results["families"],
                               profiles=results["profiles"])