from flask_restx import Namespace, Resource
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.user import User, Role
from flask_restx import fields
from app import db
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
import logging

# Importar utilidades de optimización
from app.utils.response_handler import APIResponse, ResponseFormatter
from app.utils.validators import (
    RequestValidator, PerformanceLogger, SecurityValidator
)
from app.utils.cache_manager import (
    cache_query_result, invalidate_cache_on_change
)

# Crear el namespace
users_ns = Namespace(
    'users',
    description='👥 Gestión de Usuarios del Sistema',
    path='/users'
)

logger = logging.getLogger(__name__)

# Definir modelos para este namespace
user_input_model = users_ns.model('UserInput', {
    'identification': fields.Integer(required=True, description='Número de identificación único', example=12345678),
    'fullname': fields.String(required=True, description='Nombre completo del usuario', example='Juan Pérez'),
    'password': fields.String(required=True, description='Contraseña del usuario', example='password123'),
    'email': fields.String(required=True, description='Correo electrónico único', example='juan@example.com'),
    'phone': fields.String(required=True, description='Número de teléfono (10 dígitos)', example='3001234567'),
    'address': fields.String(required=True, description='Dirección del usuario', example='Calle 123 #45-67'),
    'role': fields.String(required=True, description='Rol del usuario', enum=['Aprendiz', 'Instructor', 'Administrador'], example='Instructor'),
    'status': fields.Boolean(required=True, description='Estado activo/inactivo', example=True)
})

user_update_model = users_ns.model('UserUpdate', {
    'identification': fields.Integer(description='Número de identificación único', example=12345678),
    'fullname': fields.String(description='Nombre completo del usuario', example='Juan Pérez'),
    'password': fields.String(description='Contraseña del usuario', example='password123'),
    'email': fields.String(description='Correo electrónico único', example='juan@example.com'),
    'phone': fields.String(description='Número de teléfono (10 dígitos)', example='3001234567'),
    'address': fields.String(description='Dirección del usuario', example='Calle 123 #45-67'),
    'role': fields.String(description='Rol del usuario', enum=['Aprendiz', 'Instructor', 'Administrador'], example='Instructor'),
    'status': fields.Boolean(description='Estado activo/inactivo', example=True)
})

user_response_model = users_ns.model('UserResponse', {
    'id': fields.Integer(description='ID único del usuario'),
    'identification': fields.Integer(description='Número de identificación'),
    'fullname': fields.String(description='Nombre completo'),
    'email': fields.String(description='Correo electrónico'),
    'phone': fields.String(description='Número de teléfono'),
    'address': fields.String(description='Dirección'),
    'role': fields.String(description='Rol del usuario'),
    'status': fields.Boolean(description='Estado activo/inactivo')
})

user_list_response_model = users_ns.model('UserListResponse', {
    'users': fields.List(fields.Nested(user_response_model), description='Lista de usuarios'),
    'total': fields.Integer(description='Total de usuarios')
})

success_message_model = users_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito', example='Operación realizada exitosamente')
})

error_message_model = users_ns.model('ErrorMessage', {
    'message': fields.String(description='Mensaje de error', example='Error en la operación'),
    'error': fields.String(description='Detalles del error')
})

integrity_error_model = users_ns.model('IntegrityError', {
    'message': fields.String(description='Error de integridad', example='No se puede eliminar: existen registros relacionados'),
    'error': fields.String(description='Detalles del error de integridad')
})

