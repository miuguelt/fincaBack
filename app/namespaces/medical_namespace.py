from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.treatments import Treatments
from app.models.vaccinations import Vaccinations
from app.models.vaccines import Vaccines
from app.models.medications import Medications
from app.models.animals import Animals
from app.models.user import User
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
medical_ns = Namespace(
    'medical',
    description='💊 Gestión Médica - Tratamientos, Vacunaciones y Medicamentos',
    path='/medical'
)

logger = logging.getLogger(__name__)

# Modelos para documentación
treatment_input_model = medical_ns.model('TreatmentInput', {
    'start_date': fields.Date(required=True, description='Fecha de inicio del tratamiento (YYYY-MM-DD)', example='2023-06-15'),
    'end_date': fields.Date(description='Fecha de fin del tratamiento (YYYY-MM-DD)', example='2023-06-25'),
    'description': fields.String(required=True, description='Descripción del tratamiento', example='Tratamiento antibiótico'),
    'frequency': fields.String(required=True, description='Frecuencia del tratamiento', example='Cada 12 horas'),
    'observations': fields.String(required=True, description='Observaciones del tratamiento', example='Aplicar con comida'),
    'dosis': fields.String(required=True, description='Dosis del tratamiento', example='5ml'),
    'animal_id': fields.Integer(required=True, description='ID del animal tratado', example=1)
})

treatment_update_model = medical_ns.model('TreatmentUpdate', {
    'start_date': fields.Date(description='Fecha de inicio del tratamiento (YYYY-MM-DD)'),
    'end_date': fields.Date(description='Fecha de fin del tratamiento (YYYY-MM-DD)'),
    'description': fields.String(description='Descripción del tratamiento'),
    'frequency': fields.String(description='Frecuencia del tratamiento'),
    'observations': fields.String(description='Observaciones del tratamiento'),
    'dosis': fields.String(description='Dosis del tratamiento'),
    'animal_id': fields.Integer(description='ID del animal tratado')
})

treatment_response_model = medical_ns.model('TreatmentResponse', {
    'id': fields.Integer(description='ID único del tratamiento'),
    'start_date': fields.String(description='Fecha de inicio del tratamiento'),
    'end_date': fields.String(description='Fecha de fin del tratamiento'),
    'description': fields.String(description='Descripción del tratamiento'),
    'frequency': fields.String(description='Frecuencia del tratamiento'),
    'observations': fields.String(description='Observaciones del tratamiento'),
    'dosis': fields.String(description='Dosis del tratamiento'),
    'animal_id': fields.Integer(description='ID del animal tratado'),
    'animals': fields.Raw(description='Datos del animal')
})

vaccination_input_model = medical_ns.model('VaccinationInput', {
    'application_date': fields.Date(required=True, description='Fecha de aplicación (YYYY-MM-DD)', example='2023-06-15'),
    'animal_id': fields.Integer(required=True, description='ID del animal vacunado', example=1),
    'vaccine_id': fields.Integer(required=True, description='ID de la vacuna', example=1),
    'apprentice_id': fields.Integer(description='ID del aprendiz', example=1),
    'instructor_id': fields.Integer(required=True, description='ID del instructor', example=2)
})

vaccination_update_model = medical_ns.model('VaccinationUpdate', {
    'application_date': fields.Date(description='Fecha de aplicación (YYYY-MM-DD)'),
    'animal_id': fields.Integer(description='ID del animal vacunado'),
    'vaccine_id': fields.Integer(description='ID de la vacuna'),
    'apprentice_id': fields.Integer(description='ID del aprendiz'),
    'instructor_id': fields.Integer(description='ID del instructor')
})

vaccination_response_model = medical_ns.model('VaccinationResponse', {
    'id': fields.Integer(description='ID único de la vacunación'),
    'application_date': fields.String(description='Fecha de aplicación'),
    'animal_id': fields.Integer(description='ID del animal vacunado'),
    'vaccine_id': fields.Integer(description='ID de la vacuna'),
    'apprentice_id': fields.Integer(description='ID del aprendiz'),
    'instructor_id': fields.Integer(description='ID del instructor'),
    'animals': fields.Raw(description='Datos del animal'),
    'vaccines': fields.Raw(description='Datos de la vacuna'),
    'apprentice': fields.Raw(description='Datos del aprendiz'),
    'instructor': fields.Raw(description='Datos del instructor')
})

medication_input_model = medical_ns.model('MedicationInput', {
    'medication': fields.String(required=True, description='Nombre del medicamento', example='Penicilina'),
    'description': fields.String(description='Descripción del medicamento', example='Antibiótico de amplio espectro')
})

