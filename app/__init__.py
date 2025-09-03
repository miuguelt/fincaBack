from flask import Flask, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from flask_cors import CORS
from flask_restx import Api
from datetime import timezone, datetime
from config import config
import logging
import sys
import time
import jwt as pyjwt
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import text

# Importar middlewares de optimización
from app.utils.middleware import RequestMiddleware, SecurityMiddleware, MetricsMiddleware
from app.utils.cache_manager import cache
from app.utils.db_optimization import init_db_optimizations

# ====================================================================
# 1. Inicialización de extensiones (sin enlazarlas a la app aún)
# ====================================================================
db = SQLAlchemy()
jwt = JWTManager()

# ====================================================================
# 2. Funciones de ayuda y configuración modular
# ====================================================================
def configure_logging(app):
    """Configura el sistema de logging optimizado de la aplicación."""
    log_level = app.config.get('LOG_LEVEL', logging.INFO)
    
    # Formato mejorado de logging
    log_format = (
        '%(asctime)s - [%(levelname)s] - %(name)s - '
        '%(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Configurar handlers
    handlers = []
    
    # Handler para consola con colores
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # Handler para archivo si está habilitado
    if app.config.get('LOG_FILE_ENABLED', False):
        log_file = app.config.get('LOG_FILE', 'app.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Configurar logging root
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
        force=True  # Sobrescribir configuración existente
    )
    
    # Configurar loggers específicos
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Logger para la aplicación
    app_logger = logging.getLogger('app')
    app_logger.setLevel(log_level)
    
    app_logger.info("Sistema de logging configurado exitosamente")

def configure_jwt_handlers():
    """Configura los handlers para errores de JWT. Se llama después de jwt.init_app()."""
    logger = logging.getLogger(__name__)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        exp_timestamp = jwt_payload['exp']
        exp_utc = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        seconds_ago = int((now_utc - exp_utc).total_seconds())
        logger.warning(f"Expired token: expired {seconds_ago} seconds ago. Payload: {jwt_payload}")
        return jsonify({
            'msg': 'Token has expired',
            'expired_at_utc': exp_utc.isoformat(),
            'current_time_utc': now_utc.isoformat(),
            'seconds_expired': seconds_ago
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.error(f"Invalid token: {error}")
        return jsonify({
            'msg': f'Invalid token: {error}',
            'error_type': type(error).__name__
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        logger.warning(f"Missing token: {error}")
        return jsonify({
            'msg': 'Missing token in request',
            'error': str(error)
        }), 401

    @jwt.additional_claims_loader
    def add_claims_to_jwt(identity):
        """Agrega claims adicionales para debugging"""
        return {
            'server_time_utc': datetime.now(timezone.utc).isoformat(),
            # CAMBIO CRUCIAL: Usamos current_app en lugar de request.app
            'server_env': current_app.config.get('CONFIG_NAME') 
        }

# ====================================================================
# 3. La función principal de creación de la aplicación
# ====================================================================
def create_app(config_name='production'):
    app = Flask(__name__)
    
    # Añade ProxyFix para entornos con proxies como Vercel o Nginx
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    
    app_config = config.get(config_name, 'default')
    app.config.from_object(app_config)
    app.config['CONFIG_NAME'] = config_name

    # Configura el logging (antes de cualquier otra cosa)
    configure_logging(app)
    logger = logging.getLogger(__name__)

    logger.info("Initializing Flask app...")
    logger.debug(f"Using configuration: {config_name}")

    # Inicializa y enlaza las extensiones con la app
    db.init_app(app)
    jwt.init_app(app)
    
    # Inicializar optimizaciones de base de datos
    init_db_optimizations(app)
    logger.info("Database optimizations initialized")

    # Configura CORS con los orígenes definidos en la clase de configuración
    CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
        allow_headers=[
            "Content-Type", 
            "Authorization", 
            "X-Requested-With",
            "Accept",
            "Origin",
            "Cache-Control",
            "X-File-Name",
            "X-CSRF-Token",
            # Cabeceras de uso común en frontends
            "X-App-Version",
            "X-Client-Timezone",
            "X-Client-Locale",
            "ngrok-skip-browser-warning"
        ],
        expose_headers=[
            "Content-Range",
            "X-Content-Range",
            "X-Total-Count",
            "Authorization"
        ],
        supports_credentials=True,
        max_age=86400  # Cache preflight requests for 24 horas
    )

    # Log detallado de CORS para depuración
    @app.before_request
    def _debug_log_cors_preflight():
        if request.method == 'OPTIONS':
            logger.debug(
                "CORS preflight -> path: %s, origin: %s, req-method: %s, req-headers: %s",
                request.path,
                request.headers.get('Origin'),
                request.headers.get('Access-Control-Request-Method'),
                request.headers.get('Access-Control-Request-Headers'),
            )

    @app.after_request
    def _debug_log_cors_response(response):
        if request.method == 'OPTIONS' or request.path in {"/health", "/api/v1/auth/login", "/api/v1/auth/me"}:
            logger.debug(
                "CORS resp -> path: %s, A-C-Allow-Origin: %s, A-C-Allow-Credentials: %s, Vary: %s",
                request.path,
                response.headers.get('Access-Control-Allow-Origin'),
                response.headers.get('Access-Control-Allow-Credentials'),
                response.headers.get('Vary'),
            )
        return response

    # Log de configuración CORS/JWT para facilitar el diagnóstico en arranque
    try:
        allowed_origins = app.config.get('CORS_ORIGINS', [])
        logger.info(f"CORS habilitado. Orígenes permitidos: {allowed_origins}")
        logger.info(
            "CORS detalles -> supports_credentials: %s, methods: %s, allow_headers: %s, expose_headers: %s, max_age: %s",
            True,
            ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
            [
                "Content-Type", "Authorization", "X-Requested-With", "Accept",
                "Origin", "Cache-Control", "X-File-Name", "X-CSRF-Token",
                "X-App-Version", "X-Client-Timezone", "X-Client-Locale",
                "ngrok-skip-browser-warning"
            ],
            ["Content-Range", "X-Content-Range", "X-Total-Count", "Authorization"],
            86400,
        )
        logger.info(
            "JWT cookies -> domain: %s, secure: %s, samesite: %s, token_location: %s",
            app.config.get('JWT_COOKIE_DOMAIN'),
            app.config.get('JWT_COOKIE_SECURE'),
            app.config.get('JWT_COOKIE_SAMESITE'),
            app.config.get('JWT_TOKEN_LOCATION'),
        )
    except Exception as e:
        logger.warning(f"No se pudo registrar configuración CORS/JWT en logs: {e}")

    # Configura los handlers de JWT
    configure_jwt_handlers()
    
    # Inicializar middlewares de optimización
    request_middleware = RequestMiddleware(app)
    security_middleware = SecurityMiddleware(app)
    metrics_middleware = MetricsMiddleware(app)
    
    logger.info("Middlewares de optimización inicializados")

    # Protección global con JWT para endpoints (excepto lista blanca)
    @app.before_request
    def enforce_jwt_protection():
        # Permitir preflight CORS
        if request.method == 'OPTIONS':
            return
        path = request.path or ''
        public_paths = {
            # Autenticación
            '/login',
            '/logout',
            '/refresh',
            
            # Documentación
            '/api-documentation',
            '/docs',
            '/docs/',
            '/docs/interactive',
            '/docs/tester',
            '/api/v1/docs/',
            '/api/v1/docs',
            '/swaggerui',
            '/swagger.json',
            '/api/v1/swagger.json',
            
            # Recursos estáticos de SwaggerUI
            '/swaggerui/droid-sans.css',
            '/swaggerui/swagger-ui.css',
            '/swaggerui/swagger-ui-bundle.js',
            '/swaggerui/swagger-ui-standalone-preset.js',
            '/swaggerui/favicon-32x32.png',
            '/swaggerui/favicon-16x16.png',
            
            # Métricas y monitoreo
            '/metrics',
            '/health',
            '/api/v1/health',
            '/api/v1/analytics/dashboard',
            '/api/v1/analytics/alerts',
            
            # Autenticación (endpoints públicos)
            '/api/v1/auth/login',
            '/api/v1/login',
            
            # Debug (solo en desarrollo)
            '/debug-jwt-config',
            '/debug-jwt-config1',
            '/debug-config',
            '/debug-cookies',
            '/debug-time',
            '/debug-token-detailed',
            '/debug-complete',
            
            # Estáticos
            '/',
            '/favicon.ico'
        }
        if path in public_paths or path.startswith('/static/'):
            return
        try:
            verify_jwt_in_request()
            # Autorización por rol: solo Administrador puede hacer PUT/DELETE
            if request.method in ('PUT', 'DELETE'):
                user_id = get_jwt_identity()
                from flask_jwt_extended import get_jwt
                user_claims = get_jwt() if user_id else {}
                role = user_claims.get('role')
                if role != 'Administrador':
                    return jsonify({'msg': 'Forbidden: Admin role required'}), 403
        except Exception as e:
            # Responder consistentemente cuando falte o sea inválido el token
            return jsonify({'msg': 'Missing or invalid token', 'error': str(e)}), 401

    # Configurar Flask-RESTX API con documentación Swagger
    from flask_restx import Api
    from flask import Blueprint
    
    # Crear el blueprint para la API
    api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
    
    # Configurar Flask-RESTX
    api = Api(
        api_bp,
        version='1.0',
        title='Finca Villa Luz API',
        description='Sistema de gestión ganadera con documentación completa',
        doc='/docs/',
        contact='Finca Villa Luz',
        contact_email='info@fincavillaluz.com',
        license='MIT',
        license_url='https://opensource.org/licenses/MIT',
        authorizations={
            'Bearer': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'JWT token. Formato: Bearer <token>'
            },
            'Cookie': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'access_token_cookie',
                'description': 'JWT token en cookie (autenticación automática)'
            }
        },
        security=['Bearer', 'Cookie']
    )
    
    from app.namespaces.auth_namespace import auth_ns
    from app.namespaces.users_namespace import users_ns
    from app.namespaces.animals_namespace import animals_ns
    from app.namespaces.analytics_namespace import analytics_ns
    from app.namespaces.breeds_species_namespace import breeds_species_ns
    from app.namespaces.medical_namespace import medical_ns
    from app.namespaces.management_namespace import management_ns
    from app.namespaces.relations_namespace import relations_ns
    
    # Agregar namespaces a la API
    api.add_namespace(auth_ns)
    api.add_namespace(users_ns)
    api.add_namespace(animals_ns)
    api.add_namespace(analytics_ns)
    api.add_namespace(breeds_species_ns)
    api.add_namespace(medical_ns)
    api.add_namespace(management_ns)
    api.add_namespace(relations_ns)
    
    # Registrar el blueprint de la API
    
    # Rutas de compatibilidad para clientes que llaman endpoints antiguos o con rutas diferentes
    @api_bp.route('/login', methods=['POST', 'OPTIONS'])
    def login_alias_v1():
        # Alias para mantener compatibilidad con frontends que llaman /api/v1/login
        if request.method == 'OPTIONS':
            # Manejar preflight CORS sin redirección
            return '', 200
        from flask import redirect
        # Redirigimos conservando el método y el cuerpo (307)
        return redirect('/api/v1/auth/login', code=307)

    @api_bp.route('/health', methods=['GET', 'OPTIONS'])
    def health_alias_v1():
        # Alias para /api/v1/health -> reutiliza el endpoint global /health
        if request.method == 'OPTIONS':
            # Manejar preflight CORS sin redirección
            return '', 200
        from flask import redirect
        return redirect('/health', code=307)

    app.register_blueprint(api_bp)
    
    # Ruta global para documentación
    @app.route('/docs')
    @app.route('/docs/')
    def docs_redirect():
        """Redirigir a la documentación de la API"""
        from flask import redirect
        return redirect('/api/v1/docs/', code=302)
    
    @app.route('/swagger.json')
    def swagger_redirect():
        """Redirigir al JSON de Swagger"""
        from flask import redirect
        return redirect('/api/v1/swagger.json', code=302)
    
    # ====================================================================
    # DOCUMENTACIÓN: Flask-RESTX genera automáticamente la documentación
    # Swagger en /swagger.json y la interfaz interactiva en /docs/
    # No se necesitan blueprints adicionales para documentación
    # ====================================================================
    
    # ====================================================================
    # NOTA: Se eliminaron todos los blueprints de routes antiguos
    # Ahora se usan exclusivamente los namespaces de Flask-RESTX
    # Esto proporciona mejor documentación, validación y organización
    # ====================================================================
    
    # Middleware y endpoint de debugging
    @app.before_request
    def log_request_info():
        if app.config.get('DEBUG', False):
            if any(path in request.path for path in ['/login', '/refresh', '/protected', '/debug']):
                logger.debug(f"REQUEST: {request.method} {request.path}")
                logger.debug(f"Headers: {dict(request.headers)}")
                if request.cookies:
                    logger.debug(f"Cookies present: {list(request.cookies.keys())}")
    
    @app.route('/debug-complete', methods=['GET'])
    def debug_complete():
        access_token = request.cookies.get('access_token_cookie')
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'config': {
                'JWT_SECRET_KEY_length': len(app.config.get('JWT_SECRET_KEY', '')),
                'JWT_ACCESS_TOKEN_EXPIRES': str(app.config.get('JWT_ACCESS_TOKEN_EXPIRES')),
                'JWT_COOKIE_DOMAIN': app.config.get('JWT_COOKIE_DOMAIN'),
                'JWT_COOKIE_SECURE': app.config.get('JWT_COOKIE_SECURE'),
                'JWT_COOKIE_CSRF_PROTECT': app.config.get('JWT_COOKIE_CSRF_PROTECT'),
            },
            'request': {
                'cookies': list(request.cookies.keys()),
                'headers': dict(request.headers),
                'origin': request.headers.get('Origin'),
                'host': request.headers.get('Host')
            }
        }
        if access_token:
            try:
                unverified = pyjwt.decode(access_token, options={"verify_signature": False})
                result['token_analysis'] = {
                    'payload': unverified,
                    'is_expired': datetime.now(timezone.utc) > datetime.fromtimestamp(unverified.get('exp', 0), tz=timezone.utc),
                    'expires_at': datetime.fromtimestamp(unverified.get('exp', 0), tz=timezone.utc).isoformat()
                }
                try:
                    pyjwt.decode(access_token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
                    result['token_analysis']['signature_valid'] = True
                except pyjwt.InvalidSignatureError:
                    result['token_analysis']['signature_valid'] = False
                    result['token_analysis']['signature_error'] = 'Invalid signature'
                except Exception as e:
                    result['token_analysis']['signature_valid'] = False
                    result['token_analysis']['signature_error'] = str(e)
            except Exception as e:
                result['token_analysis'] = {'error': str(e)}
        
        return jsonify(result)
    
    # Endpoint de health check
    @app.route('/health', methods=['GET'])
    def health_check():
        """Endpoint de verificación de salud del sistema."""
        try:
            # Verificar conexión a base de datos
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        # Obtener estadísticas del caché
        cache_stats = cache.get_stats()
        
        health_data = {
            'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': '1.0.0',
            'services': {
                'database': db_status,
                'cache': {
                    'status': 'healthy',
                    'entries': cache_stats['current_entries'],
                    'hit_rate': cache_stats['hit_rate_percent']
                }
            },
            'uptime_seconds': time.time() - app.config.get('START_TIME', time.time())
        }
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        return jsonify(health_data), status_code

    # Guardar tiempo de inicio
    app.config['START_TIME'] = time.time()
    
    logger.info("Flask app initialization complete.")
    return app