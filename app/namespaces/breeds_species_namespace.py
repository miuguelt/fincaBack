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
from app.utils.cache_manager import (
    cache_query_result, invalidate_cache_on_change, QueryOptimizer
)
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
            # Obtener filtros
            name_filter = request.args.get('name')
            
            # Construir consulta
            query = Species.query
            
            if name_filter:
                query = query.filter(Species.name.ilike(f"%{name_filter}%"))
            
            species = query.order_by(Species.name).all()
            
            # Formatear respuesta
            species_data = ResponseFormatter.format_model_list(species)
            
            return APIResponse.success(
                data=species_data,
                message=f"Se encontraron {len(species)} especies"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo especies: {str(e)}")
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
            
            # Crear nueva especie
            new_species = Species(name=data['name'])
            
            db.session.add(new_species)
            db.session.commit()
            
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
                message=f"Información de especie '{species.species}' obtenida exitosamente"
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
                Species.species.ilike(data['species']),
                Species.id != species_id
            ).first()
            
            if existing_species:
                return APIResponse.conflict(
                    message="Ya existe otra especie con ese nombre",
                    details={'species': data['species']}
                )
            
            # Actualizar especie
            old_name = species.species
            species.species = data['species']
            
            db.session.commit()
            
            logger.info(
                f"Especie actualizada: '{old_name}' -> '{species.species}' "
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
            
            species_name = species.species
            db.session.delete(species)
            db.session.commit()
            
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
        """Obtener lista de razas con paginación y filtros"""
        try:
            # Obtener parámetros
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            name_filter = request.args.get('name')
            species_id = request.args.get('species_id')
            
            # Construir consulta con join a especies
            query = db.session.query(Breeds).join(Species)
            
            # Aplicar filtros
            if name_filter:
                query = query.filter(Breeds.name.ilike(f"%{name_filter}%"))
            
            if species_id:
                query = query.filter(Breeds.species_id == species_id)
            
            # Aplicar paginación
            breeds, total, page, per_page = QueryOptimizer.optimize_pagination(
                query.order_by(Breeds.name), page, per_page
            )
            
            # Formatear datos con información de especies
            breeds_data = []
            for breed in breeds:
                breed_dict = ResponseFormatter.format_model(breed)
                if breed.species:
                    breed_dict['species'] = ResponseFormatter.format_model(breed.species)
                breeds_data.append(breed_dict)
            
            return APIResponse.paginated_success(
                data=breeds_data,
                page=page,
                per_page=per_page,
                total=total,
                message=f"Se encontraron {total} razas"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'pagination': 'Parámetros de paginación inválidos'}
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
            
            # Crear nueva raza
            new_breed = Breeds(
                name=data['name'],
                species_id=data['species_id']
            )
            
            db.session.add(new_breed)
            db.session.commit()
            
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
                message=f"Información de raza '{breed.breed}' obtenida exitosamente"
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
            if 'breed' in data:
                existing_breed = Breeds.query.filter(
                    Breeds.breed.ilike(data['breed']),
                    Breeds.species_id == breed.species_id,
                    Breeds.id != breed_id
                ).first()
                
                if existing_breed:
                    return APIResponse.conflict(
                        message="Ya existe otra raza con ese nombre en esta especie",
                        details={'breed': data['breed']}
                    )
                
                breed.breed = data['breed']
            
            db.session.commit()
            
            logger.info(
                f"Raza actualizada: {breed.breed} "
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
            
            breed_name = breed.breed
            species_name = breed.species.species if breed.species else "N/A"
            
            db.session.delete(breed)
            db.session.commit()
            
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
            breeds = Breeds.query.filter_by(species_id=species_id).order_by(Breeds.breed).all()
            
            # Formatear respuesta
            breeds_data = ResponseFormatter.format_model_list(breeds)
            
            return APIResponse.success(
                data=breeds_data,
                message=f"Se encontraron {len(breeds)} razas de {species.species}"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo razas de especie {species_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )