from app import db
from datetime import datetime
from typing import List, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.base_model import BaseModel, ValidationError
from app.utils.model_validators import ValidationRules
from sqlalchemy import func
import enum
import logging

logger = logging.getLogger(__name__)


class Role(enum.Enum):
    Aprendiz = 'Aprendiz'
    Instructor = 'Instructor'
    Administrador = 'Administrador'

    @classmethod
    def get_choices(cls):
        return [(c.value, c.value) for c in cls]


class User(BaseModel):
    """Modelo mínimo de usuario; delega CRUD a BaseModel.

    Keep model surface small: validations in _validate_instance,
    password helpers, and lightweight serializers for namespaces.
    """
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    identification = db.Column(db.BigInteger, unique=True, nullable=False)
    fullname = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(40), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    role = db.Column(db.Enum(Role), nullable=False)
    status = db.Column(db.Boolean, default=True)

    # Model configuration for BaseModel helpers
    _searchable_fields = ['fullname', 'email', 'identification']
    _filterable_fields = ['role', 'status', 'identification']
    _sortable_fields = ['id', 'fullname', 'email', 'created_at']
    _required_fields = ['identification', 'fullname', 'password', 'email', 'phone', 'role']
    _unique_fields = ['identification', 'email', 'phone']

    # Relationships (names must match back_populates on related models)
    diseases = db.relationship('AnimalDiseases', back_populates='instructor', lazy='dynamic')
    vaccines_as_apprentice = db.relationship('Vaccinations', foreign_keys='Vaccinations.apprentice_id', back_populates='apprentice', lazy='dynamic')
    vaccines_as_instructor = db.relationship('Vaccinations', foreign_keys='Vaccinations.instructor_id', back_populates='instructor', lazy='dynamic')

    __table_args__ = (
        db.Index('idx_user_email', 'email'),
        db.Index('idx_user_identification', 'identification'),
        db.Index('idx_user_role', 'role'),
        db.Index('idx_user_status', 'status'),
        db.Index('idx_user_phone', 'phone'),
    )

    def _validate_instance(self):
        """Validaciones específicas para usuarios"""
        errors: List[str] = []

        # Reuse centralized validators
        try:
            errs = ValidationRules.validate_user_data({
                'identification': self.identification,
                'fullname': self.fullname,
                'email': self.email,
                'phone': self.phone,
                'address': self.address,
                'role': self.role.value if self.role else None
            })
            errors.extend(errs)
        except Exception as e:
            logger.debug(f"Validator error: {e}")

        # Password length check when plaintext provided (hashed bcrypt ~60 chars)
        if self.password and len(self.password) < 60:
            if len(self.password) < 8:
                errors.append("La contraseña debe tener al menos 8 caracteres")

        if errors:
            raise ValidationError('; '.join(errors))

    @classmethod
    def validate_for_namespace(cls, data: Dict[str, Any]) -> List[str]:
        """Validación específica para uso en namespaces"""
        from app.utils.model_validators import UserValidationRules
        
        errors = []
        
        # Usar validadores especializados
        errors.extend(UserValidationRules.validate_user_data(data))
        
        # Validar rol si está presente
        if 'role' in data:
            errors.extend(UserValidationRules.validate_role(data['role']))
        
        return errors

    def to_json(self, include_relations: bool = False, include_sensitive: bool = False, namespace_format: bool = False) -> Dict[str, Any]:
        """
        Serialización JSON optimizada para namespaces.
        
        Args:
            include_relations: Incluir contadores de relaciones
            include_sensitive: Incluir datos sensibles (email, teléfono completos)
            namespace_format: Si usar formato específico para namespaces
        """
        try:
            if namespace_format:
                # Formato específico para namespaces - sin datos sensibles por defecto
                result = {
                    'id': self.id,
                    'identification': self.identification,
                    'fullname': self.fullname,
                    'email': self.email if include_sensitive else self._mask_email(),
                    'phone': self.phone if include_sensitive else self._mask_phone(),
                    'address': self.address if include_sensitive else 'Dirección privada',
                    'role': self.role.value if self.role else None,
                    'status': self.status,
                    'is_active': self.status
                }
            else:
                # Formato estándar
                result = {
                    'id': self.id,
                    'identification': self.identification,
                    'fullname': self.fullname,
                    'email': self.email if include_sensitive else self._mask_email(),
                    'phone': self.phone if include_sensitive else self._mask_phone(),
                    'address': self.address if include_sensitive else 'Dirección privada',
                    'role': self.role.value if self.role else None,
                    'status': self.status
                }

            if include_relations:
                try:
                    result.update({
                        'diseases_count': self.diseases.count(),
                        'vaccines_as_apprentice_count': self.vaccines_as_apprentice.count(),
                        'vaccines_as_instructor_count': self.vaccines_as_instructor.count()
                    })
                except Exception:
                    pass

            return result
        except Exception as e:
            logger.error(f"Error serializing user {getattr(self, 'id', None)}: {e}")
            return {'id': getattr(self, 'id', None), 'error': str(e)}
    
    def _mask_email(self) -> str:
        """Enmascarar email para proteger privacidad"""
        if self.email and '@' in self.email:
            return self.email[:3] + '***@' + self.email.split('@')[1]
        return '***'
    
    def _mask_phone(self) -> str:
        """Enmascarar teléfono para proteger privacidad"""
        if self.phone and len(self.phone) >= 5:
            return self.phone[:3] + '***' + self.phone[-2:]
        return '***'
    
    @classmethod
    def get_statistics_for_namespace(cls) -> Dict[str, Any]:
        """Estadísticas optimizadas para namespaces"""
        stats = cls.get_statistics()
        
        try:
            # Estadísticas por rol
            role_stats = db.session.query(
                cls.role, func.count(cls.role)
            ).group_by(cls.role).all()
            stats['by_role'] = {str(role): count for role, count in role_stats}
            
            # Usuarios activos vs inactivos
            active_count = cls.query.filter(cls.status == True).count()
            inactive_count = cls.query.filter(cls.status == False).count()
            stats['by_status'] = {
                'active': active_count,
                'inactive': inactive_count,
                'total': active_count + inactive_count
            }
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas de usuarios: {e}")
            stats['calculation_errors'] = str(e)
        
        return stats

    def set_password(self, password: str) -> None:
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password, password)

    # Role helpers
    def is_admin(self) -> bool:
        return self.role == Role.Administrador

    def is_instructor(self) -> bool:
        return self.role == Role.Instructor

    def is_apprentice(self) -> bool:
        return self.role == Role.Aprendiz

    def can_manage_animals(self) -> bool:
        return self.role in [Role.Administrador, Role.Instructor]

    def can_perform_vaccinations(self) -> bool:
        return self.role in [Role.Administrador, Role.Instructor]
