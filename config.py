import os
from datetime import timedelta
import secrets
import logging

class Config:
    """Configuración base de la aplicación. Aplica a todos los entornos."""

    # Configuración de Base de Datos
    USER = os.getenv('DB_USER', 'root')
    PASSWORD = os.getenv('DB_PASSWORD', 'password')
    HOST = os.getenv('DB_HOST', 'localhost')
    PORT = os.getenv('DB_PORT', '3306')
    DATABASE = os.getenv('DB_NAME', 'finca_db')
    # Driver configurable por variable de entorno DB_DRIVER: pymysql | mysqldb | mysqlconnector
    DB_DRIVER = os.getenv('DB_DRIVER', 'pymysql').lower()
    if DB_DRIVER not in ('pymysql', 'mysqldb', 'mysqlconnector'):
        DB_DRIVER = 'pymysql'
    # Nota: mysqldb (mysqlclient) requiere compilación en Windows; fallback automático a PyMySQL si no instalado.
    SQLALCHEMY_DATABASE_URI = f'mysql+{DB_DRIVER}://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuraciones de optimización de base de datos
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 25,  # Incrementado para mejor concurrencia
        'max_overflow': 40,  # Más conexiones de overflow
        'pool_timeout': 20,  # Timeout más agresivo
        'pool_recycle': 3600,  # Reciclar conexiones cada hora
        'pool_pre_ping': True,  # Verificar conexiones antes de usar
        'echo': False,  # Cambiar a True para debug de SQL
        'connect_args': {
            'charset': 'utf8mb4',
            'autocommit': False,
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30,
            'sql_mode': 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'
        }
    }
    
    # Configuraciones de cache optimizadas
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 600  # 10 minutos para mejor rendimiento
    CACHE_THRESHOLD = 1000  # Máximo número de entradas en caché
    
    # Configuraciones de rendimiento mejoradas
    PERFORMANCE_MONITORING = True
    SLOW_QUERY_THRESHOLD = 0.5  # Más estricto para detectar consultas lentas
    QUERY_CACHE_ENABLED = True
    QUERY_CACHE_TIMEOUT = 600  # 10 minutos
    QUERY_CACHE_MAX_SIZE = 500  # Máximo número de consultas cacheadas
    
    # Configuraciones de compresión
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml', 'application/json',
        'application/javascript', 'text/javascript', 'application/xml'
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500

    # Configuración base de JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_HTTPONLY = True
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_REFRESH_COOKIE_NAME = 'refresh_token_cookie'
    JWT_COOKIE_SAMESITE = 'None'  # Cambiado de 'None' a 'Lax' para localhost HTTP
    JWT_COOKIE_CSRF_PROTECT = False

    # Configuración de CORS
    CORS_ORIGINS = [
        "https://localhost:5173", 
        "http://localhost:5173",
        "https://localhost:5175", 
        "http://localhost:5175",
        "https://localhost:3000",
        "http://localhost:3000",
        "https://finca.isladigital.xyz",
        "https://mifinca.isladigital.xyz"
    ]

    # Nivel de logging por defecto
    LOG_LEVEL = logging.INFO
    LOG_FILE_ENABLED = False
    
    # URLs base para APIs y frontend
    API_BASE_URL = os.getenv('API_BASE_URL', 'https://finca.isladigital.xyz/api/v1')
    API_HOST = os.getenv('API_HOST', 'finca.isladigital.xyz')
    API_PORT = os.getenv('API_PORT', '443')
    API_PROTOCOL = os.getenv('API_PROTOCOL', 'https')
    
    # URLs para frontend y backend
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://finca.isladigital.xyz')
    FRONTEND_HOST = os.getenv('FRONTEND_HOST', 'finca.isladigital.xyz')
    FRONTEND_PORT = os.getenv('FRONTEND_PORT', '443')
    FRONTEND_PROTOCOL = os.getenv('FRONTEND_PROTOCOL', 'https')
    
    BACKEND_URL = os.getenv('BACKEND_URL', 'https://finca.isladigital.xyz')
    BACKEND_HOST = os.getenv('BACKEND_HOST', 'finca.isladigital.xyz')
    BACKEND_PORT = os.getenv('BACKEND_PORT', '443')
    BACKEND_PROTOCOL = os.getenv('BACKEND_PROTOCOL', 'https')
    
    # URLs adicionales
    API_BASE_URL_NO_VERSION = os.getenv('API_BASE_URL_NO_VERSION', 'https://finca.isladigital.xyz')
    API_DOCS_URL = os.getenv('API_DOCS_URL', 'https://finca.isladigital.xyz/docs')
    API_SWAGGER_URL = os.getenv('API_SWAGGER_URL', 'https://finca.isladigital.xyz/swagger.json')

class DevelopmentConfig(Config):
    """Configuración para desarrollo (localhost)."""
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    
    # JWT - Desarrollo local: SECURE debe ser False para HTTP
    # Para desarrollo local, usamos SameSite=Lax para mejor compatibilidad
    JWT_COOKIE_SECURE = False  # Cambiado a False para desarrollo local HTTP
    JWT_COOKIE_SAMESITE = 'Lax'  # Cambiado de None a Lax para desarrollo
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    
    # JWT_COOKIE_DOMAIN debe ser None para que el navegador use el dominio actual
    JWT_COOKIE_DOMAIN = None
    
    # Configuración adicional para desarrollo
    JWT_COOKIE_PATH = '/'
    
    # CORS - Orígenes de desarrollo
    CORS_ORIGINS = [
        "https://localhost:5173", 
        "http://localhost:5173",
        "https://localhost:5174", 
        "http://localhost:5174",
        "https://localhost:5175", 
        "http://localhost:5175",
        "https://localhost:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
        "https://127.0.0.1:5173",
        "https://127.0.0.1:5174",
        "https://127.0.0.1:5175",
        "https://127.0.0.1:3000"
    ]

class ProductionConfig(Config):
    """Configuración para producción (HTTPS)."""
    DEBUG = False
    LOG_LEVEL = logging.INFO
    
    # JWT - Atributos específicos de producción
    # JWT_COOKIE_SECURE debe ser True para HTTPS
    JWT_COOKIE_SECURE = True
    
    @classmethod
    def validate_production_env(cls):
        """Valida variables de entorno requeridas para producción"""
        if not os.getenv('JWT_SECRET_KEY'):
            raise ValueError("La variable JWT_SECRET_KEY DEBE estar definida en producción.")
        if not os.getenv('JWT_COOKIE_DOMAIN'):
            raise ValueError("La variable JWT_COOKIE_DOMAIN DEBE estar definida en producción.")
    
    # El dominio de la cookie debe ser el dominio principal (con punto inicial)
    # para que sea válido en cualquier subdominio
    JWT_COOKIE_DOMAIN = os.getenv('JWT_COOKIE_DOMAIN')
    
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # CORS - Orígenes de producción
    # Incluye el dominio y el subdominio si tu frontend está en un subdominio
    CORS_ORIGINS = [
        "https://isladigital.xyz", 
        "https://finca.isladigital.xyz",
        "https://mifinca.isladigital.xyz",
        "https://localhost:5173", 
        "http://localhost:5173",
        "https://localhost:3000",
        "http://localhost:3000"
    ]

# Diccionario de configuración final
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}