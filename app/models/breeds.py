from app import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel

class Breeds(BaseModel):
    """Modelo para razas de animales optimizado para namespaces"""
    __tablename__ = 'breeds'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False)

    # Relaciones optimizadas
    animals = db.relationship('Animals', back_populates='breed', lazy='dynamic')
    species = db.relationship('Species', back_populates='breeds', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['name']
    _filterable_fields = ['species_id']
    _sortable_fields = ['id', 'name']
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_breeds_species', 'species_id'),
        db.Index('idx_breeds_name', 'name'),
        db.Index('idx_breeds_name_species', 'name', 'species_id'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto Breed a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la raza.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Breed {self.id}: {self.name}>'