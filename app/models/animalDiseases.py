from app import db

class AnimalDiseases(db.Model):
    __tablename__ = 'animal_diseases'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    status = db.Column(db.Boolean, nullable=False, default=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    disease_id = db.Column(db.Integer, db.ForeignKey('diseases.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diagnosis_date = db.Column(db.Date, nullable=False)

    animals = db.relationship('Animals', back_populates='diseases', lazy='joined')
    diseases = db.relationship('Diseases', back_populates='animals', lazy='joined')
    instructors = db.relationship('User', back_populates='diseases', lazy='joined')

    def to_json(self):
        return {
            'id': self.id,
            'animal_id': self.animal_id,
            'disease_id': self.disease_id,
            'instructor_id': self.instructor_id,
            'diagnosis_date': self.diagnosis_date.isoformat() if self.diagnosis_date else None,
            'animals': self.animals.to_json() if self.animals else None,
            'diseases': self.diseases.to_json() if self.diseases else None,
            'instructors': self.instructors.to_json() if self.instructors else None,
            'status': self.status

        }
    