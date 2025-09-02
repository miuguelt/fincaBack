from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.animalDiseases import AnimalDiseases
from app.models.animalFields import AnimalFields
from app.models.treatment_medications import TreatmentMedications
from app.models.treatment_vaccines import TreatmentVaccines
from app.models.animals import Animals
from app.models.diseases import Diseases
from app.models.fields import Fields
from app.models.treatments import Treatments
from app.models.medications import Medications
from app.models.vaccines import Vaccines
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
relations_ns = Namespace(
    'relations',
    description='🔗 Relaciones y Asociaciones - Vínculos entre Entidades',
    path='/relations'
)

logger = logging.getLogger(__name__)

# Modelos para documentación
animal_disease_input_model = relations_ns.model('AnimalDiseaseInput', {
    'animal_id': fields.Integer(required=True, description='ID del animal', example=1),
    'disease_id': fields.Integer(required=True, description='ID de la enfermedad', example=1),
    'instructor_id': fields.Integer(required=True, description='ID del instructor', example=1),
    'diagnosis_date': fields.Date(required=True, description='Fecha de diagnóstico (YYYY-MM-DD)', example='2023-06-15'),
    'status': fields.Boolean(description='Estado de la enfermedad', example=True, default=False)
})

animal_disease_response_model = relations_ns.model('AnimalDiseaseResponse', {
    'id': fields.Integer(description='ID único de la relación'),
    'animal_id': fields.Integer(description='ID del animal'),
    'disease_id': fields.Integer(description='ID de la enfermedad'),
    'instructor_id': fields.Integer(description='ID del instructor'),
    'diagnosis_date': fields.String(description='Fecha de diagnóstico'),
    'status': fields.Boolean(description='Estado de la enfermedad'),
    'animal_record': fields.String(description='Registro del animal'),
    'disease_name': fields.String(description='Nombre de la enfermedad'),
    'instructor_name': fields.String(description='Nombre del instructor')
})

animal_field_input_model = relations_ns.model('AnimalFieldInput', {
    'animal_id': fields.Integer(required=True, description='ID del animal', example=1),
    'field_id': fields.Integer(required=True, description='ID del campo', example=1),
    'start_date': fields.DateTime(required=True, description='Fecha de inicio de asignación', example='2023-06-15T08:00:00'),
    'end_date': fields.DateTime(description='Fecha de fin de asignación', example='2023-08-15T18:00:00'),
    'duration': fields.String(required=True, description='Duración de la asignación', example='2 meses'),
    'status': fields.Boolean(description='Estado de la asignación', example=True, default=True)
})

animal_field_response_model = relations_ns.model('AnimalFieldResponse', {
    'id': fields.Integer(description='ID único de la asignación'),
    'animal_id': fields.Integer(description='ID del animal'),
    'field_id': fields.Integer(description='ID del campo'),
    'assignment_date': fields.String(description='Fecha de inicio de asignación'),
    'removal_date': fields.String(description='Fecha de fin de asignación'),
    'duration': fields.String(description='Duración de la asignación'),
    'status': fields.Boolean(description='Estado de la asignación'),
    'animal_record': fields.String(description='Registro del animal'),
    'field_name': fields.String(description='Nombre del campo')
})

treatment_medication_input_model = relations_ns.model('TreatmentMedicationInput', {
    'treatment_id': fields.Integer(required=True, description='ID del tratamiento', example=1),
    'medication_id': fields.Integer(required=True, description='ID del medicamento', example=1),
    'dosage': fields.String(required=True, description='Dosis administrada', example='10ml cada 12 horas'),
    'frequency': fields.String(description='Frecuencia de administración', example='Cada 12 horas'),
    'duration_days': fields.Integer(description='Duración en días', example=7),
    'administration_route': fields.String(description='Vía de administración', enum=['Oral', 'Intramuscular', 'Intravenosa', 'Subcutánea', 'Tópica'], example='Intramuscular'),
    'notes': fields.String(description='Notas sobre la administración', example='Administrar con alimento')
})

treatment_medication_response_model = relations_ns.model('TreatmentMedicationResponse', {
    'id': fields.Integer(description='ID único de la relación'),
    'treatment_id': fields.Integer(description='ID del tratamiento'),
    'medication_id': fields.Integer(description='ID del medicamento'),
    'dosage': fields.String(description='Dosis administrada'),
    'frequency': fields.String(description='Frecuencia de administración'),
    'duration_days': fields.Integer(description='Duración en días'),
    'administration_route': fields.String(description='Vía de administración'),
    'notes': fields.String(description='Notas sobre la administración'),
    'treatment_diagnosis': fields.String(description='Diagnóstico del tratamiento'),
    'medication_name': fields.String(description='Nombre del medicamento'),
    'animal_record': fields.String(description='Registro del animal')
})

treatment_vaccine_input_model = relations_ns.model('TreatmentVaccineInput', {
    'treatment_id': fields.Integer(required=True, description='ID del tratamiento', example=1),
    'vaccine_id': fields.Integer(required=True, description='ID de la vacuna', example=1),
    'dose': fields.String(required=True, description='Dosis aplicada', example='5ml'),
    'application_site': fields.String(description='Sitio de aplicación', example='Cuello'),
    'batch_number': fields.String(description='Número de lote', example='VAC-2023-001'),
    'expiry_date': fields.Date(description='Fecha de vencimiento (YYYY-MM-DD)', example='2024-12-31'),
    'notes': fields.String(description='Notas adicionales', example='Sin reacciones adversas')
})

treatment_vaccine_response_model = relations_ns.model('TreatmentVaccineResponse', {
    'id': fields.Integer(description='ID único de la relación'),
    'treatment_id': fields.Integer(description='ID del tratamiento'),
    'vaccine_id': fields.Integer(description='ID de la vacuna'),
    'dose': fields.String(description='Dosis aplicada'),
    'application_site': fields.String(description='Sitio de aplicación'),
    'batch_number': fields.String(description='Número de lote'),
    'expiry_date': fields.String(description='Fecha de vencimiento'),
    'notes': fields.String(description='Notas adicionales'),
    'treatment_diagnosis': fields.String(description='Diagnóstico del tratamiento'),
    'vaccine_name': fields.String(description='Nombre de la vacuna'),
    'animal_record': fields.String(description='Registro del animal')
})

success_message_model = relations_ns.model('SuccessMessage', {
    'message': fields.String(description='Mensaje de éxito')
})

# ============================================================================
# ENDPOINTS DE ANIMAL-ENFERMEDADES
# ============================================================================

