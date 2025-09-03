from app import db
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class Species(BaseModel, TimestampMixin):
    """Modelo para especies de animales optimizado para namespaces"""
    __tablename__ = 'species'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    
    # Relaciones optimizadas
    breeds = db.relationship('Breeds', back_populates='species', lazy='dynamic')

    # Configuraciones del modelo base
    _searchable_fields = ['name']
    _sortable_fields = ['id', 'name', 'created_at']
    _required_fields = ['name']
    _unique_fields = ['name']
    
    # Índices para optimización
    __table_args__ = (
        db.Index('idx_species_name', 'name'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto Species a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la especie.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Species {self.id}: {self.name}>'