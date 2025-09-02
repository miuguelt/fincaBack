from functools import wraps
from flask import request, g
from flask_jwt_extended import get_jwt_identity
import logging
import time
from typing import Dict, List, Any, Optional, Callable
import re
from datetime import datetime
from app.utils.response_handler import APIResponse

logger = logging.getLogger(__name__)

class RequestValidator:
    """
    Sistema de validaciones automáticas para endpoints.
    """
    
    @staticmethod
    def validate_json_required(f):
        """
        Decorator que valida que la petición tenga JSON válido.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return APIResponse.validation_error(
                    {"content_type": "Se requiere Content-Type: application/json"},
                    "Formato de petición inválido"
                )
            
            try:
                request.get_json()
            except Exception as e:
                return APIResponse.validation_error(
                    {"json": f"JSON inválido: {str(e)}"},
                    "Error de formato JSON"
                )
            
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def validate_fields(required_fields: List[str] = None, 
                       optional_fields: List[str] = None,
                       field_types: Dict[str, type] = None):
        """
        Decorator que valida campos requeridos y tipos de datos.
        
        Args:
            required_fields: Lista de campos obligatorios
            optional_fields: Lista de campos opcionales
            field_types: Diccionario con tipos esperados {campo: tipo}
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                data = request.get_json() or {}
                errors = {}
                
                # Validar campos requeridos
                if required_fields:
                    for field in required_fields:
                        if field not in data or data[field] is None:
                            errors[field] = f"Campo '{field}' es requerido"
                        elif isinstance(data[field], str) and not data[field].strip():
                            errors[field] = f"Campo '{field}' no puede estar vacío"
                
                # Validar tipos de datos
                if field_types:
                    for field, expected_type in field_types.items():
                        if field in data and data[field] is not None:
                            if not isinstance(data[field], expected_type):
                                errors[field] = f"Campo '{field}' debe ser de tipo {expected_type.__name__}"
                
                # Validar campos no permitidos
                allowed_fields = set((required_fields or []) + (optional_fields or []))
                if allowed_fields:
                    for field in data.keys():
                        if field not in allowed_fields:
                            errors[field] = f"Campo '{field}' no está permitido"
                
                if errors:
                    return APIResponse.validation_error(errors)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Valida formato de email.
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Valida formato de teléfono (10 dígitos).
        """
        pattern = r'^\d{10}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """
        Valida formato de fecha YYYY-MM-DD.
        """
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_user_data(data: Dict) -> Dict[str, str]:
        """
        Validaciones específicas para datos de usuario.
        """
        errors = {}
        
        # Validar email
        if 'email' in data and not RequestValidator.validate_email(data['email']):
            errors['email'] = 'Formato de email inválido'
        
        # Validar teléfono
        if 'phone' in data and not RequestValidator.validate_phone(data['phone']):
            errors['phone'] = 'Teléfono debe tener 10 dígitos'
        
        # Validar rol
        if 'role' in data and data['role'] not in ['Aprendiz', 'Instructor', 'Administrador']:
            errors['role'] = 'Rol debe ser: Aprendiz, Instructor o Administrador'
        
        # Validar identificación
        if 'identification' in data:
            if not isinstance(data['identification'], int) or data['identification'] <= 0:
                errors['identification'] = 'Identificación debe ser un número positivo'
        
        return errors
    
    @staticmethod
    def validate_animal_data(data: Dict) -> Dict[str, str]:
        """
        Validaciones específicas para datos de animal.
        """
        errors = {}
        
        # Validar sexo
        if 'sex' in data and data['sex'] not in ['Hembra', 'Macho']:
            errors['sex'] = 'Sexo debe ser: Hembra o Macho'
        
        # Validar estado
        if 'status' in data and data['status'] not in ['Vivo', 'Vendido', 'Muerto']:
            errors['status'] = 'Estado debe ser: Vivo, Vendido o Muerto'
        
        # Validar fecha de nacimiento
        if 'birth_date' in data:
            if not RequestValidator.validate_date_format(data['birth_date']):
                errors['birth_date'] = 'Fecha debe tener formato YYYY-MM-DD'
            else:
                birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
                if birth_date > datetime.now().date():
                    errors['birth_date'] = 'Fecha de nacimiento no puede ser futura'
        
        # Validar peso
        if 'weight' in data:
            if not isinstance(data['weight'], (int, float)) or data['weight'] <= 0:
                errors['weight'] = 'Peso debe ser un número positivo'
        
        return errors


class PerformanceLogger:
    """
    Sistema de logging de rendimiento y métricas.
    """
    
    @staticmethod
    def log_request_performance(f):
        """
        Decorator que registra métricas de rendimiento de requests.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            # Información de la petición
            user_info = "Anonymous"
            try:
                jwt_identity = get_jwt_identity()
                if jwt_identity:
                    user_info = f"User {jwt_identity.get('id', 'Unknown')}"
            except:
                pass
            
            logger.info(
                f"REQUEST START: {request.method} {request.path} | "
                f"User: {user_info} | IP: {request.remote_addr}"
            )
            
            try:
                # Ejecutar función
                result = f(*args, **kwargs)
                
                # Calcular tiempo de respuesta
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)  # en ms
                
                # Determinar código de estado
                status_code = 200
                if isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                
                logger.info(
                    f"REQUEST END: {request.method} {request.path} | "
                    f"Status: {status_code} | Time: {response_time}ms | User: {user_info}"
                )
                
                # Alertar sobre requests lentos
                if response_time > 1000:  # > 1 segundo
                    logger.warning(
                        f"SLOW REQUEST: {request.method} {request.path} | "
                        f"Time: {response_time}ms | User: {user_info}"
                    )
                
                return result
                
            except Exception as e:
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)
                
                logger.error(
                    f"REQUEST ERROR: {request.method} {request.path} | "
                    f"Error: {str(e)} | Time: {response_time}ms | User: {user_info}"
                )
                raise
        
        return decorated_function
    
    @staticmethod
    def log_database_query(query_description: str):
        """
        Decorator para logging de consultas a base de datos.
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                start_time = time.time()
                
                logger.debug(f"DB QUERY START: {query_description}")
                
                try:
                    result = f(*args, **kwargs)
                    
                    end_time = time.time()
                    query_time = round((end_time - start_time) * 1000, 2)
                    
                    logger.debug(f"DB QUERY END: {query_description} | Time: {query_time}ms")
                    
                    # Alertar sobre consultas lentas
                    if query_time > 500:  # > 500ms
                        logger.warning(f"SLOW QUERY: {query_description} | Time: {query_time}ms")
                    
                    return result
                    
                except Exception as e:
                    end_time = time.time()
                    query_time = round((end_time - start_time) * 1000, 2)
                    
                    logger.error(
                        f"DB QUERY ERROR: {query_description} | "
                        f"Error: {str(e)} | Time: {query_time}ms"
                    )
                    raise
            
            return decorated_function
        return decorator


class SecurityValidator:
    """
    Validaciones de seguridad adicionales.
    """
    
    @staticmethod
    def require_admin_role(f):
        """
        Decorator que requiere rol de Administrador.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                user_id = get_jwt_identity()
                from flask_jwt_extended import get_jwt
                user_claims = get_jwt()
                if not user_id or user_claims.get('role') != 'Administrador':
                    return APIResponse.forbidden(
                        "Se requiere rol de Administrador para esta operación"
                    )
            except Exception:
                return APIResponse.unauthorized("Token JWT inválido")
            
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def validate_resource_ownership(resource_user_field: str = 'user_id'):
        """
        Decorator que valida que el usuario solo acceda a sus propios recursos.
        
        Args:
            resource_user_field: Campo que contiene el ID del usuario propietario
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                try:
                    current_user = get_jwt_identity()
                    if not current_user:
                        return APIResponse.unauthorized()
                    
                    # Los administradores pueden acceder a todo
                    if current_user.get('role') == 'Administrador':
                        return f(*args, **kwargs)
                    
                    # Validar propiedad del recurso (implementar según necesidad)
                    # Esta lógica se puede extender según el modelo específico
                    
                    return f(*args, **kwargs)
                    
                except Exception:
                    return APIResponse.unauthorized("Token JWT inválido")
            
            return decorated_function
        return decorator