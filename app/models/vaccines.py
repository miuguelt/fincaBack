from app import db
import enum
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any
from app.models.base_model import BaseModel, TimestampMixin, ValidationError

class AdministrationRoute(enum.Enum):
    """Rutas de administración de vacunas"""
    Oral = "Oral"
    Intranasal = "Intranasal"
    Tópica = "Tópica"  # Corregido: Tópica en lugar de Topica
    Intramuscular = "Intramuscular"
    Intravenosa = "Intravenosa"
    Subcutánea = "Subcutánea"
    
    # Mantener compatibilidad con código existente
    Topica = "Tópica"  # Alias para compatibilidad
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

class VaccineType(enum.Enum):
    """Tipos de vacunas disponibles"""
    Atenuada = "Atenuada"
    Inactivada = "Inactivada"
    Toxoide = "Toxoide"
    Subunidad = "Subunidad"
    Conjugada = "Conjugada"
    Recombinante = "Recombinante"
    Adn = "Adn"
    Arn = "Arn"
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

class Vaccines(BaseModel, TimestampMixin):
    """Modelo para vacunas utilizadas en el sistema.

    Ahora hereda de BaseModel para reutilizar CRUD, filtros y validaciones.
    """
    __tablename__ = 'vaccines'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dosis = db.Column(db.String(255), nullable=False)
    route_administration = db.Column(db.Enum(AdministrationRoute), nullable=False)
    vaccination_interval = db.Column(db.String(255), nullable=False)
    vaccine_type = db.Column(db.Enum(VaccineType), nullable=False)
    national_plan = db.Column(db.String(255), nullable=False)
    target_disease_id = db.Column(db.Integer, db.ForeignKey('diseases.id'), nullable=False)
    
    # Relaciones optimizadas
    diseases = db.relationship('Diseases', back_populates='vaccines', lazy='joined')
    treatments = db.relationship('TreatmentVaccines', back_populates='vaccines', lazy='dynamic')
    vaccinations = db.relationship('Vaccinations', back_populates='vaccines', lazy='dynamic')
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_vaccines_name', 'name'),
        db.Index('idx_vaccines_disease', 'target_disease_id'),
        db.Index('idx_vaccines_type', 'vaccine_type'),
        db.Index('idx_vaccines_route', 'route_administration'),
    )

    # Configuración BaseModel
    _searchable_fields = ['name', 'national_plan']
    _filterable_fields = ['target_disease_id', 'vaccine_type', 'route_administration']
    _sortable_fields = ['id', 'name', 'created_at']
    _required_fields = ['name', 'dosis', 'route_administration', 'vaccination_interval', 'vaccine_type', 'national_plan', 'target_disease_id']
    _unique_fields = ['name']
    _eager_relations = ['diseases']

    def _validate_instance(self):  # Modelo específico
        errors = []
        if self.name and len(self.name.strip()) < 2:
            errors.append('El nombre de la vacuna es demasiado corto')
        if errors:
            raise ValidationError('; '.join(errors))

    def to_json(self, include_relations: bool = False, namespace_format: bool = False):  # Mantener compatibilidad firma
        data = self.to_dict(include_relations=False)
        # Normalizar enums
        data['route_administration'] = self.route_administration.value if self.route_administration else None
        data['vaccine_type'] = self.vaccine_type.value if self.vaccine_type else None
        if include_relations and self.diseases:
            data['diseases'] = {
                'id': self.diseases.id,
                'name': getattr(self.diseases, 'name', None),
                'symptoms': getattr(self.diseases, 'symptoms', None)
            }
        if include_relations:
            # Conteos perezosos (evitar cargar listas completas)
            data['treatments_count'] = self.treatments.count() if self.treatments is not None else 0
            data['vaccinations_count'] = self.vaccinations.count() if self.vaccinations is not None else 0
        return data
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Vaccine {self.id}: {self.name}>'