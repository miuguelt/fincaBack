from flask_restx import Namespace, Resource
from flask import request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies
)
from app.models.user import User
from flask_restx import fields
from app import db
from werkzeug.security import check_password_hash
from datetime import timedelta, datetime, timezone
import logging

# Crear el namespace
auth_ns = Namespace(
    'auth',
    description='🔐 Autenticación y Autorización',
    path='/auth'
)

logger = logging.getLogger(__name__)

# Definir modelos para este namespace
login_model = auth_ns.model('Login', {
    'identification': fields.Integer(required=True, description='Número de identificación del usuario', example=12345678),
    'password': fields.String(required=True, description='Contraseña del usuario', example='password123')
})

login_response_model = auth_ns.model('LoginResponse', {
    'message': fields.String(description='Mensaje de éxito'),
    'user': fields.Raw(description='Datos del usuario autenticado'),
    'access_token': fields.String(description='Token de acceso JWT'),
    'refresh_token': fields.String(description='Token de renovación JWT')
})

refresh_response_model = auth_ns.model('RefreshResponse', {
    'message': fields.String(description='Mensaje de éxito'),
    'access_token': fields.String(description='Nuevo token de acceso JWT')
})

success_message_model = auth_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito', example='Operación realizada exitosamente')
})

error_message_model = auth_ns.model('ErrorMessage', {
    'message': fields.String(description='Mensaje de error', example='Error en la operación'),
    'error': fields.String(description='Detalles del error')
})

@auth_ns.route('/login')
class Login(Resource):
    @auth_ns.doc(
        'login_user',
        description='''
        **Autenticar usuario y generar tokens JWT**
        
        Este endpoint permite a los usuarios autenticarse en el sistema usando su número de identificación y contraseña.
        
        **Proceso de autenticación:**
        1. Valida las credenciales del usuario
        2. Genera tokens JWT (acceso y renovación)
        3. Establece cookies seguras con los tokens
        4. Retorna información del usuario autenticado
        
        **Seguridad:**
        - Los tokens se almacenan en cookies HTTPOnly para mayor seguridad
        - El token de acceso tiene una duración limitada (configurable)
        - El token de renovación permite obtener nuevos tokens de acceso
        ''',
        responses={
            200: ('Autenticación exitosa', login_response_model),
            400: 'Datos de entrada inválidos',
            401: 'Credenciales incorrectas',
            404: 'Usuario no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @auth_ns.expect(login_model, validate=True)
    def post(self):
        """Autenticar usuario y generar tokens JWT"""
        data = request.get_json()
        identification = data.get('identification')
        password = data.get('password')

        if not identification or not password:
            auth_ns.abort(400, 'Identificación y contraseña son requeridos')

        # Buscar usuario por identificación
        user = User.query.filter_by(identification=identification).first()

        if not user:
            auth_ns.abort(404, 'Usuario no encontrado')

        if not user.status:
            auth_ns.abort(401, 'Usuario inactivo')

        # Usar método optimizado del modelo para verificar contraseña
        if not user.check_password(password):
            auth_ns.abort(401, 'Credenciales incorrectas')

        try:
            # Crear tokens JWT - Compatible con Flask-JWT-Extended 4.6.0
            # El campo 'identity' debe ser string, datos adicionales van en 'additional_claims'
            user_identity = str(user.id)  # Flask-JWT-Extended 4.6.0 requiere string
            
            user_claims = {
                'id': user.id,
                'identification': user.identification,
                'role': user.role.value,
                'fullname': user.fullname
            }

            access_token = create_access_token(
                identity=user_identity,
                additional_claims=user_claims,
                expires_delta=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))
            )
            refresh_token = create_refresh_token(
                identity=user_identity,
                additional_claims=user_claims
            )

            # Crear respuesta usando formato optimizado para namespaces
            response_data = {
                'message': 'Autenticación exitosa',
                'user': user.to_json(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }

            response = jsonify(response_data)

            # Establecer cookies seguras
            set_access_cookies(response, access_token)
            set_refresh_cookies(response, refresh_token)

            logger.info(f"Usuario {user.identification} autenticado exitosamente")
            return response

        except Exception as e:
            logger.error(f"Error en la generación de tokens o cookies para el usuario {identification}: {str(e)}")
            auth_ns.abort(500, f'Error interno del servidor al procesar la sesión: {str(e)}')

@auth_ns.route('/refresh')
class RefreshToken(Resource):
    @auth_ns.doc(
        'refresh_token',
        description='''
        **Renovar token de acceso usando refresh token**
        
        Este endpoint permite obtener un nuevo token de acceso usando el refresh token.
        
        **Uso:**
        - Requiere un refresh token válido (en cookie o header Authorization)
        - Genera un nuevo token de acceso con tiempo de vida renovado
        - Mantiene la misma identidad del usuario
        
        **Seguridad:**
        - Solo funciona con refresh tokens válidos y no expirados
        - El nuevo token mantiene los mismos permisos del usuario
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Token renovado exitosamente', refresh_response_model),
            401: 'Refresh token inválido o expirado',
            500: 'Error interno del servidor'
        }
    )
    # Removed marshal_with to prevent double serialization when returning a Response
    @jwt_required(refresh=True)
    def post(self):
        """Renovar token de acceso usando refresh token"""
        try:
            # Obtener identity (string) y claims del token
            user_identity = get_jwt_identity()

            # Crear nuevo token de acceso con la misma estructura
            new_access_token = create_access_token(
                identity=user_identity,
                additional_claims={
                    'id': user_identity.get('id'),
                    'identification': user_identity.get('identification'),
                    'role': user_identity.get('role'),
                    'fullname': user_identity.get('fullname')
                },
                expires_delta=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))
            )

            response_data = {
                'message': 'Token renovado exitosamente',
                'access_token': new_access_token
            }

            response = jsonify(response_data)
            set_access_cookies(response, new_access_token)

            logger.info(f"Token renovado para usuario {user_identity.get('identification')}")
            return response

        except Exception as e:
            logger.error(f"Error en refresh: {str(e)}")
            auth_ns.abort(500, f'Error interno del servidor: {str(e)}')

@auth_ns.route('/logout')
class Logout(Resource):
    @auth_ns.doc(
        'logout_user',
        description='''
        **Cerrar sesión y limpiar tokens**
        
        Este endpoint permite cerrar la sesión del usuario actual.
        
        **Proceso:**
        1. Limpia las cookies de autenticación
        2. Invalida los tokens JWT del lado del cliente
        3. Registra el evento de logout
        
        **Nota:** Los tokens JWT no se invalidan del lado del servidor (stateless),
        pero se eliminan las cookies del navegador.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Logout exitoso', success_message_model),
            500: 'Error interno del servidor'
        }
    )
    # Removed marshal_with to prevent double serialization when returning a Response
    def post(self):
        """Cerrar sesión y limpiar tokens"""
        try:
            response_data = {'message': 'Logout exitoso'}
            response = jsonify(response_data)
            
            # Limpiar cookies JWT
            unset_jwt_cookies(response)
            
            logger.info("Usuario cerró sesión")
            return response
            
        except Exception as e:
            logger.error(f"Error en logout: {str(e)}")
            auth_ns.abort(500, f'Error interno del servidor: {str(e)}')

