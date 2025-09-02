from app import db

class TreatmentMedications(db.Model):
    __tablename__ = 'treatment_medications'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatments.id'), nullable=False)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)

    treatments = db.relationship('Treatments', back_populates='medication_treatments')

    medications = db.relationship('Medications', back_populates='treatments')

    def to_json(self):
        return {
            'id': self.id,
            'treatment_id': self.treatment_id,
            'medication_id': self.medication_id,
            'medications': self.medications.to_json() if self.medications else None
        }