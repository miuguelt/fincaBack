from app import db
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class Diseases(BaseModel, TimestampMixin):
    """Modelo para enfermedades que pueden afectar a los animales optimizado para namespaces"""
    __tablename__ = 'diseases'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    symptoms = db.Column(db.String(255), nullable=False)
    details = db.Column(db.String(255), nullable=False)

    # Relaciones optimizadas
    animals = db.relationship('AnimalDiseases', back_populates='disease', lazy='dynamic')
    vaccines = db.relationship('Vaccines', back_populates='diseases', lazy='dynamic')

    # Configuraciones del modelo base
    _searchable_fields = ['name', 'symptoms', 'details']
    _sortable_fields = ['id', 'name', 'created_at']
    _required_fields = ['name', 'symptoms', 'details']
    _unique_fields = ['name']
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_diseases_name', 'name'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto Disease a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la enfermedad.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Disease {self.id}: {self.name}>'