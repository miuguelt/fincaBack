from app import db 
import enum
from datetime import datetime, date
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin, ValidationError
from app.models.breeds import Breeds
import logging

logger = logging.getLogger(__name__)

class Sex(enum.Enum):
    """Enumeración para el sexo de los animales"""
    Hembra = 'Hembra'
    Macho = 'Macho'
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

class AnimalStatus(enum.Enum):
    """Enumeración para el estado de los animales"""
    Vivo = 'Vivo'
    Vendido = 'Vendido'
    Muerto = 'Muerto'
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]
    
class Animals(BaseModel, TimestampMixin):
    """Modelo optimizado para animales con funcionalidades CRUD avanzadas"""
    __tablename__ = 'animals'
    
    id = db.Column(db.Integer, primary_key=True)
    sex = db.Column(db.Enum(Sex), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    weight = db.Column(db.Integer, nullable=False)
    record = db.Column(db.String(255), nullable=False, unique=True)
    status = db.Column(db.Enum(AnimalStatus), default=AnimalStatus.Vivo)

    breeds_id = db.Column(db.Integer, db.ForeignKey('breeds.id'), nullable=False) 
    idFather = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=True)
    idMother = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=True)
    
    # Configuraciones del modelo base
    _searchable_fields = ['record']
    _filterable_fields = ['sex', 'status', 'breeds_id', 'birth_date', 'weight']
    _sortable_fields = ['id', 'record', 'birth_date', 'weight', 'created_at']
    _required_fields = ['sex', 'birth_date', 'weight', 'record', 'breeds_id']
    _unique_fields = ['record']

    # Relaciones optimizadas con eager loading estratégico
    breed = db.relationship('Breeds', back_populates='animals', lazy='joined')
    father = db.relationship('Animals', remote_side=[id], foreign_keys=[idFather], lazy='select')
    mother = db.relationship('Animals', remote_side=[id], foreign_keys=[idMother], lazy='select')

    # Relaciones con lazy loading para evitar consultas innecesarias
    treatments = db.relationship('Treatments', back_populates='animals', lazy='dynamic')
    vaccinations = db.relationship('Vaccinations', back_populates='animals', lazy='dynamic')
    diseases = db.relationship('AnimalDiseases', back_populates='animal', lazy='dynamic')
    controls = db.relationship('Control', back_populates='animals', lazy='dynamic', 
                              order_by='desc(Control.checkup_date)')
    genetic_improvements = db.relationship('GeneticImprovements', back_populates='animals', lazy='dynamic')
    animal_fields = db.relationship('AnimalFields', back_populates='animal', lazy='dynamic')
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_animals_breed', 'breeds_id'),
        db.Index('idx_animals_father', 'idFather'),
        db.Index('idx_animals_mother', 'idMother'),
        db.Index('idx_animals_status', 'status'),
        db.Index('idx_animals_birth_date', 'birth_date'),
        db.Index('idx_animals_record', 'record'),
        db.Index('idx_animals_status_breed', 'status', 'breeds_id'),
    )

    # ====================================================================
    # VALIDACIONES ESPECÍFICAS
    # ====================================================================
    
    def _validate_instance(self):
        """Validaciones específicas para animales"""
        errors = []
        
        # Validar peso
        if self.weight is not None and self.weight <= 0:
            errors.append("El peso debe ser mayor a 0")
        
        # Validar fecha de nacimiento
        if self.birth_date and self.birth_date > date.today():
            errors.append("La fecha de nacimiento no puede ser futura")
        
        # Validar genealogía (no puede ser padre/madre de sí mismo)
        if self.id and (self.idFather == self.id or self.idMother == self.id):
            errors.append("Un animal no puede ser padre/madre de sí mismo")
        
        # Validar que padre y madre sean diferentes
        if self.idFather and self.idMother and self.idFather == self.idMother:
            errors.append("El padre y la madre deben ser animales diferentes")
        
        if errors:
            raise ValidationError("; ".join(errors))
    

    
    # NOTE: CRUD operations (create, update, delete) and list/pagination are
    # provided by BaseModel (create(), update(), delete(), get_paginated(),
    # get_statistics()). To reduce duplication and keep the model surface
    # minimal, specialized helper methods were removed. If namespaces need to
    # perform preprocessing (enum coercion or FK checks) do it in the
    # namespace or via lightweight validators.
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Animal {self.id}: {self.record}>'
