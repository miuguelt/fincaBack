from app import db

class TreatmentVaccines(db.Model):
    __tablename__ = 'treatment_vaccines'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatments.id'), nullable=False)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)

    treatments = db.relationship('Treatments', back_populates='vaccines_treatments')

    vaccines = db.relationship('Vaccines', back_populates='treatments')

    def to_json(self):
        return {
            'id': self.id,
            'treatment_id': self.treatment_id,
            'vaccine_id': self.vaccine_id,
            'vaccines': self.vaccines.to_json() if self.vaccines else None
        }