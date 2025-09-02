from app import db
import enum

class AdministrationRoute(enum.Enum):
    Oral = "Oral"
    Intranasal = "Intranasal"
    Topica = "Tópica"
    Intramuscular = "Intramuscular"
    Intravenosa = "Intravenosa"
    Subcutánea = "Subcutánea"

class VaccineType(enum.Enum):
    Atenuada = "Atenuada"
    Inactivada = "Inactivada"
    Toxoide = "Toxoide"
    Subunidad = "Subunidad"
    Conjugada = "Conjugada"
    Recombinante = "Recombinante"
    Adn = "Adn"
    Arn = "Arn"

class Vaccines(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dosis = db.Column(db.String(255), nullable=False)
    route_administration = db.Column(db.Enum(AdministrationRoute), nullable=False)
    vaccination_interval = db.Column(db.String(255), nullable=False)
    vaccine_type = db.Column(db.Enum(VaccineType), nullable=False)
    national_plan = db.Column(db.String(255), nullable=False)

    target_disease_id = db.Column(db.Integer, db.ForeignKey('diseases.id'), nullable=False)
    
    diseases = db.relationship('Diseases', back_populates='vaccines')

    treatments = db.relationship('TreatmentVaccines', back_populates='vaccines')
    vaccinations = db.relationship('Vaccinations', back_populates='vaccines')

    def to_json(self):
        return{
            'id' : self.id,
            'name' : self.name,
            'dosis' : self.dosis,
            'route_administration' : self.route_administration.value,
            'vaccination_interval' : self.vaccination_interval,
            'target_disease_id' : self.target_disease_id,
            'vaccine_type' : self.vaccine_type.value,
            'national_plan' : self.national_plan,
            'diseases' : self.diseases.to_json()
        }