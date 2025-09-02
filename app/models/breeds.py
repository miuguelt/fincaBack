from app import db

class Breeds(db.Model):
    __tablename__ = 'breeds'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False)

    animals = db.relationship('Animals', back_populates='breed')

    species = db.relationship('Species', back_populates='breeds', lazy='joined')

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'species_id': self.species_id,
            'species': self.species.to_json() if self.species else None
        }