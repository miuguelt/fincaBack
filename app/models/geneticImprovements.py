from app import db
from datetime import date
from typing import Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class GeneticImprovements(BaseModel, TimestampMixin):
    """Modelo para mejoras genéticas aplicadas a animales optimizado para namespaces"""
    __tablename__ = 'genetic_improvements'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    details = db.Column(db.String(255), nullable=False)
    results = db.Column(db.String(255), nullable=False)
    genetic_event_technique = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)

    # Relaciones optimizadas
    animals = db.relationship('Animals', back_populates='genetic_improvements', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['details', 'results', 'genetic_event_technique']
    _filterable_fields = ['date', 'animal_id']
    _sortable_fields = ['id', 'date', 'created_at']
    _required_fields = ['date', 'details', 'results', 'genetic_event_technique', 'animal_id']
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_genetic_improvements_animal', 'animal_id'),
        db.Index('idx_genetic_improvements_date', 'date'),
        db.Index('idx_genetic_improvements_technique', 'genetic_event_technique'),
    )



    def __repr__(self):
        """Representación string del modelo"""
        return f'<GeneticImprovement {self.id}: {self.genetic_event_technique}>'
