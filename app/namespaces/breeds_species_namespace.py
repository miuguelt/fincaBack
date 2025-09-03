from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.breeds import Breeds
from app.models.species import Species
from app import db
from sqlalchemy.exc import IntegrityError
import logging

# Importar utilidades de optimización
from app.utils.response_handler import APIResponse, ResponseFormatter
from app.utils.validators import (
    RequestValidator, PerformanceLogger, SecurityValidator
)
from app.utils.cache_manager import cache_query_result, invalidate_cache_on_change
from app.utils.etag_cache import etag_cache, conditional_cache

# Crear el namespace
breeds_species_ns = Namespace(
    'breeds-species',
    description='🧬 Gestión de Razas y Especies - Catálogo Genético',
    path='/breeds-species'
)

logger = logging.getLogger(__name__)

# Modelos para documentación
species_input_model = breeds_species_ns.model('SpeciesInput', {
    'name': fields.String(required=True, description='Nombre de la especie', example='Bovino')
})

species_response_model = breeds_species_ns.model('SpeciesResponse', {
    'id': fields.Integer(description='ID único de la especie'),
    'name': fields.String(description='Nombre de la especie')
})

breed_input_model = breeds_species_ns.model('BreedInput', {
    'name': fields.String(required=True, description='Nombre de la raza', example='Holstein'),
    'species_id': fields.Integer(required=True, description='ID de la especie', example=1)
})

breed_update_model = breeds_species_ns.model('BreedUpdate', {
    'name': fields.String(description='Nombre de la raza'),
    'species_id': fields.Integer(description='ID de la especie')
})

breed_response_model = breeds_species_ns.model('BreedResponse', {
    'id': fields.Integer(description='ID único de la raza'),
    'name': fields.String(description='Nombre de la raza'),
    'species_id': fields.Integer(description='ID de la especie'),
    'species': fields.Nested(species_response_model, description='Información de la especie')
})

success_message_model = breeds_species_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito')
})

error_message_model = breeds_species_ns.model('ErrorMessage', {
    'message': fields.String(description='Mensaje de error'),
    'error': fields.String(description='Detalles del error')
})

# ============================================================================
# ENDPOINTS DE ESPECIES
# ============================================================================

@breeds_species_ns.route('/species')
class SpeciesList(Resource):
    @breeds_species_ns.doc(
        'get_species_list',
        description='''
        **Obtener lista de especies**
        
        Retorna todas las especies disponibles en el sistema.
        Útil para poblar dropdowns y formularios de selección.
        
        **Parámetros opcionales:**
        - `name`: Filtrar por nombre de especie (búsqueda parcial)
        
        **Casos de uso:**
        - Formularios de registro de animales
        - Catálogos de especies
        - Filtros de búsqueda
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'name': {'description': 'Filtrar por nombre de especie', 'type': 'string'}
        },
        responses={
            200: ('Lista de especies', [species_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @etag_cache('species', cache_timeout=1800)  # 30 minutos
    @jwt_required()
    def get(self):
        """Obtener lista de especies"""
        try:
            # Usar consulta SQL raw para evitar problemas con TimestampMixin
            from app import db
            result = db.session.execute(db.text("SELECT id, name FROM species"))
            species_data = [{'id': row[0], 'name': row[1]} for row in result.fetchall()]
            
            return APIResponse.success(
                data={
                    'species': species_data,
                    'total': len(species_data),
                    'page': 1,
                    'per_page': len(species_data),
                    'pages': 1
                },
                message=f"Se encontraron {len(species_data)} especies"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo especies: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'create_breed',
        description='Crear una nueva raza',
        security=['Bearer', 'Cookie'],
        responses={
            201: 'Raza creada exitosamente',
            400: 'Datos inválidos',
            401: 'Token JWT requerido',
            404: 'Especie no encontrada',
            409: 'Raza ya existe',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def post(self):
        """Crear nueva raza"""
        try:
            data = request.get_json()
            if not data or 'name' not in data or 'species_id' not in data:
                return APIResponse.validation_error({
                    'name': 'El nombre es requerido',
                    'species_id': 'El ID de especie es requerido'
                })
            
            # Verificar que la especie existe usando SQL raw
            from app import db
            species_exists = db.session.execute(db.text("SELECT id FROM species WHERE id = :id"), {'id': data['species_id']}).fetchone()
            if not species_exists:
                return APIResponse.error(message="Especie no encontrada", status_code=404)
            
            # Verificar si ya existe la raza
            existing = db.session.execute(db.text("SELECT id FROM breeds WHERE name = :name AND species_id = :species_id"), {
                'name': data['name'],
                'species_id': data['species_id']
            }).fetchone()
            if existing:
                return APIResponse.error(message="La raza ya existe para esta especie", status_code=409)
            
            # Crear nueva raza
            db.session.execute(db.text("INSERT INTO breeds (name, species_id) VALUES (:name, :species_id)"), {
                'name': data['name'],
                'species_id': data['species_id']
            })
            db.session.commit()
            
            # Obtener la raza creada con información de especie
            new_breed = db.session.execute(db.text("""
                SELECT b.id, b.name, b.species_id, s.name as species_name 
                FROM breeds b 
                JOIN species s ON b.species_id = s.id 
                WHERE b.name = :name AND b.species_id = :species_id
            """), {
                'name': data['name'],
                'species_id': data['species_id']
            }).fetchone()
            
            return APIResponse.created(
                data={
                    'id': new_breed[0],
                    'name': new_breed[1],
                    'species_id': new_breed[2],
                    'species_name': new_breed[3]
                },
                message=f"Raza {data['name']} creada exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error creando raza: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'create_species',
        description='Crear una nueva especie',
        security=['Bearer', 'Cookie'],
        responses={
            201: 'Especie creada exitosamente',
            400: 'Datos inválidos',
            401: 'Token JWT requerido',
            409: 'Especie ya existe',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def post(self):
        """Crear nueva especie"""
        try:
            data = request.get_json()
            if not data or 'name' not in data:
                return APIResponse.validation_error({'name': 'El nombre es requerido'})
            
            # Verificar si ya existe
            from app import db
            existing = db.session.execute(db.text("SELECT id FROM species WHERE name = :name"), {'name': data['name']}).fetchone()
            if existing:
                return APIResponse.error(message="La especie ya existe", status_code=409)
            
            # Crear nueva especie
            db.session.execute(db.text("INSERT INTO species (name) VALUES (:name)"), {'name': data['name']})
            db.session.commit()
            
            # Obtener la especie creada
            new_species = db.session.execute(db.text("SELECT id, name FROM species WHERE name = :name"), {'name': data['name']}).fetchone()
            
            return APIResponse.created(
                data={'id': new_species[0], 'name': new_species[1]},
                message=f"Especie {data['name']} creada exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error creando especie: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINT DE ESTADÍSTICAS DE BREEDS Y SPECIES
# ============================================================================

@breeds_species_ns.route('/statistics')
class BreedsSpeciesStatistics(Resource):
    @breeds_species_ns.doc(
        'get_breeds_species_statistics',
        description='''
        **Obtener estadísticas de razas y especies**
        
        Retorna estadísticas consolidadas de especies y razas en el sistema.
        
        **Información incluida:**
        - Total de especies registradas
        - Total de razas por especie
        - Distribución de animales por raza
        - Especies más populares
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: 'Estadísticas de razas y especies',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @jwt_required()
    def get(self):
        """Obtener estadísticas de razas y especies"""
        try:
            # Obtener estadísticas de especies y razas
            species_stats = Species.get_statistics()
            breeds_stats = Breeds.get_statistics()
            
            return APIResponse.success(
                data={
                    'species': species_stats,
                    'breeds': breeds_stats,
                    'summary': {
                        'total_species': species_stats.get('total_species', 0),
                        'total_breeds': breeds_stats.get('total_breeds', 0),
                        'most_popular_species': species_stats.get('most_popular', 'N/A'),
                        'most_popular_breed': breeds_stats.get('most_popular', 'N/A')
                    }
                },
                message='Estadísticas de razas y especies obtenidas exitosamente'
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de razas y especies: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'create_species',
        description='''
        **Crear nueva especie**
        
        Registra una nueva especie en el sistema.
        Requiere permisos de Administrador.
        
        **Validaciones:**
        - Nombre de especie único
        - Nombre no puede estar vacío
        
        **Casos de uso:**
        - Expansión del catálogo de especies
        - Registro de nuevas especies ganaderas
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Especie creada exitosamente', species_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            409: 'La especie ya existe',
            500: 'Error interno del servidor'
        }
    )
    @breeds_species_ns.expect(species_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['name'],
        field_types={'name': str}
    )
    @invalidate_cache_on_change(['species_list'])
    @jwt_required()
    def post(self):
        """Crear nueva especie"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Validar que no exista la especie
            existing_species = Species.query.filter(
                Species.name.ilike(data['name'])
            ).first()
            
            if existing_species:
                return APIResponse.conflict(
                    message="La especie ya existe",
                    details={'name': data['name']}
                )
            
            # Crear nueva especie usando Species.create
            new_species = Species.create(name=data['name'])
            
            logger.info(
                f"Especie creada: {new_species.name} "
                f"por administrador {current_user.get('identification')}"
            )
            
            # Formatear respuesta
            species_data = ResponseFormatter.format_model(new_species)
            
            return APIResponse.created(
                data=species_data,
                message=f"Especie '{new_species.name}' creada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando especie: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando especie: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@breeds_species_ns.route('/species/<int:species_id>')
class SpeciesDetail(Resource):
    @breeds_species_ns.doc(
        'get_species_detail',
        description='''
        **Obtener especie específica**
        
        Retorna información detallada de una especie específica.
        
        **Parámetros:**
        - `species_id`: ID único de la especie
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información de la especie', species_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Especie no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("species_detail", ttl_seconds=1800)
    @jwt_required()
    def get(self, species_id):
        """Obtener especie por ID"""
        try:
            species = Species.query.get(species_id)
            if not species:
                return APIResponse.not_found("Especie")
            
            species_data = ResponseFormatter.format_model(species)
            
            return APIResponse.success(
                data=species_data,
                message=f"Información de especie '{species.name}' obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo especie {species_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'update_species',
        description='''
        **Actualizar especie**
        
        Actualiza información de una especie existente.
        Requiere permisos de Administrador.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Especie actualizada', species_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Especie no encontrada',
            409: 'Conflicto de datos',
            500: 'Error interno del servidor'
        }
    )
    @breeds_species_ns.expect(species_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['species_list', 'species_detail', 'breeds_list'])
    @jwt_required()
    def put(self, species_id):
        """Actualizar especie"""
        try:
            species = Species.query.get(species_id)
            if not species:
                return APIResponse.not_found("Especie")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Validar que no exista otra especie con el mismo nombre
            existing_species = Species.query.filter(
                Species.name.ilike(data['name']),
                Species.id != species_id
            ).first() if 'name' in data else None
            
            if existing_species:
                return APIResponse.conflict(
                    message="Ya existe otra especie con ese nombre",
                    details={'species': data['species']}
                )
            
            # Actualizar especie
            old_name = species.name
            if 'name' in data:
                species.name = data['name']
            
            db.session.commit()
            
            logger.info(
                f"Especie actualizada: '{old_name}' -> '{species.name}' "
                f"por administrador {current_user.get('identification')}"
            )
            
            species_data = ResponseFormatter.format_model(species)
            
            return APIResponse.success(
                data=species_data,
                message=f"Especie actualizada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad actualizando especie: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando especie {species_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'delete_species',
        description='''
        **Eliminar especie**
        
        Elimina una especie del sistema.
        Requiere permisos de Administrador.
        
        **Nota:** No se puede eliminar una especie que tenga razas asociadas.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Especie eliminada', success_message_model),
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Especie no encontrada',
            409: 'No se puede eliminar: existen razas relacionadas',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @invalidate_cache_on_change(['species_list', 'species_detail'])
    @jwt_required()
    def delete(self, species_id):
        """Eliminar especie"""
        try:
            species = Species.query.get(species_id)
            if not species:
                return APIResponse.not_found("Especie")
            
            current_user = get_jwt_identity()
            
            # Verificar que no tenga razas asociadas
            breeds_count = Breeds.query.filter_by(species_id=species_id).count()
            if breeds_count > 0:
                return APIResponse.conflict(
                    message="No se puede eliminar la especie",
                    details={
                        'reason': f'Existen {breeds_count} razas asociadas a esta especie',
                        'breeds_count': breeds_count
                    }
                )
            
            species_name = species.name
            species.delete()
            
            logger.info(
                f"Especie eliminada: '{species_name}' "
                f"por administrador {current_user.get('identification')}"
            )
            
            return APIResponse.success(
                message=f"Especie '{species_name}' eliminada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad eliminando especie: {str(e)}")
            return APIResponse.conflict(
                message="No se puede eliminar: existen registros relacionados",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando especie {species_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE RAZAS
# ============================================================================

@breeds_species_ns.route('/breeds')
class BreedsList(Resource):
    @breeds_species_ns.doc(
        'get_breeds_list',
        description='''
        **Obtener lista de razas**
        
        Retorna todas las razas disponibles con información de especies.
        
        **Parámetros opcionales:**
        - `name`: Filtrar por nombre de raza (búsqueda parcial)
        - `species_id`: Filtrar por especie específica
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        
        **Casos de uso:**
        - Formularios de registro de animales
        - Catálogos de razas por especie
        - Análisis genético
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'name': {'description': 'Filtrar por nombre de raza', 'type': 'string'},
            'species_id': {'description': 'Filtrar por ID de especie', 'type': 'integer'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de razas', [breed_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @conditional_cache(['breeds', 'species'], cache_timeout=1800)  # 30 minutos
    @jwt_required()
    def get(self):
        """Obtener lista de razas con información de especies"""
        try:
            # Usar consulta SQL raw para evitar problemas con TimestampMixin
            from app import db
            result = db.session.execute(db.text("""
                SELECT b.id, b.name, b.species_id, s.name as species_name 
                FROM breeds b 
                JOIN species s ON b.species_id = s.id
                ORDER BY s.name, b.name
            """))
            breeds_data = [{
                'id': row[0], 
                'name': row[1], 
                'species_id': row[2], 
                'species_name': row[3]
            } for row in result.fetchall()]
            
            return APIResponse.success(
                data={
                    'breeds': breeds_data,
                    'total': len(breeds_data),
                    'page': 1,
                    'per_page': len(breeds_data),
                    'pages': 1
                },
                message=f"Se encontraron {len(breeds_data)} razas"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo razas: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'create_breed',
        description='''
        **Crear nueva raza**
        
        Registra una nueva raza asociada a una especie.
        Requiere permisos de Administrador.
        
        **Validaciones:**
        - Nombre de raza único dentro de la especie
        - Especie debe existir
        - Nombre no puede estar vacío
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Raza creada exitosamente', breed_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Especie no encontrada',
            409: 'La raza ya existe en esta especie',
            500: 'Error interno del servidor'
        }
    )
    @breeds_species_ns.expect(breed_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['name', 'species_id'],
        field_types={'name': str, 'species_id': int}
    )
    @invalidate_cache_on_change(['breeds_list'])
    @jwt_required()
    def post(self):
        """Crear nueva raza"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que la especie existe
            species = Species.query.get(data['species_id'])
            if not species:
                return APIResponse.not_found("Especie")
            
            # Validar que no exista la raza en esta especie
            existing_breed = Breeds.query.filter(
                Breeds.name.ilike(data['name']),
                Breeds.species_id == data['species_id']
            ).first()
            
            if existing_breed:
                return APIResponse.conflict(
                    message="La raza ya existe en esta especie",
                    details={
                        'name': data['name'],
                        'species': species.name
                    }
                )
            
            # Crear nueva raza usando Breeds.create
            new_breed = Breeds.create(
                name=data['name'],
                species_id=data['species_id']
            )
            
            logger.info(
                f"Raza creada: {new_breed.name} ({species.name}) "
                f"por administrador {current_user.get('identification')}"
            )
            
            # Formatear respuesta con información de especie
            breed_data = ResponseFormatter.format_model(new_breed)
            breed_data['species'] = ResponseFormatter.format_model(species)
            
            return APIResponse.created(
                data=breed_data,
                message=f"Raza '{new_breed.name}' creada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando raza: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando raza: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@breeds_species_ns.route('/breeds/<int:breed_id>')
class BreedDetail(Resource):
    @breeds_species_ns.doc(
        'get_breed_detail',
        description='''
        **Obtener raza específica**
        
        Retorna información detallada de una raza específica
        incluyendo información de la especie asociada.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información de la raza', breed_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Raza no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("breed_detail", ttl_seconds=1800)
    @jwt_required()
    def get(self, breed_id):
        """Obtener raza por ID"""
        try:
            breed = Breeds.query.get(breed_id)
            if not breed:
                return APIResponse.not_found("Raza")
            
            # Formatear respuesta con información de especie
            breed_data = ResponseFormatter.format_model(breed)
            if breed.species:
                breed_data['species'] = ResponseFormatter.format_model(breed.species)
            
            return APIResponse.success(
                data=breed_data,
                message=f"Información de raza '{breed.name}' obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo raza {breed_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'update_breed',
        description='''
        **Actualizar raza**
        
        Actualiza información de una raza existente.
        Requiere permisos de Administrador.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Raza actualizada', breed_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Raza no encontrada',
            409: 'Conflicto de datos',
            500: 'Error interno del servidor'
        }
    )
    @breeds_species_ns.expect(breed_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['breeds_list', 'breed_detail'])
    @jwt_required()
    def put(self, breed_id):
        """Actualizar raza"""
        try:
            breed = Breeds.query.get(breed_id)
            if not breed:
                return APIResponse.not_found("Raza")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Si se actualiza la especie, verificar que existe
            if 'species_id' in data:
                species = Species.query.get(data['species_id'])
                if not species:
                    return APIResponse.not_found("Especie")
                breed.species_id = data['species_id']
            
            # Si se actualiza el nombre, verificar unicidad
            if 'name' in data:
                existing_breed = Breeds.query.filter(
                    Breeds.name.ilike(data['name']),
                    Breeds.species_id == breed.species_id,
                    Breeds.id != breed_id
                ).first()
                if existing_breed:
                    return APIResponse.conflict(
                        message="Ya existe otra raza con ese nombre en esta especie",
                        details={'name': data['name']}
                    )
                breed.name = data['name']
            
            db.session.commit()
            
            logger.info(
                f"Raza actualizada: {breed.name} "
                f"por administrador {current_user.get('identification')}"
            )
            
            # Formatear respuesta
            breed_data = ResponseFormatter.format_model(breed)
            if breed.species:
                breed_data['species'] = ResponseFormatter.format_model(breed.species)
            
            return APIResponse.success(
                data=breed_data,
                message=f"Raza actualizada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad actualizando raza: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando raza {breed_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @breeds_species_ns.doc(
        'delete_breed',
        description='''
        **Eliminar raza**
        
        Elimina una raza del sistema.
        Requiere permisos de Administrador.
        
        **Nota:** No se puede eliminar una raza que tenga animales asociados.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Raza eliminada', success_message_model),
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Raza no encontrada',
            409: 'No se puede eliminar: existen animales relacionados',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @invalidate_cache_on_change(['breeds_list', 'breed_detail'])
    @jwt_required()
    def delete(self, breed_id):
        """Eliminar raza"""
        try:
            breed = Breeds.query.get(breed_id)
            if not breed:
                return APIResponse.not_found("Raza")
            
            current_user = get_jwt_identity()
            
            # Verificar que no tenga animales asociados
            from app.models.animals import Animals
            animals_count = Animals.query.filter_by(breeds_id=breed_id).count()
            if animals_count > 0:
                return APIResponse.conflict(
                    message="No se puede eliminar la raza",
                    details={
                        'reason': f'Existen {animals_count} animales de esta raza',
                        'animals_count': animals_count
                    }
                )
            
            breed_name = breed.name
            species_name = breed.species.name if breed.species else "N/A"
            
            # Use model delete to centralize commit and cascade handling
            breed.delete()
            
            logger.info(
                f"Raza eliminada: '{breed_name}' ({species_name}) "
                f"por administrador {current_user.get('identification')}"
            )
            
            return APIResponse.success(
                message=f"Raza '{breed_name}' eliminada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad eliminando raza: {str(e)}")
            return APIResponse.conflict(
                message="No se puede eliminar: existen registros relacionados",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando raza {breed_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@breeds_species_ns.route('/breeds/by-species/<int:species_id>')
class BreedsBySpecies(Resource):
    @breeds_species_ns.doc(
        'get_breeds_by_species',
        description='''
        **Obtener razas por especie**
        
        Retorna todas las razas de una especie específica.
        Útil para formularios en cascada.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Razas de la especie', [breed_response_model]),
            401: 'Token JWT requerido o inválido',
            404: 'Especie no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("breeds_by_species", ttl_seconds=1800)
    @jwt_required()
    def get(self, species_id):
        """Obtener razas de una especie específica"""
        try:
            # Verificar que la especie existe
            species = Species.query.get(species_id)
            if not species:
                return APIResponse.not_found("Especie")
            
            # Obtener razas de la especie
            breeds = Breeds.query.filter_by(species_id=species_id).order_by(Breeds.name).all()
            
            # Formatear respuesta
            breeds_data = ResponseFormatter.format_model_list(breeds)
            
            return APIResponse.success(
                data=breeds_data,
                message=f"Se encontraron {len(breeds)} razas de {species.name}"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo razas de especie {species_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )