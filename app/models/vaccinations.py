from app import db
from datetime import datetime, date
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Dict, Any, List
from app.models.animals import Animals
from app.models.vaccines import Vaccines
from app.models.user import User
from app.models.base_model import BaseModel, TimestampMixin, ValidationError

class Vaccinations(BaseModel, TimestampMixin):
    """Modelo para vacunaciones aplicadas a animales.

    Unificado con BaseModel para CRUD, filtros y estadísticas.
    """
    __tablename__ = "vaccinations"
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)
    application_date = db.Column(db.Date, nullable=False)
    apprentice_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relaciones optimizadas
    animals = db.relationship('Animals', back_populates='vaccinations', lazy='joined')
    vaccines = db.relationship('Vaccines', back_populates='vaccinations', lazy='joined')
    apprentice = db.relationship('User', foreign_keys=[apprentice_id], lazy='joined')
    instructor = db.relationship('User', foreign_keys=[instructor_id], lazy='joined')
    
    # Índices optimizados para consultas frecuentes
    __table_args__ = (
        db.Index('idx_vaccinations_animal', 'animal_id'),
        db.Index('idx_vaccinations_vaccine', 'vaccine_id'),
        db.Index('idx_vaccinations_date', 'application_date'),
        db.Index('idx_vaccinations_instructor', 'instructor_id'),
        db.Index('idx_vaccinations_apprentice', 'apprentice_id'),
        # Índices compuestos para consultas complejas
        db.Index('idx_vaccinations_animal_date', 'animal_id', 'application_date'),
        db.Index('idx_vaccinations_animal_vaccine', 'animal_id', 'vaccine_id'),
        db.Index('idx_vaccinations_date_instructor', 'application_date', 'instructor_id'),
        db.Index('idx_vaccinations_vaccine_date', 'vaccine_id', 'application_date'),
    )

    # Configuración BaseModel
    _searchable_fields = []
    _filterable_fields = ['animal_id', 'vaccine_id', 'instructor_id', 'apprentice_id']
    _sortable_fields = ['id', 'application_date', 'created_at']
    _required_fields = ['animal_id', 'vaccine_id', 'application_date', 'instructor_id']
    _eager_relations = ['animals', 'vaccines']

    def _validate_instance(self):
        errors = []
        if self.application_date and self.application_date > date.today():
            errors.append('La fecha de aplicación no puede ser futura')
        if errors:
            raise ValidationError('; '.join(errors))

    def to_json(self, include_relations=False, namespace_format=False):
        data = self.to_dict(include_relations=False)
        data['application_date'] = self.application_date.strftime('%Y-%m-%d') if self.application_date else None
        if include_relations:
            if self.animals:
                data['animal'] = {
                    'id': self.animals.id,
                    'record': self.animals.record,
                    'sex': self.animals.sex.value if self.animals.sex else None,
                    'status': self.animals.status.value if self.animals.status else None
                }
            if self.vaccines:
                data['vaccine'] = {
                    'id': self.vaccines.id,
                    'name': self.vaccines.name,
                    'route_administration': self.vaccines.route_administration.value if self.vaccines.route_administration else None
                }
            if self.apprentice:
                data['apprentice'] = {
                    'id': self.apprentice.id,
                    'fullname': getattr(self.apprentice, 'fullname', 'Unknown'),
                    'role': self.apprentice.role.value if getattr(self.apprentice, 'role', None) else None
                }
            if self.instructor:
                data['instructor'] = {
                    'id': self.instructor.id,
                    'fullname': getattr(self.instructor, 'fullname', 'Unknown'),
                    'role': self.instructor.role.value if getattr(self.instructor, 'role', None) else None
                }
        return data

    def __repr__(self):
        """Representación string del modelo"""
        return f'<Vaccination {self.id}: Animal {self.animal_id} - Vaccine {self.vaccine_id}>'
    
    @classmethod
    def validate_for_namespace(cls, data: Dict[str, Any]) -> List[str]:  # extender validaciones específicas
        errors = super().validate_for_namespace(data)
        # Validar fecha
        if 'application_date' in data:
            try:
                if isinstance(data['application_date'], str):
                    datetime.strptime(data['application_date'], '%Y-%m-%d')
            except Exception:
                errors.append('La fecha de aplicación debe tener formato YYYY-MM-DD')
        # Validar FK existentes (simplificado)
        if data.get('animal_id') and not Animals.query.get(data['animal_id']):
            errors.append('El animal especificado no existe')
        if data.get('vaccine_id') and not Vaccines.query.get(data['vaccine_id']):
            errors.append('La vacuna especificada no existe')
        if data.get('instructor_id') and not User.query.get(data['instructor_id']):
            errors.append('El instructor especificado no existe')
        if data.get('apprentice_id') and not User.query.get(data['apprentice_id']):
            errors.append('El aprendiz especificado no existe')
        # Evitar duplicados
        if all(k in data for k in ['animal_id', 'vaccine_id', 'application_date']):
            existing = cls.query.filter(
                cls.animal_id == data['animal_id'],
                cls.vaccine_id == data['vaccine_id'],
                cls.application_date == data['application_date']
            ).first()
            if existing:
                errors.append('Ya existe una vacunación con esos datos')
        return errors

    @classmethod
    def get_statistics_for_namespace(cls):  # conservar API previa
        total = cls.query.count()
        return {'total_vaccinations': total}
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Vaccination {self.id}: Animal {self.animal_id} - Vaccine {self.vaccine_id}>'
    

    