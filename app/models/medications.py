from app import db
import enum

class RouteAdministration(enum.Enum):
    Oral = "Oral"
    Inyección = "Inyección"
    Intranasal = "Intranasal"
    Tópica = "Tópica"

class Medications(db.Model):
    __tablename__ = 'medications'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    indications = db.Column(db.String(255), nullable=False)
    contraindications = db.Column(db.String(255), nullable=False)
    route_administration = db.Column(db.Enum(RouteAdministration), nullable=False)
    availability = db.Column(db.Boolean, nullable=False, default=True)

    treatments = db.relationship('TreatmentMedications', back_populates='medications')

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'indications': self.indications,
            'contraindications': self.contraindications,
            'route_administration': self.route_administration.value,
            'availability': self.availability
        }