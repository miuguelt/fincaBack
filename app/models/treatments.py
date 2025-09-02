from app import db

class Treatments(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(255), nullable=False)
    frequency = db.Column(db.String(255), nullable=False)
    observations = db.Column(db.String(255), nullable=False)
    dosis = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)

    animals = db.relationship('Animals', back_populates='treatments')
    vaccines_treatments = db.relationship('TreatmentVaccines', back_populates='treatments')
    medication_treatments = db.relationship('TreatmentMedications', back_populates='treatments')


    def to_json(self):
        return {
            'id': self.id,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'description': self.description,
            'frequency': self.frequency,
            'observations': self.observations,
            'dosis': self.dosis,
            'animal_id': self.animal_id,
            'animals': self.animals.to_json() if self.animals else None,
            'medication_treatments': [medication_treatment.to_json() for medication_treatment in self.medication_treatments],
            'vaccines_treatments': [vaccine_treatment.to_json() for vaccine_treatment in self.vaccines_treatments]
            
        }