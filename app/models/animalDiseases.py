from app import db
from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin, ValidationError
from app.models.animals import Animals
from app.models.diseases import Diseases
from app.models.user import User

class AnimalDiseases(BaseModel, TimestampMixin):
    """Modelo para enfermedades diagnosticadas en animales optimizado para namespaces"""
    __tablename__ = 'animal_diseases'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    disease_id = db.Column(db.Integer, db.ForeignKey('diseases.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diagnosis_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Activo')
    notes = db.Column(db.Text, nullable=True)

    # Relaciones optimizadas
    animal = db.relationship('Animals', back_populates='diseases', lazy='joined')
    disease = db.relationship('Diseases', back_populates='animals', lazy='joined')
    instructor = db.relationship('User', back_populates='diseases', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['notes', 'status']
    _filterable_fields = ['animal_id', 'disease_id', 'instructor_id', 'status', 'diagnosis_date']
    _sortable_fields = ['id', 'diagnosis_date', 'created_at']
    _required_fields = ['animal_id', 'disease_id', 'instructor_id', 'diagnosis_date', 'status']
    _unique_fields = [('animal_id', 'disease_id', 'diagnosis_date')]
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_animal_diseases_animal_id', 'animal_id'),
        db.Index('idx_animal_diseases_disease_id', 'disease_id'),
        db.Index('idx_animal_diseases_instructor_id', 'instructor_id'),
        db.Index('idx_animal_diseases_status', 'status'),
        db.Index('idx_animal_diseases_date', 'diagnosis_date'),
        db.UniqueConstraint('animal_id', 'disease_id', 'diagnosis_date', name='uq_animal_disease_date'),
    )

    def _validate_instance(self):
        """Validaciones específicas para enfermedades de animales"""
        errors = []
        
        # Validar fecha de diagnóstico
        if self.diagnosis_date and self.diagnosis_date > date.today():
            errors.append("La fecha de diagnóstico no puede ser futura")
        
        # Validar que el animal existe
        if self.animal_id and not Animals.query.get(self.animal_id):
            errors.append("El animal especificado no existe")
        
        # Validar que la enfermedad existe
        if self.disease_id and not Diseases.query.get(self.disease_id):
            errors.append("La enfermedad especificada no existe")
        
        # Validar que el instructor existe
        if self.instructor_id and not User.query.get(self.instructor_id):
            errors.append("El instructor especificado no existe")
        
        if errors:
            raise ValidationError("; ".join(errors))

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto AnimalDisease a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la enfermedad del animal.
        """
        return self.to_dict(include_relations=include_relations)

    def __repr__(self):
        """Representación string del modelo"""
        return f'<AnimalDisease {self.id}: Animal {self.animal_id} - Disease {self.disease_id}>'
    