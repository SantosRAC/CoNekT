from planet import db

class Interpro(db.Model):
    __tablename__ = 'interpro'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), unique=True, index=True)
    description = db.Column(db.Text)
