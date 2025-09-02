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
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
        "https://mifinca.isladigital.xyz",
        "https://mifican.isldigital.xya"
    ]

    # Nivel de logging por defecto
    LOG_LEVEL = logging.INFO
    LOG_FILE_ENABLED = False
    
    # URLs base para APIs y frontend
    API_BASE_URL = os.getenv('API_BASE_URL', 'https://localhost:8081/api/v1')
    API_HOST = os.getenv('API_HOST', 'localhost')
    API_PORT = os.getenv('API_PORT', '8081')
    API_PROTOCOL = os.getenv('API_PROTOCOL', 'https')
    
    # URLs para frontend y backend
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://localhost:5175')
    FRONTEND_HOST = os.getenv('FRONTEND_HOST', 'localhost')
    FRONTEND_PORT = os.getenv('FRONTEND_PORT', '5175')
    FRONTEND_PROTOCOL = os.getenv('FRONTEND_PROTOCOL', 'https')
    
    BACKEND_URL = os.getenv('BACKEND_URL', 'https://localhost:8081')
    BACKEND_HOST = os.getenv('BACKEND_HOST', 'localhost')
    BACKEND_PORT = os.getenv('BACKEND_PORT', '8081')
    BACKEND_PROTOCOL = os.getenv('BACKEND_PROTOCOL', 'https')
    
    # URLs adicionales
    API_BASE_URL_NO_VERSION = os.getenv('API_BASE_URL_NO_VERSION', 'https://localhost:8081')
    API_DOCS_URL = os.getenv('API_DOCS_URL', 'https://localhost:8081/docs')
    API_SWAGGER_URL = os.getenv('API_SWAGGER_URL', 'https://localhost:8081/swagger.json')

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
        "https://mifinca.isladigital.xyz",
        "https://mifican.isldigital.xya",
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