@relations_ns.route('/animal-diseases')
class AnimalDiseasesList(Resource):
    @relations_ns.doc(
        'get_animal_diseases_list',
        description='''
        **Obtener lista de enfermedades por animal**
        
        Retorna todas las relaciones entre animales y enfermedades.
        
        **Parámetros opcionales:**
        - `animal_id`: Filtrar por animal específico
        - `disease_id`: Filtrar por enfermedad específica
        - `status`: Filtrar por estado del tratamiento
        - `severity`: Filtrar por severidad
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        
        **Casos de uso:**
        - Historial de enfermedades por animal
        - Reportes epidemiológicos
        - Seguimiento de tratamientos
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'animal_id': {'description': 'Filtrar por ID de animal', 'type': 'integer'},
            'disease_id': {'description': 'Filtrar por ID de enfermedad', 'type': 'integer'},
            'status': {'description': 'Filtrar por estado', 'type': 'string', 'enum': ['Activo', 'En tratamiento', 'Recuperado', 'Crónico']},
            'severity': {'description': 'Filtrar por severidad', 'type': 'string', 'enum': ['Leve', 'Moderada', 'Severa', 'Crítica']},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de enfermedades por animal', [animal_disease_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("animal_diseases_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de enfermedades por animal con filtros y paginación"""
        try:
            # Consulta simplificada sin filtros complejos
            animal_diseases = AnimalDiseases.query.all()
            
            # Formatear datos básicos
            animal_diseases_data = []
            for animal_disease in animal_diseases:
                try:
                    disease_dict = {
                        'id': animal_disease.id,
                        'animal_id': animal_disease.animal_id,
                        'disease_id': animal_disease.disease_id,
                        'instructor_id': animal_disease.instructor_id,
                        'diagnosis_date': animal_disease.diagnosis_date.strftime('%Y-%m-%d') if animal_disease.diagnosis_date else None,
                        'status': animal_disease.status,
                        'animal_record': animal_disease.animals.record if animal_disease.animals else None,
                        'disease_name': animal_disease.diseases.name if animal_disease.diseases else None,
                        'instructor_name': animal_disease.instructors.fullname if animal_disease.instructors else None
                    }
                    animal_diseases_data.append(disease_dict)
                except Exception as item_error:
                    logger.error(f"Error procesando enfermedad {animal_disease.id}: {str(item_error)}")
                    continue
            
            return APIResponse.success(
                data=animal_diseases_data,
                message=f"Se encontraron {len(animal_diseases_data)} registros de enfermedades"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except Exception as e:
            logger.error(f"Error obteniendo enfermedades por animal: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @relations_ns.doc(
        'create_animal_disease',
        description='''
        **Registrar enfermedad en animal**
        
        Asocia una enfermedad con un animal específico.
        
        **Validaciones:**
        - Animal y enfermedad deben existir
        - Fecha de diagnóstico no puede ser futura
        - No se puede duplicar la misma enfermedad activa en el mismo animal
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Enfermedad registrada exitosamente', animal_disease_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Recurso no encontrado',
            409: 'La enfermedad ya está registrada para este animal',
            500: 'Error interno del servidor'
        }
    )
    @relations_ns.expect(animal_disease_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['animal_id', 'disease_id', 'diagnosis_date'],
        field_types={
            'animal_id': int,
            'disease_id': int
        }
    )
    @invalidate_cache_on_change(['animal_diseases_list'])
    @jwt_required()
    def post(self):
        """Registrar enfermedad en animal"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el animal existe
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            # Verificar que la enfermedad existe
            disease = Diseases.query.get(data['disease_id'])
            if not disease:
                return APIResponse.not_found("Enfermedad")
            
            # Validar fecha
            diagnosis_date = datetime.strptime(data['diagnosis_date'], '%Y-%m-%d').date()
            if diagnosis_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'diagnosis_date': 'La fecha de diagnóstico no puede ser futura'}
                )
            
            # Verificar que no existe una enfermedad activa del mismo tipo
            existing_disease = AnimalDiseases.query.filter(
                AnimalDiseases.animal_id == data['animal_id'],
                AnimalDiseases.disease_id == data['disease_id'],
                AnimalDiseases.status.in_(['Activo', 'En tratamiento'])
            ).first()
            
            if existing_disease:
                return APIResponse.conflict(
                    message="La enfermedad ya está registrada como activa para este animal",
                    details={
                        'animal_record': animal.record,
                        'disease_name': disease.disease,
                        'current_status': existing_disease.status
                    }
                )
            
            # Crear nueva relación animal-enfermedad
            new_animal_disease = AnimalDiseases(
                animal_id=data['animal_id'],
                disease_id=data['disease_id'],
                diagnosis_date=diagnosis_date,
                severity=data.get('severity', 'Moderada'),
                status=data.get('status', 'Activo'),
                notes=data.get('notes', '')
            )
            
            db.session.add(new_animal_disease)
            db.session.commit()
            
            logger.info(
                f"Enfermedad registrada: {disease.disease} en animal {animal.record} "
                f"por usuario {current_user.get('identification')}"
            )
            
            # Formatear respuesta
            disease_data = ResponseFormatter.format_model(new_animal_disease)
            disease_data.update({
                'animal_record': animal.record,
                'disease_name': disease.disease
            })
            
            return APIResponse.created(
                data=disease_data,
                message=f"Enfermedad '{disease.disease}' registrada para {animal.record}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad registrando enfermedad: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registrando enfermedad: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE ANIMAL-CAMPOS
# ============================================================================

@relations_ns.route('/animal-fields')
class AnimalFieldsList(Resource):
    @relations_ns.doc(
        'get_animal_fields_list',
        description='''
        **Obtener lista de asignaciones animal-campo**
        
        Retorna todas las asignaciones de animales a campos.
        
        **Parámetros opcionales:**
        - `animal_id`: Filtrar por animal específico
        - `field_id`: Filtrar por campo específico
        - `active_only`: Solo asignaciones activas (sin fecha de remoción)
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        
        **Casos de uso:**
        - Gestión de pastoreo
        - Rotación de campos
        - Ocupación de potreros
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'animal_id': {'description': 'Filtrar por ID de animal', 'type': 'integer'},
            'field_id': {'description': 'Filtrar por ID de campo', 'type': 'integer'},
            'active_only': {'description': 'Solo asignaciones activas', 'type': 'boolean'},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de asignaciones animal-campo', [animal_field_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("animal_fields_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de asignaciones animal-campo"""
        try:
            # Consulta simplificada sin filtros complejos
            animal_fields = AnimalFields.query.all()
            
            # Formatear datos básicos
            animal_fields_data = []
            for animal_field in animal_fields:
                try:
                    field_dict = {
                        'id': animal_field.id,
                        'animal_id': animal_field.animal_id,
                        'field_id': animal_field.field_id,
                        'assignment_date': animal_field.start_date.strftime('%Y-%m-%d') if animal_field.start_date else None,
                        'removal_date': animal_field.end_date.strftime('%Y-%m-%d') if animal_field.end_date else None,
                        'duration': animal_field.duration,
                        'status': animal_field.status,
                        'animal_record': animal_field.animals.record if animal_field.animals else None,
                        'field_name': animal_field.fields.name if animal_field.fields else None
                    }
                    animal_fields_data.append(field_dict)
                except Exception as item_error:
                    logger.error(f"Error procesando asignación {animal_field.id}: {str(item_error)}")
                    continue
            
            return APIResponse.success(
                data=animal_fields_data,
                message=f"Se encontraron {len(animal_fields_data)} asignaciones animal-campo"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except Exception as e:
            logger.error(f"Error obteniendo asignaciones animal-campo: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @relations_ns.doc(
        'create_animal_field',
        description='''
        **Asignar animal a campo**
        
        Asigna un animal a un campo específico.
        
        **Validaciones:**
        - Animal y campo deben existir
        - Fecha de asignación no puede ser futura
        - No se puede asignar un animal que ya está activo en otro campo
        - El campo debe tener capacidad disponible
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Animal asignado exitosamente', animal_field_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Recurso no encontrado',
            409: 'Conflicto de asignación',
            500: 'Error interno del servidor'
        }
    )
    @relations_ns.expect(animal_field_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['animal_id', 'field_id', 'assignment_date'],
        field_types={
            'animal_id': int,
            'field_id': int
        }
    )
    @invalidate_cache_on_change(['animal_fields_list'])
    @jwt_required()
    def post(self):
        """Asignar animal a campo"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el animal existe
            animal = Animals.query.get(data['animal_id'])
            if not animal:
                return APIResponse.not_found("Animal")
            
            # Verificar que el campo existe
            field = Fields.query.get(data['field_id'])
            if not field:
                return APIResponse.not_found("Campo")
            
            # Validar fecha
            assignment_date = datetime.strptime(data['assignment_date'], '%Y-%m-%d').date()
            if assignment_date > datetime.now().date():
                return APIResponse.validation_error(
                    {'assignment_date': 'La fecha de asignación no puede ser futura'}
                )
            
            # Verificar que el animal no está asignado activamente a otro campo
            active_assignment = AnimalFields.query.filter(
                AnimalFields.animal_id == data['animal_id'],
                AnimalFields.removal_date.is_(None)
            ).first()
            
            if active_assignment:
                current_field = Fields.query.get(active_assignment.field_id)
                return APIResponse.conflict(
                    message="El animal ya está asignado a otro campo",
                    details={
                        'animal_record': animal.record,
                        'current_field': current_field.field if current_field else "Campo desconocido",
                        'assignment_date': active_assignment.assignment_date.isoformat()
                    }
                )
            
            # Verificar capacidad del campo (si está definida)
            if field.capacity:
                current_animals = AnimalFields.query.filter(
                    AnimalFields.field_id == data['field_id'],
                    AnimalFields.removal_date.is_(None)
                ).count()
                
                if current_animals >= field.capacity:
                    return APIResponse.conflict(
                        message="El campo ha alcanzado su capacidad máxima",
                        details={
                            'field_name': field.field,
                            'capacity': field.capacity,
                            'current_animals': current_animals
                        }
                    )
            
            # Validar fecha de remoción si se proporciona
            removal_date = None
            if 'removal_date' in data and data['removal_date']:
                removal_date = datetime.strptime(data['removal_date'], '%Y-%m-%d').date()
                if removal_date <= assignment_date:
                    return APIResponse.validation_error(
                        {'removal_date': 'La fecha de remoción debe ser posterior a la fecha de asignación'}
                    )
            
            # Crear nueva asignación
            new_assignment = AnimalFields(
                animal_id=data['animal_id'],
                field_id=data['field_id'],
                assignment_date=assignment_date,
                removal_date=removal_date,
                reason=data.get('reason', ''),
                notes=data.get('notes', '')
            )
            
            db.session.add(new_assignment)
            db.session.commit()
            
            logger.info(
                f"Animal asignado: {animal.record} a campo {field.field} "
                f"por usuario {current_user.get('identification')}"
            )
            
            # Formatear respuesta
            assignment_data = ResponseFormatter.format_model(new_assignment)
            assignment_data.update({
                'animal_record': animal.record,
                'field_name': field.field,
                'is_active': removal_date is None
            })
            
            return APIResponse.created(
                data=assignment_data,
                message=f"Animal {animal.record} asignado a {field.field}"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad asignando animal: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error asignando animal: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE TRATAMIENTO-MEDICAMENTOS
# ============================================================================

@relations_ns.route('/treatment-medications')
class TreatmentMedicationsList(Resource):
    @relations_ns.doc(
        'get_treatment_medications_list',
        description='''
        **Obtener lista de medicamentos por tratamiento**
        
        Retorna todos los medicamentos asociados a tratamientos.
        
        **Parámetros opcionales:**
        - `treatment_id`: Filtrar por tratamiento específico
        - `medication_id`: Filtrar por medicamento específico
        - `administration_route`: Filtrar por vía de administración
        - `page`: Número de página (default: 1)
        - `per_page`: Elementos por página (default: 20)
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'treatment_id': {'description': 'Filtrar por ID de tratamiento', 'type': 'integer'},
            'medication_id': {'description': 'Filtrar por ID de medicamento', 'type': 'integer'},
            'administration_route': {'description': 'Filtrar por vía de administración', 'type': 'string', 'enum': ['Oral', 'Intramuscular', 'Intravenosa', 'Subcutánea', 'Tópica']},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de medicamentos por tratamiento', [treatment_medication_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("treatment_medications_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de medicamentos por tratamiento"""
        try:
            # Obtener parámetros
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            treatment_id = request.args.get('treatment_id')
            medication_id = request.args.get('medication_id')
            administration_route = request.args.get('administration_route')
            
            # Construir consulta con joins
            query = db.session.query(TreatmentMedications).join(Treatments).join(Medications)
            
            # Aplicar filtros
            if treatment_id:
                query = query.filter(TreatmentMedications.treatment_id == treatment_id)
            
            if medication_id:
                query = query.filter(TreatmentMedications.medication_id == medication_id)
            
            if administration_route:
                query = query.filter(TreatmentMedications.administration_route == administration_route)
            
            # Aplicar paginación
            treatment_medications, total, page, per_page = QueryOptimizer.optimize_pagination(
                query.order_by(TreatmentMedications.id.desc()), page, per_page
            )
            
            # Formatear datos con información relacionada
            treatment_medications_data = []
            for tm in treatment_medications:
                tm_dict = ResponseFormatter.format_model(tm)
                
                # Agregar información relacionada
                if tm.treatment:
                    tm_dict['treatment_diagnosis'] = tm.treatment.diagnosis
                    if tm.treatment.animal:
                        tm_dict['animal_record'] = tm.treatment.animal.record
                
                if tm.medication:
                    tm_dict['medication_name'] = tm.medication.medication
                
                treatment_medications_data.append(tm_dict)
            
            return APIResponse.paginated_success(
                data=treatment_medications_data,
                page=page,
                per_page=per_page,
                total=total,
                message=f"Se encontraron {total} medicamentos en tratamientos"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo medicamentos por tratamiento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @relations_ns.doc(
        'create_treatment_medication',
        description='''
        **Asociar medicamento a tratamiento**
        
        Asocia un medicamento específico con un tratamiento.
        
        **Validaciones:**
        - Tratamiento y medicamento deben existir
        - Dosis y frecuencia son requeridas
        - Duración debe ser positiva
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Medicamento asociado exitosamente', treatment_medication_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Recurso no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @relations_ns.expect(treatment_medication_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['treatment_id', 'medication_id', 'dosage'],
        field_types={
            'treatment_id': int,
            'medication_id': int,
            'dosage': str
        }
    )
    @invalidate_cache_on_change(['treatment_medications_list'])
    @jwt_required()
    def post(self):
        """Asociar medicamento a tratamiento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el tratamiento existe
            treatment = Treatments.query.get(data['treatment_id'])
            if not treatment:
                return APIResponse.not_found("Tratamiento")
            
            # Verificar que el medicamento existe
            medication = Medications.query.get(data['medication_id'])
            if not medication:
                return APIResponse.not_found("Medicamento")
            
            # Validar duración si se proporciona
            if 'duration_days' in data and data['duration_days'] <= 0:
                return APIResponse.validation_error(
                    {'duration_days': 'La duración debe ser mayor a 0'}
                )
            
            # Crear nueva asociación
            new_tm = TreatmentMedications(
                treatment_id=data['treatment_id'],
                medication_id=data['medication_id'],
                dosage=data['dosage'],
                frequency=data.get('frequency', ''),
                duration_days=data.get('duration_days'),
                administration_route=data.get('administration_route', 'Oral'),
                notes=data.get('notes', '')
            )
            
            db.session.add(new_tm)
            db.session.commit()
            
            logger.info(
                f"Medicamento asociado: {medication.medication} a tratamiento {treatment.diagnosis} "
                f"por usuario {current_user.get('identification')}"
            )
            
            # Formatear respuesta
            tm_data = ResponseFormatter.format_model(new_tm)
            tm_data.update({
                'treatment_diagnosis': treatment.diagnosis,
                'medication_name': medication.medication,
                'animal_record': treatment.animal.record if treatment.animal else None
            })
            
            return APIResponse.created(
                data=tm_data,
                message=f"Medicamento '{medication.medication}' asociado al tratamiento"
            )
            
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad asociando medicamento: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error asociando medicamento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

# ============================================================================
# ENDPOINTS DE TRATAMIENTO-VACUNAS
# ============================================================================

@relations_ns.route('/treatment-vaccines')
class TreatmentVaccinesList(Resource):
    @relations_ns.doc(
        'get_treatment_vaccines_list',
        description='Obtener lista de vacunas por tratamiento',
        security=['Bearer', 'Cookie'],
        params={
            'treatment_id': {'description': 'Filtrar por ID de tratamiento', 'type': 'integer'},
            'vaccine_id': {'description': 'Filtrar por ID de vacuna', 'type': 'integer'},
            'page': {'description': 'Número de página', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Elementos por página', 'type': 'integer', 'default': 20}
        },
        responses={
            200: ('Lista de vacunas por tratamiento', [treatment_vaccine_response_model]),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("treatment_vaccines_list", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener lista de vacunas por tratamiento"""
        try:
            # Obtener parámetros
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            treatment_id = request.args.get('treatment_id')
            vaccine_id = request.args.get('vaccine_id')
            
            # Construir consulta con joins
            query = db.session.query(TreatmentVaccines).join(Treatments).join(Vaccines)
            
            # Aplicar filtros
            if treatment_id:
                query = query.filter(TreatmentVaccines.treatment_id == treatment_id)
            
            if vaccine_id:
                query = query.filter(TreatmentVaccines.vaccine_id == vaccine_id)
            
            # Aplicar paginación
            treatment_vaccines, total, page, per_page = QueryOptimizer.optimize_pagination(
                query.order_by(TreatmentVaccines.id.desc()), page, per_page
            )
            
            # Formatear datos con información relacionada
            treatment_vaccines_data = []
            for tv in treatment_vaccines:
                tv_dict = ResponseFormatter.format_model(tv)
                
                # Agregar información relacionada
                if tv.treatment:
                    tv_dict['treatment_diagnosis'] = tv.treatment.diagnosis
                    if tv.treatment.animal:
                        tv_dict['animal_record'] = tv.treatment.animal.record
                
                if tv.vaccine:
                    tv_dict['vaccine_name'] = tv.vaccine.name
                
                treatment_vaccines_data.append(tv_dict)
            
            return APIResponse.paginated_success(
                data=treatment_vaccines_data,
                page=page,
                per_page=per_page,
                total=total,
                message=f"Se encontraron {total} vacunas en tratamientos"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo vacunas por tratamiento: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    @relations_ns.doc(
        'create_treatment_vaccine',
        description='Asociar vacuna a tratamiento',
        security=['Bearer', 'Cookie'],
        responses={
            201: ('Vacuna asociada exitosamente', treatment_vaccine_response_model),
            400: 'Datos inválidos',
            401: 'Token JWT requerido o inválido',
            404: 'Recurso no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @relations_ns.expect(treatment_vaccine_input_model, validate=True)
    @PerformanceLogger.log_request_performance
    @RequestValidator.validate_json_required
    @RequestValidator.validate_fields(
        required_fields=['treatment_id', 'vaccine_id', 'dose'],
        field_types={
            'treatment_id': int,
            'vaccine_id': int,
            'dose': str
        }
    )
    @invalidate_cache_on_change(['treatment_vaccines_list'])
    @jwt_required()
    def post(self):
        """Asociar vacuna a tratamiento"""
        try:
            data = request.get_json()
            current_user = get_jwt_identity()
            
            # Verificar que el tratamiento existe
            treatment = Treatments.query.get(data['treatment_id'])
            if not treatment:
                return APIResponse.not_found("Tratamiento")
            
            # Verificar que la vacuna existe
            vaccine = Vaccines.query.get(data['vaccine_id'])
            if not vaccine:
                return APIResponse.not_found("Vacuna")
            
            # Validar fecha de vencimiento si se proporciona
            expiry_date = None
            if 'expiry_date' in data and data['expiry_date']:
                expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
                if expiry_date <= datetime.now().date():
                    return APIResponse.validation_error(
                        {'expiry_date': 'La fecha de vencimiento debe ser futura'}
                    )
            
            # Crear nueva asociación
            new_tv = TreatmentVaccines(
                treatment_id=data['treatment_id'],
                vaccine_id=data['vaccine_id'],
                dose=data['dose'],
                application_site=data.get('application_site', ''),
                batch_number=data.get('batch_number', ''),
                expiry_date=expiry_date,
                notes=data.get('notes', '')
            )
            
            db.session.add(new_tv)
            db.session.commit()
            
            user_id = current_user.get('identification') if isinstance(current_user, dict) else current_user
            logger.info(
                f"Vacuna asociada: {vaccine.name} a tratamiento {treatment.description} "
                f"por usuario {user_id}"
            )
            
            # Formatear respuesta
            tv_data = ResponseFormatter.format_model(new_tv)
            tv_data.update({
                'treatment_description': treatment.description,
                'vaccine_name': vaccine.name,
                'animal_record': treatment.animal.record if treatment.animal else None
            })
            
            return APIResponse.created(
                data=tv_data,
                message=f"Vacuna '{vaccine.name}' asociada al tratamiento"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.warning(f"Error de integridad asociando vacuna: {str(e)}")
            return APIResponse.conflict(
                message="Error de integridad en los datos",
                details={'database_error': str(e)}
            )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error asociando vacuna: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )