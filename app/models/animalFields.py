from app import db
from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin, ValidationError
from app.models.animals import Animals
from app.models.fields import Fields

class AnimalFields(BaseModel, TimestampMixin):
    """Modelo para asignaciones de animales a campos/potreros optimizado para namespaces"""
    __tablename__ = 'animal_fields'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)
    assignment_date = db.Column(db.Date, nullable=False)
    removal_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relaciones optimizadas
    animal = db.relationship('Animals', back_populates='animal_fields', lazy='joined')
    field = db.relationship('Fields', back_populates='animal_fields', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['notes']
    _filterable_fields = ['animal_id', 'field_id', 'assignment_date', 'removal_date']
    _sortable_fields = ['id', 'assignment_date', 'removal_date', 'created_at']
    _required_fields = ['animal_id', 'field_id', 'assignment_date']
    _unique_fields = [('animal_id', 'field_id', 'assignment_date')]
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_animal_fields_animal_id', 'animal_id'),
        db.Index('idx_animal_fields_field_id', 'field_id'),
        db.Index('idx_animal_fields_assignment_date', 'assignment_date'),
        db.Index('idx_animal_fields_removal_date', 'removal_date'),
        db.UniqueConstraint('animal_id', 'field_id', 'assignment_date', name='uq_animal_field_date'),
    )

    def _validate_instance(self):
        """Validaciones específicas para asignaciones de animales a campos"""
        errors = []
        
        # Validar fechas
        if self.assignment_date and self.assignment_date > date.today():
            errors.append("La fecha de asignación no puede ser futura")
        
        if self.removal_date:
            if self.removal_date < self.assignment_date:
                errors.append("La fecha de retiro no puede ser anterior a la fecha de asignación")
            if self.removal_date > date.today():
                errors.append("La fecha de retiro no puede ser futura")
        
        # Validar que el animal existe
        if self.animal_id and not Animals.query.get(self.animal_id):
            errors.append("El animal especificado no existe")
        
        # Validar que el campo existe
        if self.field_id and not Fields.query.get(self.field_id):
            errors.append("El campo especificado no existe")
        
        if errors:
            raise ValidationError("; ".join(errors))

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto AnimalField a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la asignación.
        """
        return self.to_dict(include_relations=include_relations)

    def __repr__(self):
        """Representación string del modelo"""
        return f'<AnimalField {self.id}: Animal {self.animal_id} - Field {self.field_id}>'