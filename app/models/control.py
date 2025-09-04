from app import db 
import enum
from datetime import datetime, date
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin, ValidationError
from app.models.animals import Animals

class HealthStatus(enum.Enum):
    """Estados de salud para controles veterinarios"""
    Excelente = "Excelente"
    Bueno = "Bueno"
    Regular = "Regular"
    Malo = "Malo"
    
    @classmethod
    def get_choices(cls):
        """Retorna las opciones disponibles para namespaces"""
        return [(choice.value, choice.value) for choice in cls]

# Mantener compatibilidad con código existente
HealtStatus = HealthStatus

class Control(BaseModel, TimestampMixin):
    """Modelo para controles de salud de animales optimizado para namespaces"""
    __tablename__ = 'control'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    checkup_date = db.Column(db.Date, nullable=False)
    healt_status = db.Column(db.Enum(HealthStatus), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)

    # Relación optimizada con Animals
    animals = db.relationship('Animals', back_populates='controls', lazy='select')

    # Configuraciones del modelo base
    _searchable_fields = ['description']
    _filterable_fields = ['animal_id', 'healt_status', 'checkup_date']
    _sortable_fields = ['id', 'checkup_date', 'created_at']
    _required_fields = ['checkup_date', 'healt_status', 'description', 'animal_id']
    
    # Índices para optimización de consultas críticas
    __table_args__ = (
        db.Index('idx_control_animal_date', 'animal_id', 'checkup_date'),
        db.Index('idx_control_status', 'healt_status'),
        db.Index('idx_control_date', 'checkup_date'),
        db.Index('idx_control_animal_status', 'animal_id', 'healt_status'),
        db.Index('idx_control_date_status', 'checkup_date', 'healt_status'),
    )

    def _validate_instance(self):
        """Validaciones específicas para el modelo Control."""
        errors = []
        if self.checkup_date and self.checkup_date > date.today():
            errors.append("La fecha de control no puede ser futura.")
        
        # Validar que el animal existe
        if self.animal_id and not Animals.exists(self.animal_id):
            errors.append(f"El animal con id {self.animal_id} no existe.")

        if errors:
            raise ValidationError("; ".join(errors))

    @classmethod
    def validate_for_namespace(cls, data: Dict[str, Any]) -> List[str]:
        """Validación específica para uso en namespaces"""
        from app.utils.model_validators import MedicalValidationRules, ValidationRules
        
        errors = []
        
        # Validar fecha de control
        if 'checkup_date' in data:
            errors.extend(MedicalValidationRules.validate_medical_date(
                data['checkup_date'], "fecha de control"
            ))
        
        # Validar estado de salud
        if 'healt_status' in data:
            errors.extend(ValidationRules.validate_enum_value(
                data['healt_status'], HealthStatus, "estado de salud"
            ))
        
        # Validar descripción
        if 'description' in data:
            errors.extend(ValidationRules.validate_string_length(
                data['description'], "descripción", min_length=1, max_length=255
            ))
        
        # Validar que el animal existe
        if 'animal_id' in data:
            errors.extend(ValidationRules.validate_foreign_key_exists(
                data['animal_id'], Animals, "animal"
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
            result = {
                'id': self.id,
                'checkup_date': self.checkup_date.isoformat() if self.checkup_date else None,
                'healt_status': self.healt_status.value if self.healt_status else None,
                'description': self.description,
                'animal_id': self.animal_id,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            }
            
            # Incluir información básica del animal si está disponible
            if self.animals:
                result['animal'] = {
                    'id': self.animals.id,
                    'record': self.animals.record,
                    'sex': self.animals.sex.value if self.animals.sex else None,
                    'status': self.animals.status.value if self.animals.status else None
                }
            
            return result
        else:
            # Usar serialización base
            return super().to_json(include_relations)
    
    @classmethod
    def get_optimized_query(cls, include_relations: List[str] = None):
        """Consulta optimizada con eager loading para namespaces"""
        query = cls.query
        
        # Siempre incluir animal básico para evitar consultas N+1
        query = query.options(joinedload(cls.animals))
        
        # Incluir relaciones adicionales según se solicite
        if include_relations:
            if 'animal.breed' in include_relations:
                query = query.options(
                    joinedload(cls.animals).joinedload(Animals.breed)
                )
        
        return query
    
    @classmethod
    def get_recent_controls(cls, days=30, limit=100):
        """Obtener controles recientes optimizado"""
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)
        
        return cls.get_optimized_query().filter(
            cls.checkup_date >= cutoff_date
        ).limit(limit).all()
    
    @classmethod
    def get_by_health_status(cls, status, limit=100):
        """Obtener controles por estado de salud con consulta optimizada"""
        return cls.get_optimized_query().filter(
            cls.healt_status == status
        ).order_by(cls.checkup_date.desc()).limit(limit).all()
    
    @classmethod
    def get_animal_latest_control(cls, animal_id):
        """Obtener el último control de un animal específico"""
        return cls.get_optimized_query().filter(
            cls.animal_id == animal_id
        ).first()
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Control {self.id}: {self.healt_status.value if self.healt_status else "Unknown"} - {self.checkup_date}>'