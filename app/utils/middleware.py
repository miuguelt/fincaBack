from flask import request, g, current_app
from flask_jwt_extended import get_jwt_identity
import logging
import time
import traceback
from functools import wraps
from app.utils.response_handler import APIResponse
from app.utils.cache_manager import cache
import uuid

logger = logging.getLogger(__name__)

class RequestMiddleware:
    """
    Middleware centralizado para manejo de requests y respuestas.
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el middleware con la aplicación Flask."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_appcontext(self.teardown_request)
        
        # Registrar manejadores de errores
        app.errorhandler(400)(self.handle_bad_request)
        app.errorhandler(401)(self.handle_unauthorized)
        app.errorhandler(403)(self.handle_forbidden)
        app.errorhandler(404)(self.handle_not_found)
        app.errorhandler(405)(self.handle_method_not_allowed)
        app.errorhandler(422)(self.handle_unprocessable_entity)
        app.errorhandler(500)(self.handle_internal_error)
        app.errorhandler(Exception)(self.handle_generic_exception)
    
    def before_request(self):
        """Ejecuta antes de cada request."""
        # Generar ID único para el request
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
        
        # Información del usuario
        g.user_info = "Anonymous"
        try:
            jwt_identity = get_jwt_identity()
            if jwt_identity:
                g.user_info = f"User {jwt_identity.get('id', 'Unknown')}"
                g.user_role = jwt_identity.get('role', 'Unknown')
        except:
            g.user_role = None
        
        # Log del inicio del request
        logger.info(
            f"[{g.request_id}] REQUEST START: {request.method} {request.path} | "
            f"User: {g.user_info} | IP: {request.remote_addr} | "
            f"User-Agent: {request.headers.get('User-Agent', 'Unknown')[:50]}"
        )
        
        # Limpiar caché expirado periódicamente
        if hasattr(g, 'request_id') and int(g.request_id[:2], 16) % 100 == 0:
            cache.cleanup_expired()
    
    def after_request(self, response):
        """Ejecuta después de cada request."""
        if hasattr(g, 'start_time'):
            response_time = round((time.time() - g.start_time) * 1000, 2)
            
            # Agregar headers de respuesta
            response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
            response.headers['X-Response-Time'] = f"{response_time}ms"
            response.headers['X-API-Version'] = '1.0'
            
            # Log del final del request
            logger.info(
                f"[{getattr(g, 'request_id', 'unknown')}] REQUEST END: "
                f"{request.method} {request.path} | Status: {response.status_code} | "
                f"Time: {response_time}ms | User: {getattr(g, 'user_info', 'Unknown')}"
            )
            
            # Alertar sobre requests lentos
            if response_time > 1000:
                logger.warning(
                    f"[{getattr(g, 'request_id', 'unknown')}] SLOW REQUEST: "
                    f"{request.method} {request.path} | Time: {response_time}ms"
                )
        
        return response
    
    def teardown_request(self, exception):
        """Ejecuta al final del contexto del request."""
        if exception:
            logger.error(
                f"[{getattr(g, 'request_id', 'unknown')}] REQUEST EXCEPTION: {str(exception)}"
            )
    
    # Manejadores de errores centralizados
    def handle_bad_request(self, error):
        """Maneja errores 400."""
        logger.warning(f"[{getattr(g, 'request_id', 'unknown')}] Bad Request: {str(error)}")
        return APIResponse.error(
            message="Solicitud incorrecta",
            status_code=400,
            error_code="BAD_REQUEST",
            details={'description': str(error)}
        )
    
    def handle_unauthorized(self, error):
        """Maneja errores 401."""
        logger.warning(f"[{getattr(g, 'request_id', 'unknown')}] Unauthorized: {str(error)}")
        return APIResponse.unauthorized("Acceso no autorizado")
    
    def handle_forbidden(self, error):
        """Maneja errores 403."""
        logger.warning(f"[{getattr(g, 'request_id', 'unknown')}] Forbidden: {str(error)}")
        return APIResponse.forbidden("Acceso prohibido")
    
    def handle_not_found(self, error):
        """Maneja errores 404."""
        logger.warning(f"[{getattr(g, 'request_id', 'unknown')}] Not Found: {request.path}")
        return APIResponse.not_found("Endpoint")
    
    def handle_method_not_allowed(self, error):
        """Maneja errores 405."""
        logger.warning(
            f"[{getattr(g, 'request_id', 'unknown')}] Method Not Allowed: "
            f"{request.method} {request.path}"
        )
        return APIResponse.error(
            message=f"Método {request.method} no permitido para este endpoint",
            status_code=405,
            error_code="METHOD_NOT_ALLOWED"
        )
    
    def handle_unprocessable_entity(self, error):
        """Maneja errores 422."""
        logger.warning(f"[{getattr(g, 'request_id', 'unknown')}] Validation Error: {str(error)}")
        return APIResponse.validation_error(
            errors={'validation': str(error)},
            message="Error de validación"
        )
    
    def handle_internal_error(self, error):
        """Maneja errores 500."""
        logger.error(
            f"[{getattr(g, 'request_id', 'unknown')}] Internal Server Error: {str(error)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        # En producción, no mostrar detalles del error
        if current_app.config.get('DEBUG', False):
            details = {'error': str(error), 'traceback': traceback.format_exc()}
        else:
            details = {'request_id': getattr(g, 'request_id', 'unknown')}
        
        return APIResponse.error(
            message="Error interno del servidor",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            details=details
        )
    
    def handle_generic_exception(self, error):
        """Maneja excepciones no capturadas."""
        logger.error(
            f"[{getattr(g, 'request_id', 'unknown')}] Unhandled Exception: {str(error)}\n"
            f"Type: {type(error).__name__}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        return self.handle_internal_error(error)


class SecurityMiddleware:
    """
    Middleware de seguridad adicional.
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el middleware de seguridad."""
        app.before_request(self.security_checks)
        app.after_request(self.add_security_headers)
    
    def security_checks(self):
        """Realiza verificaciones de seguridad."""
        # Rate limiting básico (se puede mejorar con Redis)
        client_ip = request.remote_addr
        
        # Validar Content-Type para requests con body
        if request.method in ['POST', 'PUT', 'PATCH']:
            if request.content_length and request.content_length > 0:
                if not request.is_json:
                    logger.warning(
                        f"[{getattr(g, 'request_id', 'unknown')}] Invalid Content-Type: "
                        f"{request.content_type} from {client_ip}"
                    )
        
        # Validar tamaño del payload
        max_content_length = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB
        if request.content_length and max_content_length and request.content_length > max_content_length:
            logger.warning(
                f"[{getattr(g, 'request_id', 'unknown')}] Payload too large: "
                f"{request.content_length} bytes from {client_ip}"
            )
            return APIResponse.error(
                message="Payload demasiado grande",
                status_code=413,
                error_code="PAYLOAD_TOO_LARGE"
            )
    
    def add_security_headers(self, response):
        """Añade headers de seguridad."""
        # Headers de seguridad básicos
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Importante: No establecer manualmente CORS aquí.
        # Flask-CORS ya gestiona los encabezados adecuados (incluyendo
        # Access-Control-Allow-Origin y Access-Control-Allow-Credentials)
        # según la configuración en app.__init__.py.
        
        return response


class MetricsMiddleware:
    """
    Middleware para recolección de métricas.
    """
    
    def __init__(self, app=None):
        self.metrics = {
            'requests_total': 0,
            'requests_by_method': {},
            'requests_by_status': {},
            'response_times': [],
            'errors_total': 0
        }
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa el middleware de métricas."""
        app.after_request(self.collect_metrics)
        
        # Endpoint para obtener métricas
        @app.route('/metrics')
        def get_metrics():
            cache_stats = cache.get_stats()
            
            avg_response_time = (
                sum(self.metrics['response_times']) / len(self.metrics['response_times'])
                if self.metrics['response_times'] else 0
            )
            
            return APIResponse.success({
                'requests': self.metrics,
                'cache': cache_stats,
                'average_response_time_ms': round(avg_response_time, 2)
            }, message="Métricas del sistema")
    
    def collect_metrics(self, response):
        """Recolecta métricas del request."""
        if hasattr(g, 'start_time'):
            response_time = (time.time() - g.start_time) * 1000
            
            # Actualizar métricas
            self.metrics['requests_total'] += 1
            
            method = request.method
            self.metrics['requests_by_method'][method] = \
                self.metrics['requests_by_method'].get(method, 0) + 1
            
            status = str(response.status_code)
            self.metrics['requests_by_status'][status] = \
                self.metrics['requests_by_status'].get(status, 0) + 1
            
            # Mantener solo los últimos 1000 tiempos de respuesta
            self.metrics['response_times'].append(response_time)
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = self.metrics['response_times'][-1000:]
            
            if response.status_code >= 400:
                self.metrics['errors_total'] += 1
        
        return response