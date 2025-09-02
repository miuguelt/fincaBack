from app import db

class GeneticImprovements(db.Model):
    __tablename__ = 'genetic_improvements'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    details = db.Column(db.String(255), nullable=False)
    results = db.Column(db.String(255), nullable=False)
    genetic_event_techique = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)

    animals = db.relationship('Animals', back_populates='genetic_improvements', lazy='joined')

    def to_json(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'details': self.details,
            'results': self.results,
            'genetic_event_techique': self.genetic_event_techique,
            'animal_id': self.animal_id,
            'animals': self.animals.to_json() if self.animals else None
        }
