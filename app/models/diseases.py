from app import db

class Diseases(db.Model):
    id = db.Column(db.Integer, autoincrement = True ,primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    syntoptoms = db.Column(db.String(255), nullable=False)
    details = db.Column(db.String(255), nullable=False)

    animals = db.relationship('AnimalDiseases', back_populates='diseases')
    vaccines = db.relationship('Vaccines', back_populates='diseases')

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'syntoptoms': self.syntoptoms,
            'details': self.details
        }