medication_response_model = medical_ns.model('MedicationResponse', {
    'id': fields.Integer(description='ID único del medicamento'),
    'medication': fields.String(description='Nombre del medicamento'),
    'description': fields.String(description='Descripción del medicamento')
})

vaccine_input_model = medical_ns.model('VaccineInput', {
    'vaccine': fields.String(required=True, description='Nombre de la vacuna', example='Vacuna Triple'),
    'description': fields.String(description='Descripción de la vacuna', example='Protege contra 3 enfermedades')
})

vaccine_response_model = medical_ns.model('VaccineResponse', {
    'id': fields.Integer(description='ID único de la vacuna'),
    'vaccine': fields.String(description='Nombre de la vacuna'),
    'description': fields.String(description='Descripción de la vacuna')
})

success_message_model = medical_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito')
})

# ============================================================================
# ENDPOINTS DE TRATAMIENTOS
# ============================================================================

@medical_ns.route('/treatments')
class TreatmentsList(Resource):
    @medical_ns.doc(
        'get_treatments_list',
        description='''
        **Obtener lista de tratamientos**
        
        Retorna todos los tratamientos médicos registrados.
        
        **Parámetros opcionales:**
        - `animal_id`: Filtrar por animal específico
        - `diagnosis`: Filtrar por diagnóstico (búsqueda parcial)
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        
        **Casos de uso:**
        - Historial médico de animales
        - Reportes de tratamientos
        - Análisis de salud del hato
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'animal_id': {'description': 'Filtrar por ID de animal', 'type': 'integer'},
            'diagnosis': {'description': 'Filtrar por diagnóstico', 'type': 'string'},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de tratamientos', [treatment_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("treatments_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de tratamientos"""
        try:
            # Consulta básica sin filtros complejos
            treatments = Treatments.query.all()
            
            # Formatear datos básicos
            treatments_data = []
            for treatment in treatments:
                try:
                    treatment_dict = {
                        'id': treatment.id,
                        'start_date': treatment.start_date.strftime('%Y-%m-%d') if treatment.start_date else None,
                        'end_date': treatment.end_date.strftime('%Y-%m-%d') if treatment.end_date else None,
                        'description': treatment.description,
                        'frequency': treatment.frequency,
                        'observations': treatment.observations,
                        'dosis': treatment.dosis,
                        'animal_id': treatment.animal_id
                    }
                    treatments_data.append(treatment_dict)
                except Exception as treatment_error:
                    logger.error(f"Error procesando tratamiento {treatment.id}: {str(treatment_error)}")
                    continue
            
            return APIResponse.success(
                data=treatments_data,
                message=f"Se encontraron {len(treatments_data)} tratamientos"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo tratamientos: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'create_treatment',
        description='''
        **Crear nuevo tratamiento**
        
        Registra un nuevo tratamiento médico para un animal.
        
        **Validaciones:**
        - Animal debe existir
        - Fecha no puede ser futura
        - Diagnóstico y tipo de tratamiento son requeridos
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Tratamiento creado exitosamente', treatment_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Animal no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(treatment_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['start_date', 'description', 'frequency', 'observations', 'dosis', 'animal_id'],
        field_types={
            'start_date': str,
            'description': str,
            'frequency': str,
            'observations': str,
            'dosis': str,
            'animal_id': int
        }
    )
    @invalidate_cache_on_change(['treatments_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo tratamiento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el animal existe
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            # Validar fecha
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            if start_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'start_date': 'La fecha de inicio no puede ser futura'}
                )
            
            # Crear nuevo tratamiento
            new_treatment = Treatments(
                start_date=start_date,
                end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
                description=data['description'],
                frequency=data['frequency'],
                observations=data['observations'],
                dosis=data['dosis'],
                animal_id=data['animal_id']
            )
            
            db.session.add(new_treatment)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Tratamiento creado: Animal {animal.record}, Descripción: {data['description']} "
                f"por usuario {user_id}"
            )
            
            # Formatear respuesta
            treatment_data = ResponseFormatter.format_model(new_treatment)
            if new_treatment.animals:
                treatment_data['animal_record'] = new_treatment.animals.record
            
            return APIResponse.created(
                data=treatment_data,
                message=f"Tratamiento registrado exitosamente para {animal.record}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando tratamiento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando tratamiento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@medical_ns.route('/vaccinations/<int:vaccination_id>')
class VaccinationDetail(Resource):
    @medical_ns.doc(
        'get_vaccination_detail',
        description='Obtener información detallada de una vacunación específica',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información de la vacunación', vaccination_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Vacunación no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("vaccination_detail", ttl_seconds=600)
    @jwt_required()
    def get(self, vaccination_id):
        """Obtener vacunación por ID"""
        try:
            vaccination = Vaccinations.query.get(vaccination_id)
            if not vaccination:
                return APIResponse.not_found("Vacunación")
            
            # Formatear respuesta básica
            vaccination_data = {
                'id': vaccination.id,
                'application_date': vaccination.application_date.strftime('%Y-%m-%d') if vaccination.application_date else None,
                'animal_id': vaccination.animal_id,
                'vaccine_id': vaccination.vaccine_id,
                'apprentice_id': vaccination.apprentice_id,
                'instructor_id': vaccination.instructor_id
            }
            
            return APIResponse.success(
                data=vaccination_data,
                message="Información de la vacunación obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo vacunación {vaccination_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'update_vaccination',
        description='Actualizar información de una vacunación',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Vacunación actualizada', vaccination_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Vacunación no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(vaccination_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['vaccinations_list', 'vaccination_detail'])
    @jwt_required()
    def put(self, vaccination_id):
        """Actualizar vacunación"""
        try:
            vaccination = Vaccinations.query.get(vaccination_id)
            if not vaccination:
                return APIResponse.not_found("Vacunación")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Actualizar campos
            if 'application_date' in data:
                application_date = datetime.strptime(data['application_date'], '%Y-%m-%d').date()
                vaccination.application_date = application_date
            
            if 'animal_id' in data:
                vaccination.animal_id = data['animal_id']
            
            if 'vaccine_id' in data:
                vaccination.vaccine_id = data['vaccine_id']
            
            if 'apprentice_id' in data:
                vaccination.apprentice_id = data['apprentice_id']
            
            if 'instructor_id' in data:
                vaccination.instructor_id = data['instructor_id']
            
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(f"Vacunación {vaccination_id} actualizada por usuario {user_id}")
            
            # Formatear respuesta
            vaccination_data = {
                'id': vaccination.id,
                'application_date': vaccination.application_date.strftime('%Y-%m-%d') if vaccination.application_date else None,
                'animal_id': vaccination.animal_id,
                'vaccine_id': vaccination.vaccine_id,
                'apprentice_id': vaccination.apprentice_id,
                'instructor_id': vaccination.instructor_id
            }
            
            return APIResponse.success(
                data=vaccination_data,
                message="Vacunación actualizada exitosamente"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad actualizando vacunación: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando vacunación {vaccination_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'delete_vaccination',
        description='Eliminar una vacunación',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Vacunación eliminada', success_message_model),
            401: 'Token JWT requerido o inválido',
            404: 'Vacunación no encontrada',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @invalidate_cache_on_change(['vaccinations_list', 'vaccination_detail'])
    @jwt_required()
    def delete(self, vaccination_id):
        """Eliminar vacunación"""
        try:
            vaccination = Vaccinations.query.get(vaccination_id)
            if not vaccination:
                return APIResponse.not_found("Vacunación")
            
            current_user = get_jwt_identity()
            
            vaccination_info = f"Vacunación del {vaccination.application_date}"
            
            db.session.delete(vaccination)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(f"Vacunación {vaccination_id} eliminada: {vaccination_info} por usuario {user_id}")
            
            return APIResponse.success(
                message=f"Vacunación eliminada exitosamente: {vaccination_info}"
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando vacunación {vaccination_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'create_treatment',
        description='''
        **Crear nuevo tratamiento**
        
        Registra un nuevo tratamiento médico para un animal.
        
        **Validaciones:**
        - Animal debe existir
        - Fecha no puede ser futura
        - Diagnóstico y tipo de tratamiento son requeridos
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Tratamiento creado exitosamente', treatment_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Animal no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(treatment_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['start_date', 'description', 'frequency', 'observations', 'dosis', 'animal_id'],
        field_types={
            'start_date': str,
            'description': str,
            'frequency': str,
            'observations': str,
            'dosis': str,
            'animal_id': int
        }
    )
    @invalidate_cache_on_change(['treatments_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo tratamiento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el animal existe
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            # Validar fecha
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            if start_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'start_date': 'La fecha del tratamiento no puede ser futura'}
                )
            
            end_date = None
            if 'end_date' in data and data['end_date']:
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            
            # Crear nuevo tratamiento
            new_treatment = Treatments(
                start_date=start_date,
                end_date=end_date,
                description=data['description'],
                frequency=data['frequency'],
                observations=data['observations'],
                dosis=data['dosis'],
                animal_id=data['animal_id']
            )
            
            db.session.add(new_treatment)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Tratamiento creado: {new_treatment.description} para animal {animal.record} "
                f"por usuario {user_id}"
            )
            
            # Formatear respuesta
            treatment_data = ResponseFormatter.format_model(new_treatment)
            treatment_data['animal_record'] = animal.record
            
            return APIResponse.created(
                data=treatment_data,
                message=f"Tratamiento registrado exitosamente para {animal.record}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando tratamiento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando tratamiento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@medical_ns.route('/treatments/<int:treatment_id>')
class TreatmentDetail(Resource):
    @medical_ns.doc(
        'get_treatment_detail',
        description='Obtener información detallada de un tratamiento específico',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Información del tratamiento', treatment_response_model),
            401: 'Token JWT requerido o inválido',
            404: 'Tratamiento no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("treatment_detail", ttl_seconds=600)
    @jwt_required()
    def get(self, treatment_id):
        """Obtener tratamiento por ID"""
        try:
            treatment = Treatments.query.get(treatment_id)
            if not treatment:
                return APIResponse.not_found("Tratamiento")
            
            # Formatear respuesta con información del animal
            treatment_data = ResponseFormatter.format_model(treatment)
            if treatment.animals:
                treatment_data['animal_record'] = treatment.animals.record
            
            return APIResponse.success(
                data=treatment_data,
                message="Información del tratamiento obtenida exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo tratamiento {treatment_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'update_treatment',
        description='Actualizar información de un tratamiento',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Tratamiento actualizado', treatment_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Tratamiento no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(treatment_update_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['treatments_list', 'treatment_detail'])
    @jwt_required()
    def put(self, treatment_id):
        """Actualizar tratamiento"""
        try:
            treatment = Treatments.query.get(treatment_id)
            if not treatment:
                return APIResponse.not_found("Tratamiento")
            
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Actualizar campos
            if 'start_date' in data:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
                if start_date > datetime.now().date():
                    return APIResponse.validation_error(
                        {'start_date': 'La fecha de inicio no puede ser futura'}
                    )
                treatment.start_date = start_date
            
            if 'end_date' in data:
                if data['end_date']:
                    treatment.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
                else:
                    treatment.end_date = None
            
            if 'description' in data:
                treatment.description = data['description']
            
            if 'frequency' in data:
                treatment.frequency = data['frequency']
            
            if 'observations' in data:
                treatment.observations = data['observations']
            
            if 'dosis' in data:
                treatment.dosis = data['dosis']
            
            if 'animal_id' in data:
                animal = Animals.query.get(data['animal_id'])
                if not animal:
                    return APIResponse.not_found("Animal")
                treatment.animal_id = data['animal_id']
            
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Tratamiento actualizado: ID {treatment_id} "
                f"por usuario {user_id}"
            )
            
            # Formatear respuesta
            treatment_data = ResponseFormatter.format_model(treatment)
            if treatment.animals:
                treatment_data['animal_record'] = treatment.animals.record
            
            return APIResponse.success(
                data=treatment_data,
                message="Tratamiento actualizado exitosamente"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad actualizando tratamiento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando tratamiento {treatment_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'delete_treatment',
        description='Eliminar un tratamiento del sistema',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Tratamiento eliminado', success_message_model),
            401: 'Token JWT requerido o inválido',
            404: 'Tratamiento no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @invalidate_cache_on_change(['treatments_list', 'treatment_detail'])
    @jwt_required()
    def delete(self, treatment_id):
        """Eliminar tratamiento"""
        try:
            treatment = Treatments.query.get(treatment_id)
            if not treatment:
                return APIResponse.not_found("Tratamiento")
            
            current_user = get_jwt_identity()
            
            treatment_info = f"{treatment.description} - {treatment.start_date}"
            animal_record = treatment.animals.record if treatment.animals else "N/A"
            
            db.session.delete(treatment)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Tratamiento eliminado: {treatment_info} (Animal: {animal_record}) "
                f"por usuario {user_id}"
            )
            
            return APIResponse.success(
                message="Tratamiento eliminado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad eliminando tratamiento: {str(e)}")
            return APIResponse.conflict(
                message="No se puede eliminar: existen registros relacionados",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando tratamiento {treatment_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE VACUNACIONES
# ============================================================================

@medical_ns.route('/vaccinations')
class VaccinationsList(Resource):
    @medical_ns.doc(
        'get_vaccinations_list',
        description='''
        **Obtener lista de vacunaciones**
        
        Retorna todas las vacunaciones registradas.
        
        **Parámetros opcionales:**
        - `animal_id`: Filtrar por animal específico
        - `vaccine_id`: Filtrar por vacuna específica
        - `instructor_id`: Filtrar por instructor
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'animal_id': {'description': 'Filtrar por ID de animal', 'type': 'integer'},
            'vaccine_id': {'description': 'Filtrar por ID de vacuna', 'type': 'integer'},
            'instructor_id': {'description': 'Filtrar por ID de instructor', 'type': 'integer'},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de vacunaciones', [vaccination_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("vaccinations_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de vacunaciones con filtros y paginación"""
        try:
            # Consulta básica sin filtros complejos
            vaccinations = Vaccinations.query.all()
            
            # Formatear datos básicos
            vaccinations_data = []
            for vaccination in vaccinations:
                try:
                    vaccination_dict = {
                        'id': vaccination.id,
                        'application_date': vaccination.application_date.strftime('%Y-%m-%d') if vaccination.application_date else None,
                        'animal_id': vaccination.animal_id,
                        'vaccine_id': vaccination.vaccine_id,
                        'apprentice_id': vaccination.apprentice_id,
                        'instructor_id': vaccination.instructor_id
                    }
                    vaccinations_data.append(vaccination_dict)
                except Exception as vaccination_error:
                    logger.error(f"Error procesando vacunación {vaccination.id}: {str(vaccination_error)}")
                    continue
            
            return APIResponse.success(
                data=vaccinations_data,
                message=f"Se encontraron {len(vaccinations_data)} vacunaciones"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except Exception as e:
            logger.error(f"Error obteniendo vacunaciones: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'create_vaccination',
        description='''
        **Crear nueva vacunación**
        
        Registra una nueva vacunación para un animal.
        
        **Validaciones:**
        - Animal, vacuna, instructor y aprendiz deben existir
        - Fecha no puede ser futura
        - Dosis es requerida
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Vacunación creada exitosamente', vaccination_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Recurso no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(vaccination_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['application_date', 'animal_id', 'vaccine_id', 'instructor_id'],
        field_types={
            'application_date': str,
            'animal_id': int,
            'vaccine_id': int,
            'apprentice_id': int,
            'instructor_id': int
        }
    )
    @invalidate_cache_on_change(['vaccinations_list'])
    @jwt_required()
    def post(self):
        """Crear nueva vacunación"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que todos los recursos existen
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            vaccine = Vaccines.query.get(data['vaccine_id'])
            if not vaccine:
                return APIResponse.not_found("Vacuna")
            
            instructor = User.query.get(data['instructor_id'])
            if not instructor:
                return APIResponse.not_found("Instructor")
            
            # Validar aprendiz si se proporciona
            apprentice_id = data.get('apprentice_id')
            if apprentice_id:
                apprentice = User.query.get(apprentice_id)
                if not apprentice:
                    return APIResponse.not_found("Aprendiz")
            
            # Validar fecha
            application_date = datetime.strptime(data['application_date'], '%Y-%m-%d').date()
            if application_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'application_date': 'La fecha de vacunación no puede ser futura'}
                )
            
            # Crear nueva vacunación
            new_vaccination = Vaccinations(
                application_date=application_date,
                animal_id=data['animal_id'],
                vaccine_id=data['vaccine_id'],
                apprentice_id=apprentice_id,
                instructor_id=data['instructor_id']
            )
            
            db.session.add(new_vaccination)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Vacunación creada: {vaccine.name} para animal {animal.record} "
                f"por instructor {instructor.fullname} - Usuario: {user_id}"
            )
            
            # Formatear respuesta
            vaccination_data = ResponseFormatter.format_model(new_vaccination)
            vaccination_data.update({
                'animal_record': animal.record,
                'vaccine_name': vaccine.name,
                'instructor_name': instructor.fullname,
                'apprentice_name': apprentice.fullname if apprentice_id and apprentice else None
            })
            
            return APIResponse.created(
                data=vaccination_data,
                message=f"Vacunación registrada exitosamente para {animal.record}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando vacunación: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando vacunación: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE MEDICAMENTOS
# ============================================================================

@medical_ns.route('/medications')
class MedicationsList(Resource):
    @medical_ns.doc(
        'get_medications_list',
        description='Obtener lista de medicamentos disponibles',
        security=['Bearer', 'Cookie'],
        params={
            'name': {'description': 'Filtrar por nombre de medicamento', 'type': 'string'}
        },
        responses={
            200: ('Lista de medicamentos', [medication_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("medications_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de medicamentos"""
        try:
            name_filter = request.args.get('name')
            
            query = Medications.query
            
            if name_filter:
                query = query.filter(Medications.medication.ilike(f"%{name_filter}%"))
            
            medications = query.order_by(Medications.medication).all()
            
            medications_data = ResponseFormatter.format_model_list(medications)
            
            return APIResponse.success(
                data=medications_data,
                message=f"Se encontraron {len(medications)} medicamentos"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo medicamentos: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'create_medication',
        description='Crear nuevo medicamento',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Medicamento creado', medication_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            409: 'El medicamento ya existe',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(medication_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['medications_list'])
    @jwt_required()
    def post(self):
        """Crear nuevo medicamento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que no existe el medicamento
            existing_medication = Medications.query.filter(
                Medications.medication.ilike(data['medication'])
            ).first()
            
            if existing_medication:
                return APIResponse.conflict(
                    message="El medicamento ya existe",
                    details={'medication': data['medication']}
                )
            
            # Crear nuevo medicamento
            new_medication = Medications(
                medication=data['medication'],
                description=data.get('description', '')
            )
            
            db.session.add(new_medication)
            db.session.commit()
            
            logger.info(
                f"Medicamento creado: {new_medication.medication} "
                f"por administrador {current_user.get('identification')}"
            )
            
            medication_data = ResponseFormatter.format_model(new_medication)
            
            return APIResponse.created(
                data=medication_data,
                message=f"Medicamento '{new_medication.medication}' creado exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando medicamento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando medicamento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE VACUNAS
# ============================================================================

@medical_ns.route('/vaccines')
class VaccinesList(Resource):
    @medical_ns.doc(
        'get_vaccines_list',
        description='Obtener lista de vacunas disponibles',
        security=['Bearer', 'Cookie'],
        params={
            'name': {'description': 'Filtrar por nombre de vacuna', 'type': 'string'}
        },
        responses={
            200: ('Lista de vacunas', [vaccine_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("vaccines_list", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener lista de vacunas"""
        try:
            name_filter = request.args.get('name')
            
            query = Vaccines.query
            
            if name_filter:
                query = query.filter(Vaccines.name.ilike(f"%{name_filter}%"))
            
            vaccines = query.order_by(Vaccines.name).all()
            
            vaccines_data = ResponseFormatter.format_model_list(vaccines)
            
            return APIResponse.success(
                data=vaccines_data,
                message=f"Se encontraron {len(vaccines)} vacunas"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo vacunas: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @medical_ns.doc(
        'create_vaccine',
        description='Crear nueva vacuna',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Vacuna creada', vaccine_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            403: 'Se requiere rol de Administrador',
            409: 'La vacuna ya existe',
            500: 'Error interno del servidor'
        }
    )
    @medical_ns.expect(vaccine_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @SecurityValidator.require_admin_role
    @RequestValidator.validate_json_required
    @invalidate_cache_on_change(['vaccines_list'])
    @jwt_required()
    def post(self):
        """Crear nueva vacuna"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que no existe la vacuna
            existing_vaccine = Vaccines.query.filter(
                Vaccines.name.ilike(data['vaccine'])
            ).first()
            
            if existing_vaccine:
                return APIResponse.conflict(
                    message="La vacuna ya existe",
                    details={'vaccine': data['vaccine']}
                )
            
            # Crear nueva vacuna
            new_vaccine = Vaccines(
                name=data['vaccine'],
                dosis=data.get('dosis', '1ml'),
                route_administration=data.get('route_administration', 'Intramuscular'),
                vaccination_interval=data.get('vaccination_interval', '12 meses'),
                vaccine_type=data.get('vaccine_type', 'Inactivada'),
                national_plan=data.get('national_plan', 'Plan Nacional'),
                target_disease_id=data.get('target_disease_id', 1)
            )
            
            db.session.add(new_vaccine)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Vacuna creada: {new_vaccine.name} "
                f"por administrador {user_id}"
            )
            
            vaccine_data = ResponseFormatter.format_model(new_vaccine)
            
            return APIResponse.created(
                data=vaccine_data,
                message=f"Vacuna '{new_vaccine.name}' creada exitosamente"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad creando vacuna: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando vacuna: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )