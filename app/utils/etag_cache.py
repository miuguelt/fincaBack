from functools import wraps
from flask import request, jsonify, make_response
from datetime import datetime, timedelta
import hashlib
import json
import logging
from typing import Any, Callable, Optional
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ETagCacheManager:
    """
    Sistema de caché con ETags para optimizar endpoints de listar.
    Solo envía datos cuando hay cambios reales en la base de datos.
    """
    
    def __init__(self):
        self._table_timestamps = {}
        self._etag_cache = {}
    
    def _get_table_last_modified(self, table_name: str) -> datetime:
        """
        Obtiene la última fecha de modificación de una tabla.
        """
        try:
            # Primero intentar con columnas de timestamp
            try:
                query = text(f"""
                    SELECT GREATEST(
                        COALESCE(MAX(created_at), '1970-01-01'),
                        COALESCE(MAX(updated_at), '1970-01-01')
                    ) as last_modified
                    FROM {table_name}
                """)
                
                result = db.session.execute(query).fetchone()
                if result and result[0]:
                    return result[0]
            except Exception:
                # Si no hay columnas de timestamp, usar COUNT como indicador de cambios
                pass
            
            # Fallback: usar COUNT como indicador de cambios
            count_query = text(f"SELECT COUNT(*) as count FROM {table_name}")
            count_result = db.session.execute(count_query).fetchone()
            count = count_result[0] if count_result else 0
            
            # Crear un timestamp basado en el count (simulado)
            base_time = datetime(2024, 1, 1)  # Fecha base
            return base_time + timedelta(seconds=count)
                
        except Exception as e:
            logger.warning(f"Error obteniendo timestamp de {table_name}: {e}")
            return datetime.utcnow()
    
    def _generate_etag(self, data: Any, table_name: str) -> str:
        """
        Genera un ETag basado en los datos y el timestamp de la tabla.
        """
        last_modified = self._get_table_last_modified(table_name)
        
        # Crear hash basado en timestamp y estructura de datos
        etag_data = {
            'table': table_name,
            'last_modified': last_modified.isoformat(),
            'data_hash': hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        }
        
        etag_string = json.dumps(etag_data, sort_keys=True)
        return hashlib.md5(etag_string.encode()).hexdigest()
    
    def _check_if_modified(self, table_name: str, client_etag: Optional[str]) -> bool:
        """
        Verifica si los datos han sido modificados desde la última consulta.
        """
        if not client_etag:
            return True
        
        current_timestamp = self._get_table_last_modified(table_name)
        cached_timestamp = self._table_timestamps.get(table_name)
        
        # Si no hay timestamp en caché o ha cambiado, los datos fueron modificados
        if not cached_timestamp or current_timestamp > cached_timestamp:
            self._table_timestamps[table_name] = current_timestamp
            return True
        
        return False

def etag_cache(table_name: str, cache_timeout: int = 300):
    """
    Decorador para implementar caché con ETags en endpoints de listar.
    
    Args:
        table_name: Nombre de la tabla principal del endpoint
        cache_timeout: Tiempo de caché en segundos (default: 5 minutos)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = ETagCacheManager()
            
            # Obtener ETag del cliente
            client_etag = request.headers.get('If-None-Match')
            
            # Verificar si los datos han sido modificados
            if not cache_manager._check_if_modified(table_name, client_etag):
                # Los datos no han cambiado, devolver 304 Not Modified
                logger.info(f"Cache HIT: {table_name} - No modificado, devolviendo 304")
                response = make_response('', 304)
                response.headers['ETag'] = client_etag
                response.headers['Cache-Control'] = f'max-age={cache_timeout}'
                return response
            
            # Los datos han cambiado, ejecutar la función original
            logger.info(f"Cache MISS: {table_name} - Datos modificados, ejecutando consulta")
            
            try:
                # Ejecutar la función original
                result = func(*args, **kwargs)
                
                # Si el resultado es una tupla (data, status_code), extraer los datos
                if isinstance(result, tuple):
                    data, status_code = result
                else:
                    data = result
                    status_code = 200
                
                # Generar nuevo ETag
                new_etag = cache_manager._generate_etag(data, table_name)
                
                # Crear respuesta con ETag
                response = make_response(jsonify(data), status_code)
                response.headers['ETag'] = new_etag
                response.headers['Cache-Control'] = f'max-age={cache_timeout}'
                response.headers['Last-Modified'] = cache_manager._get_table_last_modified(table_name).strftime('%a, %d %b %Y %H:%M:%S GMT')
                
                # Guardar en caché
                cache_manager._etag_cache[new_etag] = {
                    'data': data,
                    'timestamp': datetime.utcnow(),
                    'table': table_name
                }
                
                logger.info(f"Cache SET: {table_name} - Nuevo ETag: {new_etag[:8]}...")
                return response
                
            except Exception as e:
                logger.error(f"Error en endpoint cacheado {table_name}: {e}")
                # En caso de error, ejecutar sin caché
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

def conditional_cache(table_names: list, cache_timeout: int = 300):
    """
    Decorador para endpoints que consultan múltiples tablas.
    
    Args:
        table_names: Lista de nombres de tablas que consulta el endpoint
        cache_timeout: Tiempo de caché en segundos
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = ETagCacheManager()
            
            # Verificar si alguna de las tablas ha sido modificada
            client_etag = request.headers.get('If-None-Match')
            
            tables_modified = any(
                cache_manager._check_if_modified(table, client_etag) 
                for table in table_names
            )
            
            if not tables_modified and client_etag:
                # Ninguna tabla ha sido modificada
                logger.info(f"Cache HIT: {table_names} - No modificado, devolviendo 304")
                response = make_response('', 304)
                response.headers['ETag'] = client_etag
                response.headers['Cache-Control'] = f'max-age={cache_timeout}'
                return response
            
            # Al menos una tabla ha sido modificada
            logger.info(f"Cache MISS: {table_names} - Datos modificados, ejecutando consulta")
            
            try:
                result = func(*args, **kwargs)
                
                if isinstance(result, tuple):
                    data, status_code = result
                else:
                    data = result
                    status_code = 200
                
                # Generar ETag combinado para múltiples tablas
                combined_table_name = '_'.join(sorted(table_names))
                new_etag = cache_manager._generate_etag(data, combined_table_name)
                
                response = make_response(jsonify(data), status_code)
                response.headers['ETag'] = new_etag
                response.headers['Cache-Control'] = f'max-age={cache_timeout}'
                
                # Usar el timestamp más reciente de todas las tablas
                latest_timestamp = max(
                    cache_manager._get_table_last_modified(table) 
                    for table in table_names
                )
                response.headers['Last-Modified'] = latest_timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')
                
                logger.info(f"Cache SET: {table_names} - Nuevo ETag: {new_etag[:8]}...")
                return response
                
            except Exception as e:
                logger.error(f"Error en endpoint cacheado {table_names}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Instancia global del cache manager
cache_manager = ETagCacheManager()