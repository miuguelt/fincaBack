from functools import wraps
from flask import request, current_app
import hashlib
import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Sistema de caché en memoria para optimizar consultas frecuentes.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Genera una clave única para el caché.
        """
        key_data = {
            'prefix': prefix,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del caché.
        """
        if key in self._cache:
            cache_entry = self._cache[key]
            
            # Verificar expiración
            if cache_entry['expires_at'] > datetime.utcnow():
                self._cache_stats['hits'] += 1
                logger.debug(f"Cache HIT: {key}")
                return cache_entry['data']
            else:
                # Eliminar entrada expirada
                del self._cache[key]
                logger.debug(f"Cache EXPIRED: {key}")
        
        self._cache_stats['misses'] += 1
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """
        Almacena un valor en el caché.
        
        Args:
            key: Clave del caché
            value: Valor a almacenar
            ttl_seconds: Tiempo de vida en segundos (default: 5 minutos)
        """
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        self._cache[key] = {
            'data': value,
            'created_at': datetime.utcnow(),
            'expires_at': expires_at
        }
        
        self._cache_stats['sets'] += 1
        logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
    
    def delete(self, key: str) -> bool:
        """
        Elimina una entrada del caché.
        """
        if key in self._cache:
            del self._cache[key]
            self._cache_stats['deletes'] += 1
            logger.debug(f"Cache DELETE: {key}")
            return True
        return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Elimina todas las entradas que coincidan con un patrón.
        """
        keys_to_delete = [key for key in self._cache.keys() if pattern in key]
        
        for key in keys_to_delete:
            del self._cache[key]
        
        deleted_count = len(keys_to_delete)
        self._cache_stats['deletes'] += deleted_count
        logger.debug(f"Cache CLEAR PATTERN: {pattern} ({deleted_count} entries)")
        return deleted_count
    
    def clear_all(self) -> int:
        """
        Limpia todo el caché.
        """
        count = len(self._cache)
        self._cache.clear()
        self._cache_stats['deletes'] += count
        logger.info(f"Cache CLEAR ALL: {count} entries")
        return count
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas del caché.
        """
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self._cache_stats,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'current_entries': len(self._cache)
        }
    
    def cleanup_expired(self) -> int:
        """
        Limpia entradas expiradas del caché.
        """
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry['expires_at'] <= now
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cache CLEANUP: {len(expired_keys)} expired entries")
        
        return len(expired_keys)


# Instancia global del caché
cache = CacheManager()


def cached(ttl_seconds: int = 300, key_prefix: str = None):
    """
    Decorator para cachear resultados de funciones.
    
    Args:
        ttl_seconds: Tiempo de vida del caché en segundos
        key_prefix: Prefijo personalizado para la clave
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generar clave de caché
            prefix = key_prefix or f"{f.__module__}.{f.__name__}"
            cache_key = cache._generate_key(prefix, *args, **kwargs)
            
            # Intentar obtener del caché
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = f(*args, **kwargs)
            
            # Solo cachear si el resultado no es una tupla con Response object
            # (evita cachear respuestas de Flask que no son serializables)
            should_cache = True
            
            # Verificar si es una tupla con Response object
            if isinstance(result, tuple) and len(result) == 2:
                response_obj, status_code = result
                if hasattr(response_obj, '__class__'):
                    class_name = str(response_obj.__class__)
                    if 'Response' in class_name or 'flask' in class_name.lower():
                        should_cache = False
            
            # Verificar si contiene objetos no serializables
            try:
                import json
                json.dumps(result, default=str)  # Test serialization
            except (TypeError, ValueError):
                should_cache = False
                logger.debug(f"Function not cached (not serializable): {f.__name__}")
            
            if should_cache:
                cache.set(cache_key, result, ttl_seconds)
                logger.debug(f"Function cached: {f.__name__}")
            else:
                logger.debug(f"Function not cached (Response/non-serializable object): {f.__name__}")
            
            return result
        
        return decorated_function
    return decorator


def cache_query_result(query_name: str, ttl_seconds: int = 300):
    """
    Decorator específico para cachear resultados de consultas a BD.
    
    Args:
        query_name: Nombre descriptivo de la consulta
        ttl_seconds: Tiempo de vida del caché
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Incluir parámetros de request en la clave si existen
            request_params = {}
            if hasattr(request, 'args'):
                request_params = dict(request.args)
            
            cache_key = cache._generate_key(
                f"query_{query_name}",
                *args,
                **kwargs,
                **request_params
            )
            
            # Intentar obtener del caché
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Query cache hit: {query_name}")
                return cached_result
            
            # Ejecutar consulta y cachear
            start_time = time.time()
            result = f(*args, **kwargs)
            query_time = round((time.time() - start_time) * 1000, 2)
            
            # Solo cachear si el resultado no es una tupla con Response object
            # (evita cachear respuestas de Flask que no son serializables)
            should_cache = True
            
            # Verificar si es una tupla con Response object
            if isinstance(result, tuple) and len(result) == 2:
                response_obj, status_code = result
                if hasattr(response_obj, '__class__'):
                    class_name = str(response_obj.__class__)
                    if 'Response' in class_name or 'flask' in class_name.lower():
                        should_cache = False
            
            # Verificar si contiene objetos no serializables
            try:
                import json
                json.dumps(result, default=str)  # Test serialization
            except (TypeError, ValueError):
                should_cache = False
                logger.debug(f"Query not cached (not serializable): {query_name} (Time: {query_time}ms)")
            
            if should_cache:
                cache.set(cache_key, result, ttl_seconds)
                logger.debug(f"Query cached: {query_name} (Time: {query_time}ms, TTL: {ttl_seconds}s)")
            else:
                logger.debug(f"Query not cached (Response/non-serializable object): {query_name} (Time: {query_time}ms)")
            
            return result
        
        return decorated_function
    return decorator


