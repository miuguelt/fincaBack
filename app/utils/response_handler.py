from flask import jsonify
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class APIResponse:
    """
    Sistema de respuestas estandarizadas para compatibilidad total con React.
    Proporciona estructura consistente y códigos de estado HTTP apropiados.
    """
    
    @staticmethod
    def success(data: Any = None, message: str = "Operación exitosa", 
                status_code: int = 200, meta: Optional[Dict] = None) -> tuple:
        """
        Respuesta de éxito estandarizada.
        
        Args:
            data: Datos a retornar (puede ser dict, list, etc.)
            message: Mensaje descriptivo
            status_code: Código HTTP (200, 201, etc.)
            meta: Metadatos adicionales (paginación, totales, etc.)
        
        Returns:
            Tuple con (response_json, status_code)
        """
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status_code": status_code
        }
        
        if meta:
            response["meta"] = meta
            
        logger.info(f"Success response: {status_code} - {message}")
        # Return plain dict; let Flask / Flask-RESTX handle serialization
        return response, status_code
    
    @staticmethod
    def error(message: str, status_code: int = 400, 
              error_code: Optional[str] = None, 
              details: Optional[Dict] = None) -> tuple:
        """
        Respuesta de error estandarizada.
        
        Args:
            message: Mensaje de error descriptivo
            status_code: Código HTTP de error
            error_code: Código interno de error (opcional)
            details: Detalles adicionales del error
        
        Returns:
            Tuple con (response_json, status_code)
        """
        response = {
            "success": False,
            "message": message,
            "error": {
                "code": error_code or f"HTTP_{status_code}",
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "status_code": status_code
        }
        
        logger.error(f"Error response: {status_code} - {message}")
        # Return plain dict; let Flask / Flask-RESTX handle serialization
        return response, status_code
    
    @staticmethod
    def validation_error(errors: Union[Dict, List], 
                        message: str = "Errores de validación") -> tuple:
        """
        Respuesta específica para errores de validación.
        
        Args:
            errors: Errores de validación (dict o list)
            message: Mensaje principal
        
        Returns:
            Tuple con (response_json, 422)
        """
        return APIResponse.error(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors}
        )
    
    @staticmethod
    def not_found(resource: str = "Recurso") -> tuple:
        """
        Respuesta para recursos no encontrados.
        
        Args:
            resource: Nombre del recurso no encontrado
        
        Returns:
            Tuple con (response_json, 404)
        """
        return APIResponse.error(
            message=f"{resource} no encontrado",
            status_code=404,
            error_code="NOT_FOUND"
        )
    
    @staticmethod
    def unauthorized(message: str = "Acceso no autorizado") -> tuple:
        """
        Respuesta para errores de autenticación.
        
        Args:
            message: Mensaje de error personalizado
        
        Returns:
            Tuple con (response_json, 401)
        """
        return APIResponse.error(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED"
        )
    
    @staticmethod
    def forbidden(message: str = "Acceso prohibido") -> tuple:
        """
        Respuesta para errores de autorización.
        
        Args:
            message: Mensaje de error personalizado
        
        Returns:
            Tuple con (response_json, 403)
        """
        return APIResponse.error(
            message=message,
            status_code=403,
            error_code="FORBIDDEN"
        )
    
    @staticmethod
    def conflict(message: str = "Conflicto de datos", details: Optional[Dict] = None) -> tuple:
        """
        Respuesta para conflictos de integridad.
        
        Args:
            message: Mensaje de error
            details: Detalles del conflicto
        
        Returns:
            Tuple con (response_json, 409)
        """
        return APIResponse.error(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details
        )
    
    @staticmethod
    def paginated_success(data: List, page: int, per_page: int, 
                         total: int, message: str = "Datos obtenidos exitosamente") -> tuple:
        """
        Respuesta de éxito con paginación.
        
        Args:
            data: Lista de datos
            page: Página actual
            per_page: Elementos por página
            total: Total de elementos
            message: Mensaje descriptivo
        
        Returns:
            Tuple con (response_json, 200)
        """
        total_pages = (total + per_page - 1) // per_page
        
        meta = {
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
        return APIResponse.success(
            data=data,
            message=message,
            meta=meta
        )
    
    @staticmethod
    def created(data: Any, message: str = "Recurso creado exitosamente") -> tuple:
        """
        Respuesta para recursos creados.
        
        Args:
            data: Datos del recurso creado
            message: Mensaje de éxito
        
        Returns:
            Tuple con (response_json, 201)
        """
        return APIResponse.success(
            data=data,
            message=message,
            status_code=201
        )
    
    @staticmethod
    def no_content(message: str = "Operación completada") -> tuple:
        """
        Respuesta sin contenido (para DELETE exitoso).
        
        Args:
            message: Mensaje de confirmación
        
        Returns:
            Tuple con (response_json, 200)
        """
        return APIResponse.success(
            data=None,
            message=message,
            status_code=200
        )


class ResponseFormatter:
    """
    Formateador de datos para respuestas consistentes.
    """
    
    @staticmethod
    def format_model(model_instance, exclude_fields: Optional[List[str]] = None) -> Dict:
        """
        Formatea una instancia de modelo SQLAlchemy.
        
        Args:
            model_instance: Instancia del modelo
            exclude_fields: Campos a excluir
        
        Returns:
            Diccionario con los datos formateados
        """
        if hasattr(model_instance, 'to_json'):
            data = model_instance.to_json()
        else:
            # Fallback para modelos sin to_json
            data = {c.name: getattr(model_instance, c.name) 
                   for c in model_instance.__table__.columns}
        
        if exclude_fields:
            for field in exclude_fields:
                data.pop(field, None)
        
        return data
    
    @staticmethod
    def format_model_list(model_list, exclude_fields: Optional[List[str]] = None) -> List[Dict]:
        """
        Formatea una lista de modelos SQLAlchemy.
        
        Args:
            model_list: Lista de instancias de modelo
            exclude_fields: Campos a excluir
        
        Returns:
            Lista de diccionarios formateados
        """
        return [ResponseFormatter.format_model(model, exclude_fields) 
                for model in model_list]
    
    @staticmethod
    def sanitize_for_frontend(data: Any) -> Any:
        """
        Sanitiza datos para el frontend (convierte fechas, etc.).
        
        Args:
            data: Datos a sanitizar
        
        Returns:
            Datos sanitizados
        """
        if isinstance(data, dict):
            return {k: ResponseFormatter.sanitize_for_frontend(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ResponseFormatter.sanitize_for_frontend(item) for item in data]
        elif hasattr(data, 'isoformat'):  # datetime objects
            return data.isoformat() + "Z"
        else:
            return data