from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.control import Control, HealtStatus
from app.models.fields import Fields, LandStatus
from app.models.diseases import Diseases
from app.models.geneticImprovements import GeneticImprovements
from app.models.foodTypes import FoodTypes
from app.models.animals import Animals
from app import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging

# Importar utilidades de optimización
from app.utils.response_handler import APIResponse, ResponseFormatter
from app.utils.validators import (
    RequestValidator, PerformanceLogger, SecurityValidator
)
from app.utils.cache_manager import (
    cache_query_result, invalidate_cache_on_change, QueryOptimizer
)

# Crear el namespace
management_ns = Namespace(
    'management',
    description='🏞️ Gestión y Control - Campos, Salud y Mejoras Genéticas',
    path='/management'
)

logger = logging.getLogger(__name__)

# Modelos para documentación
control_input_model = management_ns.model('ControlInput', {
    'checkup_date': fields.Date(required=True, description='Fecha de control (YYYY-MM-DD)', example='2023-06-15'),
    'healt_status': fields.String(required=True, description='Estado de salud', enum=['Excelente', 'Bueno', 'Regular', 'Malo'], example='Bueno'),
    'description': fields.String(required=True, description='Descripción del control', example='Control rutinario de peso y salud'),
    'animal_id': fields.Integer(required=True, description='ID del animal controlado', example=1)
})

control_update_model = management_ns.model('ControlUpdate', {
    'checkup_date': fields.Date(description='Fecha de control (YYYY-MM-DD)'),
    'healt_status': fields.String(description='Estado de salud', enum=['Excelente', 'Bueno', 'Regular', 'Malo']),
    'description': fields.String(description='Descripción del control'),
    'animal_id': fields.Integer(description='ID del animal controlado')
})

control_response_model = management_ns.model('ControlResponse', {
    'id': fields.Integer(description='ID único del control'),
    'checkup_date': fields.String(description='Fecha de control'),
    'healt_status': fields.String(description='Estado de salud'),
    'description': fields.String(description='Descripción del control'),
    'animal_id': fields.Integer(description='ID del animal controlado'),
    'animals': fields.Raw(description='Datos del animal')
})

field_input_model = management_ns.model('FieldInput', {
    'name': fields.String(required=True, description='Nombre del campo', example='Potrero Norte'),
    'ubication': fields.String(required=True, description='Ubicación del campo', example='Sector Norte'),
    'capacity': fields.String(required=True, description='Capacidad del campo', example='50 animales'),
    'state': fields.String(required=True, description='Estado del campo', enum=['Disponible', 'Ocupado', 'Mantenimiento', 'Restringido', 'Dañado'], example='Disponible'),
    'handlings': fields.String(required=True, description='Manejos del campo', example='Pastoreo rotativo'),
    'guages': fields.String(required=True, description='Medidas del campo', example='100m x 150m'),
    'area': fields.String(required=True, description='Área del campo', example='15.5 hectáreas'),
    'food_type_id': fields.Integer(description='ID del tipo de alimento', example=1)
})

field_response_model = management_ns.model('FieldResponse', {
    'id': fields.Integer(description='ID único del campo'),
    'name': fields.String(description='Nombre del campo'),
    'ubication': fields.String(description='Ubicación del campo'),
    'capacity': fields.String(description='Capacidad del campo'),
    'state': fields.String(description='Estado del campo'),
    'handlings': fields.String(description='Manejos del campo'),
    'guages': fields.String(description='Medidas del campo'),
    'area': fields.String(description='Área del campo'),
    'food_type_id': fields.Integer(description='ID del tipo de alimento'),
    'food_types': fields.Raw(description='Datos del tipo de alimento')
})

disease_input_model = management_ns.model('DiseaseInput', {
    'disease': fields.String(required=True, description='Nombre de la enfermedad', example='Fiebre Aftosa'),
    'description': fields.String(description='Descripción de la enfermedad', example='Enfermedad viral altamente contagiosa'),
    'symptoms': fields.String(description='Síntomas principales', example='Fiebre, lesiones en boca y patas'),
    'treatment': fields.String(description='Tratamiento recomendado', example='Aislamiento y medicación específica')
})

disease_response_model = management_ns.model('DiseaseResponse', {
    'id': fields.Integer(description='ID único de la enfermedad'),
    'disease': fields.String(description='Nombre de la enfermedad'),
    'description': fields.String(description='Descripción de la enfermedad'),
    'symptoms': fields.String(description='Síntomas principales'),
    'treatment': fields.String(description='Tratamiento recomendado')
})

genetic_improvement_input_model = management_ns.model('GeneticImprovementInput', {
    'improvement_type': fields.String(required=True, description='Tipo de mejora genética', example='Inseminación Artificial'),
    'description': fields.String(description='Descripción de la mejora', example='Mejora de características productivas'),
    'expected_result': fields.String(description='Resultado esperado', example='Aumento del 20% en producción'),
    'date': fields.String(description='Fecha de la mejora (YYYY-MM-DD)', example='2023-06-15'),
    'animal_id': fields.Integer(required=True, description='ID del animal', example=1)
})

genetic_improvement_update_model = management_ns.model('GeneticImprovementUpdate', {
    'improvement_type': fields.String(description='Tipo de mejora genética'),
    'description': fields.String(description='Descripción de la mejora'),
    'expected_result': fields.String(description='Resultado esperado'),
    'date': fields.String(description='Fecha de la mejora (YYYY-MM-DD)'),
    'animal_id': fields.Integer(description='ID del animal')
})

genetic_improvement_response_model = management_ns.model('GeneticImprovementResponse', {
    'id': fields.Integer(description='ID único de la mejora genética'),
    'genetic_event_techique': fields.String(description='Tipo de mejora genética'),
    'details': fields.String(description='Descripción de la mejora'),
    'results': fields.String(description='Resultado esperado'),
    'date': fields.String(description='Fecha de la mejora'),
    'animal_id': fields.Integer(description='ID del animal'),
    'animals': fields.Raw(description='Datos del animal')
})

food_type_input_model = management_ns.model('FoodTypeInput', {
    'food_type': fields.String(required=True, description='Tipo de alimento', example='Concentrado'),
    'description': fields.String(description='Descripción del alimento', example='Alimento balanceado para bovinos'),
    'nutritional_value': fields.String(description='Valor nutricional', example='Proteína: 18%, Fibra: 12%'),
    'cost_per_kg': fields.Float(description='Costo por kilogramo', example=2.5)
})

food_type_response_model = management_ns.model('FoodTypeResponse', {
    'id': fields.Integer(description='ID único del tipo de alimento'),
    'food_type': fields.String(description='Tipo de alimento'),
    'description': fields.String(description='Descripción del alimento'),
    'nutritional_value': fields.String(description='Valor nutricional'),
    'cost_per_kg': fields.Float(description='Costo por kilogramo')
})

success_message_model = management_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito')
})

# ============================================================================
# ENDPOINTS DE CONTROL DE SALUD
# ============================================================================

@management_ns.route('/controls')
class ControlsList(Resource):
    @management_ns.doc(
        'get_controls_list',
        description='''
        **Obtener lista de controles de salud**
        
        Retorna todos los controles de salud registrados.
        
        **Parámetros opcionales:**
        - `animal_id`: Filtrar por animal específico
        - `health_status`: Filtrar por estado de salud
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        - `min_weight`: Peso mínimo
        - `max_weight`: Peso máximo
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        
        **Casos de uso:**
        - Seguimiento de peso y salud
        - Análisis de crecimiento
        - Reportes veterinarios
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'animal_id': {'description': 'Filtrar por ID de animal', 'type': 'integer'},
            'health_status': {'description': 'Filtrar por estado de salud', 'type': 'string', 'enum': ['Excelente', 'Bueno', 'Regular', 'Malo']},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'},
            'min_weight': {'description': 'Peso mínimo en kg', 'type': 'integer'},
            'max_weight': {'description': 'Peso máximo en kg', 'type': 'integer'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de controles', [control_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("controls_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de controles"""
        try:
            # Consulta básica sin filtros complejos
            controls = Control.query.all()
            
            # Formatear datos básicos
            controls_data = []
            for control in controls:
                try:
                    control_dict = {
                        'id': control.id,
                        'checkup_date': control.checkup_date.strftime('%Y-%m-%d') if control.checkup_date else None,
                        'healt_status': control.healt_status.value if control.healt_status else None,
                        'description': control.description,
                        'animal_id': control.animal_id
                    }
                    controls_data.append(control_dict)
                except Exception as control_error:
                    logger.error(f"Error procesando control {control.id}: {str(control_error)}")
                    continue
            
            return APIResponse.success(
                data=controls_data,
                message=f"Se encontraron {len(controls_data)} controles"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo controles: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

    @management_ns.doc(
        'create_control',
        description='''
        **Crear nuevo control de salud**
        
        Registra un nuevo control de salud para un animal.
        
        **Validaciones:**
        - Animal debe existir
        - Fecha no puede ser futura
        - Peso debe ser positivo
        - Estado de salud debe ser válido
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Control creado exitosamente', control_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Animal no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(control_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['checkup_date', 'healt_status', 'description', 'animal_id'],
        field_types={
            'checkup_date': str,
            'healt_status': str,
            'description': str,
            'animal_id': int
        }
    )
    @invalidate_cache_on_change(['controls_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo control de salud"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el animal existe
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            # Validar fecha
            checkup_date = datetime.strptime(data['checkup_date'], '%Y-%m-%d').date()
            if checkup_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'checkup_date': 'La fecha del control no puede ser futura'}
                )
            
            # Validar estado de salud
            try:
                health_status = HealtStatus(data['healt_status'])
            except ValueError:
                return APIResponse.validation_error(
                    {'healt_status': f'Estado de salud inválido: {data["healt_status"]}. Valores permitidos: Excelente, Bueno, Regular, Malo'}
                )
            
            # Crear nuevo control
            new_control = Control(
                checkup_date=checkup_date,
                healt_status=health_status,
                description=data['description'],
                animal_id=data['animal_id']
            )
            
            db.session.add(new_control)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Control creado: Animal {animal.record}, Estado: {health_status.value}, "
                f"Descripción: {data['description']} por usuario {user_id}"
            )
            
            # Formatear respuesta
            control_data = ResponseFormatter.format_model(new_control)
            control_data['animal_record'] = animal.record
            
            return APIResponse.created(
                data=control_data,
                message=f"Control registrado exitosamente para {animal.record}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando control: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando control: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@management_ns.route('/fields/<int:field_id>')
class FieldDetail(Resource):
    @management_ns.doc(
        'get_field_detail',
        description='Obtener información detallada de un campo específico',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información del campo', field_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Campo no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("field_detail", ttl_seconds=600)
    @jwt_required()
    def get(self, field_id):
        """Obtener campo por ID"""
        try:
            field = Fields.query.get(field_id)
            if not field:
                return APIResponse.not_found("Campo")
            
            field_data = {
                'id': field.id,
                'name': field.name,
                'ubication': field.ubication,
                'capacity': field.capacity,
                'state': field.state.value if field.state else None,
                'handlings': field.handlings,
                'guages': field.guages,
                'area': field.area,
                'food_type_id': field.food_type_id
            }
            
            return APIResponse.success(
                data=field_data,
                message="Información del campo obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo campo {field_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'update_field',
        description='Actualizar información de un campo',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Campo actualizado', field_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Campo no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['fields_list', 'field_detail'])
    @jwt_required()
    def put(self, field_id):
        """Actualizar campo"""
        try:
            field = Fields.query.get(field_id)
            if not field:
                return APIResponse.not_found("Campo")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Actualizar campos
            if 'name' in data:
                field.name = data['name']
            if 'ubication' in data:
                field.ubication = data['ubication']
            if 'capacity' in data:
                field.capacity = data['capacity']
            if 'state' in data:
                try:
                    field.state = LandStatus(data['state'])
                except ValueError:
                    return APIResponse.validation_error(
                        {'state': f'Estado inválido: {data["state"]}'}
                    )
            if 'handlings' in data:
                field.handlings = data['handlings']
            if 'guages' in data:
                field.guages = data['guages']
            if 'area' in data:
                field.area = data['area']
            if 'food_type_id' in data:
                field.food_type_id = data['food_type_id']
            
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Campo actualizado: ID {field_id} "
                f"por usuario {user_id}"
            )
            
            field_data = {
                'id': field.id,
                'name': field.name,
                'ubication': field.ubication,
                'capacity': field.capacity,
                'state': field.state.value if field.state else None,
                'handlings': field.handlings,
                'guages': field.guages,
                'area': field.area,
                'food_type_id': field.food_type_id
            }
            
            return APIResponse.success(
                data=field_data,
                message="Campo actualizado exitosamente"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando campo {field_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'delete_field',
        description='Eliminar un campo del sistema',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Campo eliminado', success_message_model),
            401: 'Token JWT requerido o inválido',
            404: 'Campo no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @invalidate_cache_on_change(['fields_list', 'field_detail'])
    @jwt_required()
    def delete(self, field_id):
        """Eliminar campo"""
        try:
            field = Fields.query.get(field_id)
            if not field:
                return APIResponse.not_found("Campo")
            
            current_user = get_jwt_identity()
            
            field_info = f"{field.name} - {field.ubication}"
            
            db.session.delete(field)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Campo eliminado: {field_info} "
                f"por usuario {user_id}"
            )
            
            return APIResponse.success(
                message="Campo eliminado exitosamente"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando campo {field_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@management_ns.route('/controls/<int:control_id>')
class ControlDetail(Resource):
    @management_ns.doc(
        'get_control_detail',
        description='Obtener información detallada de un control específico',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información del control', control_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Control no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("control_detail", ttl_seconds=600)
    @jwt_required()
    def get(self, control_id):
        """Obtener control por ID"""
        try:
            control = Control.query.get(control_id)
            if not control:
                return APIResponse.not_found("Control")
            
            # Formatear respuesta con información del animal
            control_data = ResponseFormatter.format_model(control)
            if control.animals:
                    control_data['animal_record'] = control.animals.record
            
            return APIResponse.success(
                data=control_data,
                message="Información del control obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo control {control_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'update_control',
        description='Actualizar información de un control',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Control actualizado', control_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Control no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(control_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['controls_list', 'control_detail'])
    @jwt_required()
    def put(self, control_id):
        """Actualizar control"""
        try:
            control = Control.query.get(control_id)
            if not control:
                return APIResponse.not_found("Control")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Actualizar campos
            if 'control_date' in data:
                control_date = datetime.strptime(data['control_date'], '%Y-%m-%d').date()
                if control_date > datetime.now().date():
                    return APIResponse.validation_error(
                        {'control_date': 'La fecha del control no puede ser futura'}
                    )
                control.checkup_date = control_date
            
            if 'healt_status' in data:
                try:
                    health_status = HealtStatus(data['healt_status'])
                    control.healt_status = health_status
                except ValueError:
                    return APIResponse.validation_error(
                        {'healt_status': f'Estado de salud inválido: {data["healt_status"]}'}
                    )
            
            if 'weight' in data:
                if data['weight'] <= 0:
                    return APIResponse.validation_error(
                        {'weight': 'El peso debe ser mayor a 0'}
                    )
                control.weight = data['weight']
            
            if 'animal_id' in data:
                animal = Animals.query.get(data['animal_id'])
                if not animal:
                    return APIResponse.not_found("Animal")
                control.animal_id = data['animal_id']
            
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Control actualizado: ID {control_id} "
                f"por usuario {user_id}"
            )
            
            # Formatear respuesta
            control_data = ResponseFormatter.format_model(control)
            if control.animals:
                control_data['animal_record'] = control.animals.record
            
            return APIResponse.success(
                data=control_data,
                message="Control actualizado exitosamente"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad actualizando control: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando control {control_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'delete_control',
        description='Eliminar un control del sistema',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Control eliminado', success_message_model),
            401: 'Token JWT requerido o inválido',
            404: 'Control no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @invalidate_cache_on_change(['controls_list', 'control_detail'])
    @jwt_required()
    def delete(self, control_id):
        """Eliminar control"""
        try:
            control = Control.query.get(control_id)
            if not control:
                return APIResponse.not_found("Control")
            
            current_user = get_jwt_identity()
            
            control_info = f"{control.checkup_date} - {control.healt_status.value if control.healt_status else 'N/A'}"
            animal_record = control.animals.record if control.animals else "N/A"
            
            db.session.delete(control)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Control eliminado: {control_info} (Animal: {animal_record}) "
                f"por usuario {user_id}"
            )
            
            return APIResponse.success(
                message="Control eliminado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad eliminando control: {str(e)}")
            return APIResponse.conflict(
                message="No se puede eliminar: existen registros relacionados",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando control {control_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE CAMPOS
# ============================================================================

@management_ns.route('/fields')
class FieldsList(Resource):
    @management_ns.doc(
        'get_fields_list',
        description='''
        **Obtener lista de campos**
        
        Retorna todos los campos/potreros de la finca.
        
        **Parámetros opcionales:**
        - `status`: Filtrar por estado del campo
        - `min_area`: Área mínima en hectáreas
        - `max_area`: Área máxima en hectáreas
        - `available_capacity`: Solo campos con capacidad disponible
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'status': {'description': 'Filtrar por estado', 'type': 'string', 'enum': ['Disponible', 'Ocupado', 'Mantenimiento']},
            'min_area': {'description': 'Área mínima en hectáreas', 'type': 'number'},
            'max_area': {'description': 'Área máxima en hectáreas', 'type': 'number'},
            'available_capacity': {'description': 'Solo campos con capacidad disponible', 'type': 'boolean'}
        },
        responses={
            200: ('Lista de campos', [field_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("fields_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de campos"""
        try:
            # Consulta básica sin filtros para identificar el problema
            fields = Fields.query.all()
            
            # Formatear datos básicos
            fields_data = []
            for field in fields:
                try:
                    field_dict = {
                        'id': field.id,
                        'name': field.name,
                        'ubication': field.ubication,
                        'capacity': field.capacity,
                        'state': field.state.value if field.state else None,
                        'handlings': field.handlings,
                        'guages': field.guages,
                        'area': field.area,
                        'food_type_id': field.food_type_id
                    }
                    fields_data.append(field_dict)
                except Exception as field_error:
                    logger.error(f"Error procesando campo {field.id}: {str(field_error)}")
                    continue
            
            return APIResponse.success(
                data=fields_data,
                message=f"Se encontraron {len(fields_data)} campos"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo campos: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'create_field',
        description='''
        **Crear nuevo campo**
        
        Registra un nuevo campo/potrero en la finca.
        Requiere permisos de Administrador.
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Campo creado exitosamente', field_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            409: 'El campo ya existe',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(field_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['name', 'ubication', 'capacity', 'state', 'handlings', 'guages', 'area'],
        field_types={'name': str, 'ubication': str, 'capacity': str, 'state': str, 'handlings': str, 'guages': str, 'area': str, 'food_type_id': int}
    )
    @invalidate_cache_on_change(['fields_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo campo"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que no existe el campo
            existing_field = Fields.query.filter(
                Fields.name.ilike(data['name'])
            ).first()
            
            if existing_field:
                return APIResponse.conflict(
                    message="El campo ya existe",
                    details={'name': data['name']}
                )
            
            # Los campos area y capacity son strings, no se validan numéricamente
            
            # Crear nuevo campo
            new_field = Fields(
                name=data['name'],
                ubication=data['ubication'],
                capacity=data['capacity'],
                state=LandStatus(data['state']),
                handlings=data['handlings'],
                guages=data['guages'],
                area=data['area'],
                food_type_id=data.get('food_type_id')
            )
            
            db.session.add(new_field)
            db.session.commit()
            
            logger.info(
                f"Campo creado: {new_field.name} "
                f"por administrador {current_user}"
            )
            
            # Formatear respuesta
            field_data = ResponseFormatter.format_model(new_field)
            field_data['current_animals'] = 0
            
            return APIResponse.created(
                data=field_data,
                message=f"Campo '{new_field.name}' creado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando campo: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando campo: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE ENFERMEDADES
# ============================================================================

@management_ns.route('/diseases')
class DiseasesList(Resource):
    @management_ns.doc(
        'get_diseases_list',
        description='Obtener lista de enfermedades registradas',
        security=['Bearer', 'Cookie'],
        params={
            'name': {'description': 'Filtrar por nombre de enfermedad', 'type': 'string'}
        },
        responses={
            200: ('Lista de enfermedades', [disease_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("diseases_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de enfermedades"""
        try:
            name_filter = request.args.get('name')
            
            query = Diseases.query
            
            if name_filter:
                query = query.filter(Diseases.disease.ilike(f"%{name_filter}%"))
            
            diseases = query.order_by(Diseases.disease).all()
            
            diseases_data = ResponseFormatter.format_model_list(diseases)
            
            return APIResponse.success(
                data=diseases_data,
                message=f"Se encontraron {len(diseases)} enfermedades"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo enfermedades: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'create_disease',
        description='Crear nueva enfermedad',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Enfermedad creada', disease_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            409: 'La enfermedad ya existe',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(disease_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['diseases_list'])
    @jwt_required()
    def post(self):
        """Crear nueva enfermedad"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que no existe la enfermedad
            existing_disease = Diseases.query.filter(
                Diseases.disease.ilike(data['disease'])
            ).first()
            
            if existing_disease:
                return APIResponse.conflict(
                    message="La enfermedad ya existe",
                    details={'disease': data['disease']}
                )
            
            # Crear nueva enfermedad
            new_disease = Diseases(
                disease=data['disease'],
                description=data.get('description', ''),
                symptoms=data.get('symptoms', ''),
                treatment=data.get('treatment', '')
            )
            
            db.session.add(new_disease)
            db.session.commit()
            
            logger.info(
                f"Enfermedad creada: {new_disease.disease} "
                f"por administrador {current_user.get('identification')}"
            )
            
            disease_data = ResponseFormatter.format_model(new_disease)
            
            return APIResponse.created(
                data=disease_data,
                message=f"Enfermedad '{new_disease.disease}' creada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando enfermedad: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando enfermedad: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE MEJORAS GENÉTICAS
# ============================================================================

@management_ns.route('/genetic-improvements')
class GeneticImprovementsList(Resource):
    @management_ns.doc(
        'get_genetic_improvements_list',
        description='Obtener lista de mejoras genéticas',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Lista de mejoras genéticas', [genetic_improvement_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("genetic_improvements_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de mejoras genéticas"""
        try:
            improvements = GeneticImprovements.query.order_by(GeneticImprovements.genetic_event_techique).all()
            
            improvements_data = ResponseFormatter.format_model_list(improvements)
            
            return APIResponse.success(
                data=improvements_data,
                message=f"Se encontraron {len(improvements)} mejoras genéticas"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo mejoras genéticas: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'create_genetic_improvement',
        description='Crear nueva mejora genética',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Mejora genética creada', genetic_improvement_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(genetic_improvement_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['genetic_improvements_list'])
    @jwt_required()
    def post(self):
        """Crear nueva mejora genética"""
        try:
            data = request.get_json()
            user_id = get_jwt_identity()
            from flask_jwt_extended import get_jwt
            user_claims = get_jwt()
            
            # Crear nueva mejora genética
            new_improvement = GeneticImprovements(
                genetic_event_techique=data['improvement_type'],
                details=data.get('description', ''),
                results=data.get('expected_result', ''),
                date=datetime.strptime(data.get('date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
                animal_id=data['animal_id']
            )
            
            db.session.add(new_improvement)
            db.session.commit()
            
            logger.info(
                f"Mejora genética creada: {new_improvement.genetic_event_techique} "
                f"por administrador {user_claims.get('identification')}"
            )
            
            improvement_data = ResponseFormatter.format_model(new_improvement)
            
            return APIResponse.created(
                data=improvement_data,
                message=f"Mejora genética '{new_improvement.genetic_event_techique}' creada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando mejora genética: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando mejora genética: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@management_ns.route('/genetic-improvements/<int:improvement_id>')
class GeneticImprovementDetail(Resource):
    @management_ns.doc(
        'get_genetic_improvement',
        description='Obtener mejora genética específica',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Mejora genética encontrada', genetic_improvement_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Mejora genética no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("genetic_improvement_detail", ttl_seconds=600)
    @jwt_required()
    def get(self, improvement_id):
        """Obtener mejora genética por ID"""
        try:
            improvement = GeneticImprovements.query.get(improvement_id)
            if not improvement:
                return APIResponse.not_found("Mejora genética")
            
            improvement_data = ResponseFormatter.format_model(improvement)
            
            return APIResponse.success(
                data=improvement_data,
                message="Mejora genética encontrada"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo mejora genética {improvement_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'update_genetic_improvement',
        description='Actualizar mejora genética',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Mejora genética actualizada', genetic_improvement_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Mejora genética no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(genetic_improvement_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['genetic_improvements_list', 'genetic_improvement_detail'])
    @jwt_required()
    def put(self, improvement_id):
        """Actualizar mejora genética"""
        try:
            improvement = GeneticImprovements.query.get(improvement_id)
            if not improvement:
                return APIResponse.not_found("Mejora genética")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Actualizar campos
            if 'improvement_type' in data:
                improvement.genetic_event_techique = data['improvement_type']
            if 'description' in data:
                improvement.details = data['description']
            if 'expected_result' in data:
                improvement.results = data['expected_result']
            if 'date' in data:
                improvement.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            if 'animal_id' in data:
                improvement.animal_id = data['animal_id']
            
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Mejora genética actualizada: {improvement.genetic_event_techique} "
                f"por usuario {user_id}"
            )
            
            improvement_data = ResponseFormatter.format_model(improvement)
            
            return APIResponse.success(
                data=improvement_data,
                message="Mejora genética actualizada exitosamente"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando mejora genética {improvement_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'delete_genetic_improvement',
        description='Eliminar mejora genética',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Mejora genética eliminada', success_message_model),
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            404: 'Mejora genética no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @invalidate_cache_on_change(['genetic_improvements_list', 'genetic_improvement_detail'])
    @jwt_required()
    def delete(self, improvement_id):
        """Eliminar mejora genética"""
        try:
            improvement = GeneticImprovements.query.get(improvement_id)
            if not improvement:
                return APIResponse.not_found("Mejora genética")
            
            current_user = get_jwt_identity()
            
            improvement_info = f"{improvement.genetic_event_techique} - {improvement.date}"
            animal_record = improvement.animals.record if improvement.animals else "N/A"
            
            db.session.delete(improvement)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Mejora genética eliminada: {improvement_info} (Animal: {animal_record}) "
                f"por usuario {user_id}"
            )
            
            return APIResponse.success(
                message="Mejora genética eliminada exitosamente"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando mejora genética {improvement_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE TIPOS DE ALIMENTO
# ============================================================================

@management_ns.route('/food-types')
class FoodTypesList(Resource):
    @management_ns.doc(
        'get_food_types_list',
        description='Obtener lista de tipos de alimento',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Lista de tipos de alimento', [food_type_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("food_types_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de tipos de alimento"""
        try:
            food_types = FoodTypes.query.order_by(FoodTypes.food_type).all()
            
            food_types_data = ResponseFormatter.format_model_list(food_types)
            
            return APIResponse.success(
                data=food_types_data,
                message=f"Se encontraron {len(food_types)} tipos de alimento"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo tipos de alimento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @management_ns.doc(
        'create_food_type',
        description='Crear nuevo tipo de alimento',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Tipo de alimento creado', food_type_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            500: 'Error interno del servidor'
        }
    )
    @management_ns.expect(food_type_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['food_types_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo tipo de alimento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Crear nuevo tipo de alimento
            new_food_type = FoodTypes(
                food_type=data['food_type'],
                description=data.get('description', ''),
                nutritional_value=data.get('nutritional_value', ''),
                cost_per_kg=data.get('cost_per_kg')
            )
            
            db.session.add(new_food_type)
            db.session.commit()
            
            logger.info(
                f"Tipo de alimento creado: {new_food_type.food_type} "
                f"por administrador {current_user.get('identification')}"
            )
            
            food_type_data = ResponseFormatter.format_model(new_food_type)
            
            return APIResponse.created(
                data=food_type_data,
                message=f"Tipo de alimento '{new_food_type.food_type}' creado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando tipo de alimento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando tipo de alimento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )