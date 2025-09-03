from app import db
import enum
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class LandStatus(enum.Enum):
    """Estados posibles para los campos/potreros"""
    Disponible = "Disponible"
    Ocupado = "Ocupado"
    Mantenimiento = "Mantenimiento"
    Restringido = "Restringido"
    Dañado = "Dañado"
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

class Fields(BaseModel, TimestampMixin):
    """Modelo para campos/potreros de la finca optimizado para namespaces"""
    __tablename__ = "fields"
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    ubication = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.String(255), nullable=False)
    state = db.Column(db.Enum(LandStatus), nullable=False)
    handlings = db.Column(db.String(255), nullable=False)
    gauges = db.Column(db.String(255), nullable=False)
    area = db.Column(db.String(255), nullable=False)
    food_type_id = db.Column(db.Integer, db.ForeignKey('food_types.id'), nullable=True)

    # Relaciones optimizadas
    animal_fields = db.relationship('AnimalFields', back_populates='field', lazy='dynamic')
    food_types = db.relationship('FoodTypes', back_populates='fields', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['name', 'ubication', 'handlings']
    _filterable_fields = ['state', 'food_type_id', 'capacity', 'area']
    _sortable_fields = ['id', 'name', 'capacity', 'area', 'created_at']
    _required_fields = ['name', 'ubication', 'capacity', 'state', 'handlings', 'gauges', 'area']
    _unique_fields = ['name']
    
    # Índices optimizados para consultas frecuentes
    __table_args__ = (
        db.Index('idx_fields_name', 'name'),
        db.Index('idx_fields_state', 'state'),
        db.Index('idx_fields_food_type', 'food_type_id'),
        # Índices compuestos para consultas de disponibilidad
        db.Index('idx_fields_state_food_type', 'state', 'food_type_id'),
        db.Index('idx_fields_state_capacity', 'state', 'capacity'),
        db.Index('idx_fields_name_state', 'name', 'state'),
    )
    
    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto Field a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos del campo.
        """
        return self.to_dict(include_relations=include_relations)

    def __repr__(self):
        """Representación string del modelo"""
        return f'<Field {self.id}: {self.name}>'
