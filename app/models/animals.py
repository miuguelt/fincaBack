from app import db 
import enum
from datetime import datetime, date
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, ValidationError
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
    
class Animals(BaseModel):
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
    _sortable_fields = ['id', 'record', 'birth_date', 'weight']
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
        
        # Validar que la raza exista
        if self.breeds_id and not Breeds.query.get(self.breeds_id):
            errors.append("La raza especificada no existe")
        
        # Validar que el padre exista si se especifica
        if self.idFather and not Animals.query.get(self.idFather):
            errors.append("El padre especificado no existe")
        
        # Validar que la madre exista si se especifica
        if self.idMother and not Animals.query.get(self.idMother):
            errors.append("La madre especificada no existe")
        
        if errors:
            raise ValidationError("; ".join(errors))
    
    @classmethod
    def validate_for_namespace(cls, data: Dict[str, Any]) -> List[str]:
        """Validación específica para uso en namespaces"""
        from app.utils.model_validators import AnimalValidationRules
        
        errors = []
        
        # Usar validadores especializados
        errors.extend(AnimalValidationRules.validate_animal_data(data))
        
        # Validar enums si están presentes
        if 'sex' in data:
            errors.extend(AnimalValidationRules.validate_sex(data['sex']))
        
        if 'status' in data:
            errors.extend(AnimalValidationRules.validate_status(data['status']))
        
        # Validar foreign keys
        if 'breeds_id' in data:
            from app.utils.model_validators import ValidationRules
            errors.extend(ValidationRules.validate_foreign_key_exists(
                data['breeds_id'], Breeds, "raza"
            ))
        
        return errors
    
    def to_json(self, include_relations: List[str] = None, namespace_format: bool = False) -> Dict[str, Any]:
        """
        Serialización JSON optimizada para namespaces.
        
        Args:
            include_relations: Relaciones a incluir
            namespace_format: Si usar formato específico para namespaces
        """
        if namespace_format:
            # Formato específico para namespaces con campos renombrados
            result = {
                'idAnimal': self.id,
                'sex': self.sex.value if self.sex else None,
                'birth_date': self.birth_date.isoformat() if self.birth_date else None,
                'weight': self.weight,
                'record': self.record,
                'status': self.status.value if self.status else None,
                'breeds_id': self.breeds_id,
                'idFather': self.idFather,
                'idMother': self.idMother,
            }
            
            # Incluir información de la raza si está disponible
            if self.breed:
                result['breed'] = {
                    'id': self.breed.id,
                    'breed': self.breed.breed,
                    'species_id': self.breed.species_id
                }
            
            # Incluir relaciones específicas si se solicitan
            if include_relations:
                if 'father' in include_relations and self.father:
                    result['father'] = {
                        'id': self.father.id,
                        'record': self.father.record,
                        'sex': self.father.sex.value if self.father.sex else None
                    }
                
                if 'mother' in include_relations and self.mother:
                    result['mother'] = {
                        'id': self.mother.id,
                        'record': self.mother.record,
                        'sex': self.mother.sex.value if self.mother.sex else None
                    }
            
            return result
        else:
            # Usar serialización base
            return super().to_json(include_relations)
    
    @classmethod
    def get_optimized_query(cls, include_relations: List[str] = None):
        """Consulta optimizada con eager loading para namespaces"""
        query = cls.query
        
        # Siempre incluir breed para evitar consultas N+1
        query = query.options(joinedload(cls.breed))
        
        # Incluir relaciones adicionales según se solicite
        if include_relations:
            if 'father' in include_relations:
                query = query.options(joinedload(cls.father))
            if 'mother' in include_relations:
                query = query.options(joinedload(cls.mother))
            if 'breed.species' in include_relations:
                query = query.options(
                    joinedload(cls.breed).joinedload(Breeds.species)
                )
        
        return query
    
    @classmethod
    def get_statistics_for_namespace(cls) -> Dict[str, Any]:
        """Estadísticas optimizadas para namespaces"""
        stats = cls.get_statistics()
        
        # Agregar estadísticas específicas de animales
        try:
            # Estadísticas por sexo
            sex_stats = db.session.query(
                cls.sex, func.count(cls.sex)
            ).group_by(cls.sex).all()
            stats['by_sex'] = {str(sex): count for sex, count in sex_stats}
            
            # Estadísticas por raza (top 5)
            breed_stats = db.session.query(
                Breeds.breed, func.count(cls.id)
            ).join(cls.breed).group_by(Breeds.breed).order_by(
                func.count(cls.id).desc()
            ).limit(5).all()
            stats['top_breeds'] = [
                {'breed': breed, 'count': count} 
                for breed, count in breed_stats
            ]
            
            # Promedio de peso por estado
            if hasattr(cls, 'status'):
                weight_stats = db.session.query(
                    cls.status, 
                    func.avg(cls.weight).label('avg_weight'),
                    func.count(cls.id).label('count')
                ).group_by(cls.status).all()
                stats['weight_by_status'] = {
                    str(status): {
                        'average_weight': round(float(avg_weight), 2) if avg_weight else 0,
                        'count': count
                    }
                    for status, avg_weight, count in weight_stats
                }
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas de animales: {e}")
            stats['calculation_errors'] = str(e)
        
        return stats
    

    
    # NOTE: CRUD operations (create, update, delete) and list/pagination are
    # provided by BaseModel (create(), update(), delete(), get_paginated(),
    # get_statistics()). To reduce duplication and keep the model surface
    # minimal, specialized helper methods were removed. If namespaces need to
    # perform preprocessing (enum coercion or FK checks) do it in the
    # namespace or via lightweight validators.
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Animal {self.id}: {self.record}>'
