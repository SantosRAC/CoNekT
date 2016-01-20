from flask import Blueprint, redirect, url_for, render_template

from planet import cache
from planet.models.clades import Clade

clade = Blueprint('clade', __name__)


@clade.route('/')
def clade_overview():
    """
    For lack of a better alternative redirect users to the main page
    """
    return redirect(url_for('main.screen'))


@clade.route('/view/<clade_id>')
@cache.cached()
def clade_view(clade_id):
    """
    Get a sequence based on the ID and show the details for this sequence

    :param sequence_id: ID of the sequence
    """
    current_clade = Clade.query.get_or_404(clade_id)

    return render_template('clade.html', clade=current_clade)