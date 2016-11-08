from flask_wtf import Form
from wtforms import StringField, RadioField, SelectField
from flask_wtf.file import FileRequired, FileField, InputRequired

from planet.models.species import Species


class AddGOForm(Form):
    species_id = SelectField('Species', coerce=int)

    source = StringField('Source', [InputRequired()])

    file = FileField()

    def populate_species(self):
        self.species_id.choices = [(s.id, s.name) for s in Species.query.order_by(Species.name)]