@users_ns.route('/')
class UserList(Resource):
    @users_ns.doc(
        'list_users',
        description='''
        **Listar todos los usuarios del sistema**
        
        Este endpoint retorna una lista de todos los usuarios registrados en el sistema.
        
        **Filtros disponibles:**
        - `fullname`: Filtrar por nombre completo (búsqueda parcial)
        - `role`: Filtrar por rol específico (Aprendiz, Instructor, Administrador)
        - `status`: Filtrar por estado (true/false para activo/inactivo)
        
        **Ejemplos de uso:**
        - `GET /users/` - Todos los usuarios
        - `GET /users/?fullname=Juan` - Usuarios con "Juan" en el nombre
        - `GET /users/?role=Instructor` - Solo instructores
        - `GET /users/?status=true` - Solo usuarios activos
        - `GET /users/?role=Administrador&status=true` - Administradores activos
        
        **Permisos:** Requiere autenticación JWT
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'fullname': {'description': 'Filtrar por nombre completo (búsqueda parcial)', 'type': 'string'},
            'role': {'description': 'Filtrar por rol', 'type': 'string', 'enum': ['Aprendiz', 'Instructor', 'Administrador']},
            'status': {'description': 'Filtrar por estado (true/false)', 'type': 'boolean'}
        },
        responses={
            200: ('Lista de usuarios', user_list_response_model),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("users_list", ttl_seconds=300)
    @jwt_required()
    def get(self):
        """Obtener lista de usuarios con filtros opcionales"""
        try:
            # Argumentos de paginación y filtros
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 50, type=int), 100)

            # Usar método paginado y optimizado del modelo base
            pagination = User.get_paginated(
                page=page,
                per_page=per_page,
                filters=request.args,
                search_query=request.args.get('search'),
                sort_by=request.args.get('sort_by', 'id'),
                sort_order=request.args.get('sort_order', 'asc')
            )
            
            users_data = [
                user.to_json(include_relations=True, include_sensitive=False) 
                for user in pagination.items
            ]
            
            return APIResponse.success(
                data={
                    'users': users_data,
                    'total': pagination.total,
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                },
                message=f"Se encontraron {pagination.total} usuarios"
            )
            
        except ValueError as e:
            logger.warning(f"Error de validación en listado de usuarios: {str(e)}")
            return APIResponse.validation_error(
                {'pagination': 'Parámetros de paginación inválidos'}
            )
        except Exception as e:
            logger.error(f"Error listando usuarios: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINT DE ESTADÍSTICAS DE USUARIOS
# ============================================================================

@users_ns.route('/statistics')
class UsersStatistics(Resource):
    @users_ns.doc(
        'get_users_statistics',
        description='''
        **Obtener estadísticas de usuarios**
        
        Retorna estadísticas consolidadas de usuarios del sistema.
        
        **Información incluida:**
        - Total de usuarios por rol
        - Usuarios activos vs inactivos
        - Distribución de usuarios por estado
        - Actividad reciente de usuarios
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: 'Estadísticas de usuarios',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def get(self):
        """Obtener estadísticas de usuarios"""
        try:
            # Obtener estadísticas de usuarios utilizando el método genérico
            users_stats = User.get_statistics()
            
            return APIResponse.success(
                data={
                    'users': users_stats,
                    'summary': {
                        'total_users': users_stats.get('total_users', 0),
                        'active_users': users_stats.get('active_users', 0),
                        'inactive_users': users_stats.get('inactive_users', 0),
                        'administrators': users_stats.get('role_distribution', {}).get('Administrador', 0),
                        'instructors': users_stats.get('role_distribution', {}).get('Instructor', 0),
                        'apprentices': users_stats.get('role_distribution', {}).get('Aprendiz', 0)
                    }
                },
                message='Estadísticas de usuarios obtenidas exitosamente'
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de usuarios: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @users_ns.doc(
        'create_user',
        description='''
        **Crear un nuevo usuario en el sistema**
        
        Este endpoint permite crear un nuevo usuario con todos los datos requeridos.
        
        **Validaciones:**
        - El número de identificación debe ser único
        - El email debe ser único
        - El teléfono debe ser único y tener 10 dígitos
        - La contraseña se hashea automáticamente
        - El rol debe ser válido (Aprendiz, Instructor, Administrador)
        
        **Permisos:** Requiere autenticación JWT y rol de Administrador
        
        **Ejemplo de payload:**
        ```json
        {
            "identification": 12345678,
            "fullname": "Juan Pérez",
            "password": "password123",
            "email": "juan@example.com",
            "phone": "3001234567",
            "address": "Calle 123 #45-67",
            "role": "Instructor",
            "status": true
        }
        ```
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Usuario creado exitosamente', user_response_model),
            400: 'Datos de entrada inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Permisos insuficientes (se requiere rol Administrador)',
            409: 'Conflicto - Identificación, email o teléfono ya existe',
            422: 'Error de validación',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['identification', 'fullname', 'password', 'email', 'phone', 'address', 'role', 'status'],
        field_types={
            'identification': int,
            'fullname': str,
            'password': str,
            'email': str,
            'phone': str,
            'address': str,
            'role': str,
            'status': bool
        }
    )
    @invalidate_cache_on_change(['users_list', 'users_stats'])
    @jwt_required()
    def post(self):
        """Crear un nuevo usuario"""
        try:
            data = request.get_json()
            current_user_claims = get_jwt()
            
            # Validaciones específicas de usuario
            validation_errors = RequestValidator.validate_user_data(data)
            if validation_errors:
                return APIResponse.validation_error(validation_errors)
            
            # Validar rol
            try:
                role_enum = Role(data['role'])
            except ValueError:
                return APIResponse.validation_error(
                    {'role': f'Rol inválido: {data["role"]}. Valores permitidos: Aprendiz, Instructor, Administrador'}
                )
            
            # Hashear contraseña y delegar creación al modelo (valida y hace commit)
            hashed_password = generate_password_hash(data['password'])
            
            new_user = User.create(
                identification=data['identification'],
                fullname=data['fullname'],
                password=hashed_password,
                email=data['email'],
                phone=data['phone'],
                address=data['address'],
                role=role_enum,
                status=data['status']
            )
            
            logger.info(
                f"Usuario creado: ID {new_user.identification} ({new_user.fullname}) "
                f"por administrador {current_user_claims.get('identification')}"
            )
            
            # Formatear respuesta sin contraseña
            user_data = new_user.to_json()
            
            return APIResponse.created(
                data=user_data,
                message=f"Usuario {new_user.fullname} creado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            
            # Determinar tipo de error de integridad
            error_details = {}
            if 'identification' in str(e):
                error_details['identification'] = 'El número de identificación ya existe'
            elif 'email' in str(e):
                error_details['email'] = 'El email ya está registrado'
            elif 'phone' in str(e):
                error_details['phone'] = 'El teléfono ya está registrado'
            else:
                error_details['general'] = 'Datos duplicados'
            
            logger.warning(f"Error de integridad creando usuario: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details=error_details
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando usuario: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@users_ns.route('/<int:user_id>')
class UserDetail(Resource):
    @users_ns.doc(
        'get_user',
        description='''
        **Obtener información detallada de un usuario específico**
        
        Este endpoint retorna toda la información de un usuario por su ID.
        
        **Permisos:** Requiere autenticación JWT
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información del usuario', user_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Usuario no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @users_ns.marshal_with(user_response_model)
    @jwt_required()
    def get(self, user_id):
        """Obtener usuario por ID"""
        try:
            user = User.get_by_id(user_id)
            if not user:
                users_ns.abort(404, 'Usuario no encontrado')
            return user.to_json()
            
        except Exception as e:
            logger.error(f"Error obteniendo usuario {user_id}: {str(e)}")
            users_ns.abort(500, f'Error interno del servidor: {str(e)}')
    
    @users_ns.doc(
        'update_user',
        description='''
        **Actualizar información de un usuario existente**
        
        Este endpoint permite actualizar los datos de un usuario existente.
        
        **Características:**
        - Solo se actualizan los campos enviados (actualización parcial)
        - La contraseña se hashea automáticamente si se proporciona
        - Se validan las restricciones de unicidad
        
        **Permisos:** Requiere autenticación JWT y rol de Administrador
        
        **Ejemplo de payload (actualización parcial):**
        ```json
        {
            "fullname": "Juan Carlos Pérez",
            "email": "juan.carlos@example.com",
            "status": false
        }
        ```
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Usuario actualizado exitosamente', user_response_model),
            400: 'Datos de entrada inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Permisos insuficientes (se requiere rol Administrador)',
            404: 'Usuario no encontrado',
            409: 'Conflicto - Identificación, email o teléfono ya existe',
            500: 'Error interno del servidor'
        }
    )
    @users_ns.expect(user_update_model, validate=True)
    @users_ns.marshal_with(user_response_model)
    @jwt_required()
    def put(self, user_id):
        """Actualizar usuario existente"""
        try:
            # Verificar permisos de administrador con claims del JWT
            claims = get_jwt()
            if claims.get('role') != 'Administrador':
                users_ns.abort(403, 'Se requiere rol de Administrador para actualizar usuarios')
            
            # Usar el user_id del path para actualizar al usuario correcto
            user = User.get_by_id(user_id)
            if not user:
                users_ns.abort(404, 'Usuario no encontrado')

            data = request.get_json() or {}

            update_payload = {}
            mapping_fields = ['identification', 'fullname', 'email', 'phone', 'address', 'status']
            for field in mapping_fields:
                if field in data:
                    update_payload[field] = data[field]

            if 'password' in data:
                update_payload['password'] = generate_password_hash(data['password'])
            if 'role' in data:
                try:
                    update_payload['role'] = Role(data['role'])
                except ValueError:
                    users_ns.abort(400, f"Rol inválido: {data['role']}. Valores permitidos: Aprendiz, Instructor, Administrador")

            if update_payload:
                user.update(**update_payload)

            logger.info(f"Usuario {user_id} actualizado por {claims.get('identification')}")
            return user.to_json()
            
        except IntegrityError as e:
            db.session.rollback()
            error_msg = 'Error de integridad: '
            if 'identification' in str(e):
                error_msg += 'El número de identificación ya existe'
            elif 'email' in str(e):
                error_msg += 'El email ya está registrado'
            elif 'phone' in str(e):
                error_msg += 'El teléfono ya está registrado'
            else:
                error_msg += 'Datos duplicados'
            
            logger.warning(f"Error de integridad actualizando usuario {user_id}: {str(e)}")
            users_ns.abort(409, error_msg)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando usuario {user_id}: {str(e)}")
            users_ns.abort(500, f'Error interno del servidor: {str(e)}')
    
    @users_ns.doc(
        'delete_user',
        description='''
        **Eliminar un usuario del sistema**
        
        Este endpoint permite eliminar un usuario existente.
        
        **Importante:**
        - La eliminación puede fallar si el usuario tiene registros relacionados
        - Se recomienda desactivar el usuario (status=false) en lugar de eliminarlo
        - La eliminación es permanente y no se puede deshacer
        
        **Permisos:** Requiere autenticación JWT y rol de Administrador
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Usuario eliminado exitosamente', success_message_model),
            401: 'Token JWT requerido o inválido',
            403: 'Permisos insuficientes (se requiere rol Administrador)',
            404: 'Usuario no encontrado',
            409: ('Error de integridad - Usuario tiene registros relacionados', integrity_error_model),
            500: 'Error interno del servidor'
        }
    )
    @users_ns.marshal_with(success_message_model)
    @jwt_required()
    def delete(self, user_id):
        """Eliminar usuario"""
        try:
            # Verificar permisos de administrador con claims del JWT
            claims = get_jwt()
            if claims.get('role') != 'Administrador':
                users_ns.abort(403, 'Se requiere rol de Administrador para eliminar usuarios')
            
            user = User.get_by_id(user_id)
            if not user:
                users_ns.abort(404, 'Usuario no encontrado')
            user.delete()
            logger.info(f"Usuario {user_id} eliminado por {claims.get('identification')}")
            return {'message': f'Usuario {user_id} eliminado exitosamente'}
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad eliminando usuario {user_id}: {str(e)}")
            users_ns.abort(409, 'No se puede eliminar: el usuario tiene registros relacionados (vacunaciones, tratamientos, etc.)')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando usuario {user_id}: {str(e)}")
            users_ns.abort(500, f'Error interno del servidor: {str(e)}')

@users_ns.route('/status')
class UserStatus(Resource):
    @users_ns.doc(
        'get_user_status',
        description='''
        **Obtener estadísticas de usuarios por estado**
        
        Este endpoint retorna un resumen de usuarios agrupados por estado (activo/inactivo).
        
        **Información retornada:**
        - Total de usuarios activos
        - Total de usuarios inactivos
        - Porcentaje de usuarios activos
        - Total general de usuarios
        
        **Permisos:** Requiere autenticación JWT
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: 'Estadísticas de usuarios por estado',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def get(self):
        """Obtener estadísticas de usuarios por estado"""
        try:
            active_users = User.query.filter_by(status=True).count()
            inactive_users = User.query.filter_by(status=False).count()
            total_users = active_users + inactive_users
            
            return {
                'active_users': active_users,
                'inactive_users': inactive_users,
                'total_users': total_users,
                'active_percentage': round((active_users / total_users * 100) if total_users > 0 else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de usuarios: {str(e)}")
            users_ns.abort(500, f'Error interno del servidor: {str(e)}')

@users_ns.route('/roles')
class UserRoles(Resource):
    @users_ns.doc(
        'get_user_roles',
        description='''
        **Obtener distribución de usuarios por roles**
        
        Este endpoint retorna un resumen de usuarios agrupados por rol.
        
        **Información retornada:**
        - Cantidad de usuarios por cada rol (Aprendiz, Instructor, Administrador)
        - Porcentaje de distribución por rol
        - Total de usuarios
        
        **Permisos:** Requiere autenticación JWT
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: 'Distribución de usuarios por roles',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def get(self):
        """Obtener distribución de usuarios por roles"""
        try:
            aprendices = User.query.filter_by(role=Role.Aprendiz).count()
            instructores = User.query.filter_by(role=Role.Instructor).count()
            administradores = User.query.filter_by(role=Role.Administrador).count()
            total_users = aprendices + instructores + administradores
            
            return {
                'roles': {
                    'Aprendiz': {
                        'count': aprendices,
                        'percentage': round((aprendices / total_users * 100) if total_users > 0 else 0, 2)
                    },
                    'Instructor': {
                        'count': instructores,
                        'percentage': round((instructores / total_users * 100) if total_users > 0 else 0, 2)
                    },
                    'Administrador': {
                        'count': administradores,
                        'percentage': round((administradores / total_users * 100) if total_users > 0 else 0, 2)
                    }
                },
                'total_users': total_users
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo distribución de roles: {str(e)}")
            users_ns.abort(500, f'Error interno del servidor: {str(e)}')