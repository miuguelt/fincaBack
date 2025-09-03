from app import db
from datetime import datetime, date
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin, ValidationError
from app.models.animals import Animals
import logging

logger = logging.getLogger(__name__)

class Treatments(BaseModel, TimestampMixin):
    """Modelo optimizado para tratamientos aplicados a animales con funcionalidades CRUD avanzadas"""
    __tablename__ = 'treatments'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(255), nullable=False)
    frequency = db.Column(db.String(255), nullable=False)
    observations = db.Column(db.String(255), nullable=False)
    dosis = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    
    # Configuraciones del modelo base
    _searchable_fields = ['description', 'observations']
    _filterable_fields = ['animal_id', 'start_date', 'end_date', 'frequency']
    _sortable_fields = ['id', 'start_date', 'end_date', 'created_at']
    _required_fields = ['start_date', 'description', 'frequency', 'observations', 'dosis', 'animal_id']
    _unique_fields = []

    # Relaciones optimizadas
    animals = db.relationship('Animals', back_populates='treatments', lazy='joined')
    vaccines_treatments = db.relationship('TreatmentVaccines', back_populates='treatments', lazy='dynamic')
    medication_treatments = db.relationship('TreatmentMedications', back_populates='treatments', lazy='dynamic')
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_treatments_animal', 'animal_id'),
        db.Index('idx_treatments_start_date', 'start_date'),
        db.Index('idx_treatments_end_date', 'end_date'),
        db.Index('idx_treatments_animal_date', 'animal_id', 'start_date'),
        db.Index('idx_treatments_date_range', 'start_date', 'end_date'),
    )
    
    # ====================================================================
    # VALIDACIONES ESPECÍFICAS
    # ====================================================================
    
    def _validate_instance(self):
        """Validaciones específicas para tratamientos"""
        errors = []
        
        # Validar fechas
        if self.start_date and self.start_date > date.today():
            errors.append("La fecha de inicio no puede ser futura")
        
        if self.end_date:
            if self.end_date < self.start_date:
                errors.append("La fecha de fin no puede ser anterior a la fecha de inicio")
            if self.end_date > date.today():
                errors.append("La fecha de fin no puede ser futura")
        
        # Validar campos de texto no vacíos
        if not self.description or not self.description.strip():
            errors.append("La descripción no puede estar vacía")
        
        if not self.frequency or not self.frequency.strip():
            errors.append("La frecuencia no puede estar vacía")
        
        if not self.dosis or not self.dosis.strip():
            errors.append("La dosis no puede estar vacía")
        
        if errors:
            raise ValidationError("; ".join(errors))
    
    # ====================================================================
    # MÉTODOS CRUD ESPECÍFICOS
    # ====================================================================
    
    # NOTE: Treatment creation should use BaseModel.create().
    # Keep instance helpers (complete_treatment, extend_treatment) and
    # validation logic in _validate_instance. Namespaces should:
    #  - validate incoming data
    #  - ensure animal exists and is in proper state
    #  - hash/prepare fields if needed
    #  - call Treatments.create(**data)
    
    def complete_treatment(self, end_date: date = None) -> 'Treatments':
        """Completar tratamiento estableciendo fecha de fin"""
        if self.end_date:
            raise ValidationError("El tratamiento ya está completado")
        
        completion_date = end_date or date.today()
        
        if completion_date < self.start_date:
            raise ValidationError("La fecha de finalización no puede ser anterior al inicio")
        
        return self.update(end_date=completion_date)
    
    def extend_treatment(self, new_end_date: date) -> 'Treatments':
        """Extender duración del tratamiento"""
        if new_end_date <= self.start_date:
            raise ValidationError("La nueva fecha debe ser posterior al inicio del tratamiento")
        
        if self.end_date and new_end_date <= self.end_date:
            raise ValidationError("La nueva fecha debe ser posterior a la fecha actual de fin")
        
        return self.update(end_date=new_end_date)
    
    def get_duration_days(self) -> int:
        """Calcular duración del tratamiento en días"""
        if not self.end_date:
            return (date.today() - self.start_date).days
        return (self.end_date - self.start_date).days
    
    def is_active(self) -> bool:
        """Verificar si el tratamiento está activo"""
        today = date.today()
        if self.start_date > today:
            return False  # Aún no ha comenzado
        if self.end_date and self.end_date < today:
            return False  # Ya terminó
        return True
    
    # ====================================================================
    # MÉTODOS DE CONSULTA ESPECIALIZADOS (REFACTORIZADOS)
    # ====================================================================
    # Los métodos como get_by_animal, get_active_treatments, etc., 
    # ahora se manejan a través de `get_paginated` con filtros.

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto Treatment a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos del tratamiento.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Treatment {self.id}: {self.description[:30]}...>'