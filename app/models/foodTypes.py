from app import db
from datetime import datetime, date
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class FoodTypes(BaseModel, TimestampMixin):
    """Modelo para tipos de alimentos/cultivos optimizado para namespaces"""
    __tablename__ = 'food_types'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    food_type = db.Column(db.String(255), nullable=False, unique=True)
    sowing_date = db.Column(db.Date, nullable=False)
    harvest_date = db.Column(db.Date, nullable=True)
    area = db.Column(db.Integer, nullable=False)
    handlings = db.Column(db.String(255), nullable=False)
    gauges = db.Column(db.String(255), nullable=False)

    # Relaciones optimizadas
    fields = db.relationship('Fields', back_populates='food_types', lazy='dynamic')

    # Configuraciones del modelo base
    _searchable_fields = ['food_type', 'handlings']
    _filterable_fields = ['sowing_date', 'harvest_date', 'area']
    _sortable_fields = ['id', 'food_type', 'sowing_date', 'harvest_date', 'area', 'created_at']
    _required_fields = ['food_type', 'sowing_date', 'area', 'handlings', 'gauges']
    _unique_fields = ['food_type']
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_food_types_food_type', 'food_type'),
        db.Index('idx_food_types_sowing_date', 'sowing_date'),
        db.Index('idx_food_types_harvest_date', 'harvest_date'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto FoodType a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos del tipo de alimento.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<FoodType {self.id}: {self.food_type}>'