def invalidate_cache_on_change(cache_patterns: List[str]):
    """
    Decorator que invalida patrones de caché cuando se modifica data.
    
    Args:
        cache_patterns: Lista de patrones de caché a invalidar
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ejecutar función
            result = f(*args, **kwargs)
            
            # Invalidar caché relacionado
            total_invalidated = 0
            for pattern in cache_patterns:
                invalidated = cache.clear_pattern(pattern)
                total_invalidated += invalidated
            
            if total_invalidated > 0:
                logger.debug(f"Cache invalidated: {total_invalidated} entries for patterns {cache_patterns}")
            
            return result
        
        return decorated_function
    return decorator


class QueryOptimizer:
    """
    Utilidades para optimizar consultas a la base de datos.
    """
    
    @staticmethod
    def optimize_pagination(query, page: int, per_page: int, max_per_page: int = 100):
        """
        Optimiza consultas paginadas.
        
        Args:
            query: Query de SQLAlchemy
            page: Página solicitada
            per_page: Elementos por página
            max_per_page: Máximo elementos por página
        
        Returns:
            Tuple con (items, total, page, per_page)
        """
        # Validar parámetros
        page = max(1, page)
        per_page = min(max(1, per_page), max_per_page)
        
        # Calcular offset
        offset = (page - 1) * per_page
        
        # Obtener total (con caché)
        total = query.count()
        
        # Obtener items paginados
        items = query.offset(offset).limit(per_page).all()
        
        return items, total, page, per_page
    
    @staticmethod
    def apply_filters(query, filters: Dict[str, Any], model_class):
        """
        Aplica filtros de manera optimizada a una consulta.
        
        Args:
            query: Query de SQLAlchemy
            filters: Diccionario de filtros
            model_class: Clase del modelo SQLAlchemy
        
        Returns:
            Query filtrada
        """
        for field, value in filters.items():
            if value is not None and hasattr(model_class, field):
                column = getattr(model_class, field)
                
                # Filtros especiales
                if field.endswith('_like') and isinstance(value, str):
                    # Búsqueda parcial
                    actual_field = field[:-5]  # Remover '_like'
                    if hasattr(model_class, actual_field):
                        actual_column = getattr(model_class, actual_field)
                        query = query.filter(actual_column.ilike(f'%{value}%'))
                elif field.startswith('min_') and isinstance(value, (int, float)):
                    # Valor mínimo
                    actual_field = field[4:]  # Remover 'min_'
                    if hasattr(model_class, actual_field):
                        actual_column = getattr(model_class, actual_field)
                        query = query.filter(actual_column >= value)
                elif field.startswith('max_') and isinstance(value, (int, float)):
                    # Valor máximo
                    actual_field = field[4:]  # Remover 'max_'
                    if hasattr(model_class, actual_field):
                        actual_column = getattr(model_class, actual_field)
                        query = query.filter(actual_column <= value)
                else:
                    # Filtro exacto
                    query = query.filter(column == value)
        
        return query
    
    @staticmethod
    def get_request_filters() -> Dict[str, Any]:
        """
        Extrae filtros de los parámetros de la petición.
        
        Returns:
            Diccionario con filtros válidos
        """
        filters = {}
        
        for key, value in request.args.items():
            if value and value.strip():
                # Convertir tipos básicos
                if value.lower() in ['true', 'false']:
                    filters[key] = value.lower() == 'true'
                elif value.isdigit():
                    filters[key] = int(value)
                elif value.replace('.', '').isdigit():
                    filters[key] = float(value)
                else:
                    filters[key] = value.strip()
        
        return filters