@auth_ns.route('/me')
class CurrentUser(Resource):
    @auth_ns.doc(
        'get_current_user',
        description='''
        **Obtener información del usuario autenticado**
        
        Este endpoint retorna la información del usuario actualmente autenticado.
        
        **Uso:**
        - Requiere token JWT válido
        - Útil para verificar el estado de autenticación
        - Retorna datos actualizados del usuario
        
        **Casos de uso:**
        - Verificar si el usuario sigue autenticado
        - Obtener información actualizada del perfil
        - Validar permisos antes de operaciones sensibles
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: 'Información del usuario actual',
            401: 'Token JWT requerido o inválido',
            404: 'Usuario no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def get(self):
        """Obtener información del usuario autenticado"""
        try:
            # Obtener identity (string) y claims del token
            user_id = get_jwt_identity()
            from flask_jwt_extended import get_jwt
            user_claims = get_jwt()
            
            # Buscar usuario en la base de datos para obtener información actualizada
            user = User.query.filter_by(id=int(user_id)).first()
            
            if not user:
                auth_ns.abort(404, 'Usuario no encontrado')
            
            if not user.status:
                auth_ns.abort(401, 'Usuario inactivo')
            
            logger.info(f"Información de usuario solicitada: {user_claims.get('identification')}")
            
            return {
                'message': 'Información del usuario obtenida exitosamente',
                'user': user.to_json()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo usuario actual: {str(e)}")
            auth_ns.abort(500, f'Error interno del servidor: {str(e)}')

@auth_ns.route('/test')
class AuthTest(Resource):
    @auth_ns.doc(
        'test_auth',
        description='''
        **Endpoint de prueba para verificar autenticación**
        
        Este endpoint sirve para probar que la autenticación JWT funciona correctamente.
        
        **Propósito:**
        - Verificar que los tokens JWT se validan correctamente
        - Probar la configuración de autenticación
        - Endpoint de diagnóstico para desarrolladores
        - Compatible con frontend React
        
        **Uso:**
        - Requiere token JWT válido (en cookie o header Authorization)
        - Retorna confirmación de autenticación exitosa
        - Útil para verificar estado de sesión
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Autenticación válida', success_message_model),
            401: 'Token JWT requerido o inválido'
        }
    )
    @auth_ns.marshal_with(success_message_model)
    @jwt_required()
    def get(self):
        """Verificar autenticación JWT"""
        # Obtener identity (string) y claims del token
        user_id = get_jwt_identity()
        from flask_jwt_extended import get_jwt
        user_claims = get_jwt()
        
        logger.info(f"Auth test exitoso para usuario: {user_claims.get('fullname', 'Unknown')}")
        
        return {
            'message': 'Autenticación válida',
            'authenticated': True,
            'user_id': user_id,
            'user': user_claims.get('fullname', 'Usuario'),
            'role': user_claims.get('role', 'Unknown'),
            'identification': user_claims.get('identification'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@auth_ns.route('/protected')
class ProtectedEndpoint(Resource):
    @auth_ns.doc(
        'test_protection',
        description='''
        **Endpoint protegido para pruebas avanzadas**
        
        Este endpoint sirve para probar que la autenticación JWT funciona correctamente.
        
        **Propósito:**
        - Verificar que los tokens JWT se validan correctamente
        - Probar la configuración de autenticación
        - Endpoint de diagnóstico para desarrolladores
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Acceso autorizado', success_message_model),
            401: 'Token JWT requerido o inválido'
        }
    )
    @auth_ns.marshal_with(success_message_model)
    @jwt_required()
    def get(self):
        """Endpoint protegido para pruebas de autenticación"""
        # Obtener identity (string) y claims del token
        user_id = get_jwt_identity()
        from flask_jwt_extended import get_jwt
        user_claims = get_jwt()
        
        return {
            'message': f'Acceso autorizado para {user_claims.get("fullname", "usuario")}',
            'user_id': user_id,
            'user_info': user_claims
        }