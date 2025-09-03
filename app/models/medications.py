from app import db
import enum
from typing import Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class RouteAdministration(enum.Enum):
    """Rutas de administración de medicamentos"""
    Oral = "Oral"
    Inyección = "Inyección"
    Intranasal = "Intranasal"
    Tópica = "Tópica"
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

class Medications(BaseModel, TimestampMixin):
    """Modelo para medicamentos utilizados en tratamientos optimizado para namespaces"""
    __tablename__ = 'medications'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=False)
    indications = db.Column(db.String(255), nullable=False)
    contraindications = db.Column(db.String(255), nullable=False)
    route_administration = db.Column(db.Enum(RouteAdministration), nullable=False)
    availability = db.Column(db.Boolean, nullable=False, default=True)

    # Relaciones optimizadas
    treatments = db.relationship('TreatmentMedications', back_populates='medications', lazy='dynamic')

    # Configuraciones del modelo base
    _searchable_fields = ['name', 'description', 'indications', 'contraindications']
    _filterable_fields = ['route_administration', 'availability']
    _sortable_fields = ['id', 'name', 'created_at']
    _required_fields = ['name', 'description', 'indications', 'contraindications', 'route_administration', 'availability']
    _unique_fields = ['name']
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_medications_name', 'name'),
        db.Index('idx_medications_availability', 'availability'),
        db.Index('idx_medications_route', 'route_administration'),
    )


    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Medication {self.id}: {self.name}>'