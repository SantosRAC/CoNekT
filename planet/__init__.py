from flask import Flask, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager

from flask_admin import Admin

from flask_debugtoolbar import DebugToolbarExtension

# Set up app, database and login manager before importing models and controllers
# Important for db_create script

app = Flask(__name__)

app.config.from_object('config')

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

toolbar = DebugToolbarExtension(app)

# Import all models here

from planet.models.users import User
from planet.models.species import Species
from planet.models.sequences import Sequence
from planet.models.go import GO
from planet.models.interpro import Interpro
from planet.models.gene_families import GeneFamilyMethod, GeneFamily
from planet.models.coexpression_clusters import CoexpressionClusteringMethod, CoexpressionCluster

# Import all relationships (tables for many-to-many relationships)

import planet.models.relationships

# Import controllers and register as blueprint

from planet.controllers.main import main
from planet.controllers.auth import auth
from planet.controllers.sequence import sequence
from planet.controllers.species import species
from planet.controllers.go import go
from planet.controllers.interpro import interpro
from planet.controllers.family import family

app.register_blueprint(main)
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(sequence, url_prefix='/sequence')
app.register_blueprint(species, url_prefix='/species')
app.register_blueprint(go, url_prefix='/go')
app.register_blueprint(interpro, url_prefix='/interpro')
app.register_blueprint(family, url_prefix='/family')

# Admin panel
from planet.admin.views import MyAdminIndexView
from planet.admin.views import SpeciesAdminView

admin = Admin(app, index_view=MyAdminIndexView())
admin.add_view(SpeciesAdminView(Species, db.session))

# Custom error handler for 404 errors

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404

@app.errorhandler(403)
def page_not_found(e):
    return render_template('error/403.html'), 403