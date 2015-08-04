from planet import app,db
from planet.models.interpro import Interpro
from build.parser.interpro import Parser as InterproParser


def populate_interpro(filename, empty=True):
    # If required empty the table first
    if empty:
        try:
            db.session.query(Interpro).delete()
            db.session.commit()
        except:
            db.session.rollback()

    interpro_parser = InterproParser()

    interpro_parser.readfile(filename)

    for domain in interpro_parser.domains:
        interpro = Interpro(domain.label, domain.description)

        db.session.add(interpro)

    db.session.commit()
