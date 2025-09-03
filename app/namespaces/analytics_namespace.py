from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.animals import Animals, Sex, AnimalStatus
from app.models.user import User, Role
from app.models.treatments import Treatments
from app.models.vaccinations import Vaccinations
from app.models.control import Control, HealthStatus
# HealtStatus es ahora un alias de HealthStatus para compatibilidad
from app.models.breeds import Breeds
from app.models.species import Species
from app.models.diseases import Diseases
from app.models.medications import Medications
from app.models.vaccines import Vaccines
from app import db
from sqlalchemy import func, extract, desc, asc
from datetime import datetime, timedelta
import logging

# Importar utilidades de optimización
from app.utils.response_handler import APIResponse, ResponseFormatter
from app.utils.validators import PerformanceLogger, SecurityValidator
from app.utils.cache_manager import cache_query_result

# Crear el namespace
analytics_ns = Namespace(
    'analytics',
    description='📊 Analytics y Dashboard - Sistema de Gestión Integral',
    path='/analytics'
)

logger = logging.getLogger(__name__)

# Modelos para respuestas
dashboard_stats_model = analytics_ns.model('DashboardStats', {
    'total_animals': fields.Integer(description='Total de animales'),
    'active_animals': fields.Integer(description='Animales activos (vivos)'),
    'total_treatments': fields.Integer(description='Total de tratamientos'),
    'total_vaccinations': fields.Integer(description='Total de vacunaciones'),
    'total_users': fields.Integer(description='Total de usuarios'),
    'recent_activities': fields.List(fields.Raw(), description='Actividades recientes')
})

animal_stats_model = analytics_ns.model('AnimalStats', {
    'by_status': fields.Raw(description='Estadísticas por estado'),
    'by_sex': fields.Raw(description='Estadísticas por sexo'),
    'by_breed': fields.Raw(description='Estadísticas por raza'),
    'by_age_group': fields.Raw(description='Estadísticas por grupo de edad'),
    'weight_distribution': fields.Raw(description='Distribución de pesos')
})

health_stats_model = analytics_ns.model('HealthStats', {
    'treatments_by_month': fields.Raw(description='Tratamientos por mes'),
    'vaccinations_by_month': fields.Raw(description='Vacunaciones por mes'),
    'health_status_distribution': fields.Raw(description='Distribución de estados de salud'),
    'common_diseases': fields.Raw(description='Enfermedades más comunes'),
    'medication_usage': fields.Raw(description='Uso de medicamentos')
})

production_stats_model = analytics_ns.model('ProductionStats', {
    'weight_trends': fields.Raw(description='Tendencias de peso'),
    'growth_rates': fields.Raw(description='Tasas de crecimiento'),
    'productivity_metrics': fields.Raw(description='Métricas de productividad')
})

@analytics_ns.route('/dashboard')
class DashboardStats(Resource):
    @analytics_ns.doc(
        'get_dashboard_stats',
        description='''
        **Estadísticas principales del dashboard**
        
        Retorna un resumen completo de las métricas clave del sistema:
        - Total de animales y distribución por estado
        - Actividad médica (tratamientos y vacunaciones)
        - Usuarios del sistema
        - Actividades recientes
        
        **Casos de uso:**
        - Dashboard principal de la aplicación
        - Vista general del estado de la finca
        - Métricas para toma de decisiones
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Estadísticas del dashboard', dashboard_stats_model),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("dashboard_stats", ttl_seconds=300)
    @jwt_required()
    def get(self):
        """Obtener estadísticas principales del dashboard"""
        try:
            # Usar métodos optimizados de estadísticas de todos los modelos
            animals_stats = Animals.get_statistics_for_namespace()
            treatments_stats = Treatments.get_statistics_for_namespace()
            vaccinations_stats = Vaccinations.get_statistics_for_namespace()
            control_stats = Control.get_statistics_for_namespace()
            users_stats = User.get_statistics_for_namespace()
            
            # Consolidar estadísticas del dashboard
            dashboard_data = {
                'total_animals': animals_stats.get('total_animals', 0),
                'active_animals': animals_stats.get('status_distribution', {}).get('Vivo', {}).get('count', 0),
                'sold_animals': animals_stats.get('status_distribution', {}).get('Vendido', {}).get('count', 0),
                'deceased_animals': animals_stats.get('status_distribution', {}).get('Muerto', {}).get('count', 0),
                'total_treatments': treatments_stats.get('total_treatments', 0),
                'total_vaccinations': vaccinations_stats.get('total_vaccinations', 0),
                'total_controls': control_stats.get('total_controls', 0),
                'total_users': users_stats.get('total_users', 0),
                'active_users': users_stats.get('active_users', 0),
                'animals_by_status': animals_stats.get('status_distribution', {}),
                'animals_by_sex': animals_stats.get('sex_distribution', {}),
                'health_summary': control_stats.get('health_distribution', {}),
                'recent_treatments_week': treatments_stats.get('recent_week_count', 0),
                'recent_vaccinations_week': vaccinations_stats.get('recent_week_count', 0),
                'monthly_activity': {
                    'treatments': treatments_stats.get('monthly_treatments', {}),
                    'vaccinations': vaccinations_stats.get('monthly_vaccinations', {}),
                    'controls': control_stats.get('monthly_controls', {})
                },
                'alerts': {
                    'mortality_rate': animals_stats.get('summary', {}).get('mortality_rate', 0),
                    'animals_needing_attention': control_stats.get('animals_needing_attention', 0)
                },
                'productivity_summary': {
                    'average_weight': animals_stats.get('average_weight', 0),
                    'weight_trends': animals_stats.get('weight_trends', {})
                }
            }
            
            return APIResponse.success(
                data=dashboard_data,
                message="Estadísticas del dashboard obtenidas exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del dashboard: {str(e)}")
            return APIResponse.error(
                 message="Error interno del servidor",
                 status_code=500,
                 details={'error': str(e)}
             )

@analytics_ns.route('/alerts')
class SystemAlerts(Resource):
    @analytics_ns.doc(
        'get_system_alerts',
        description='''
        **Sistema de alertas y notificaciones automáticas**
        
        Genera alertas inteligentes basadas en el estado del hato:
        - Animales que requieren atención médica
        - Controles de salud vencidos
        - Vacunaciones pendientes
        - Anomalías en el crecimiento
        - Alertas de productividad
        
        **Parámetros opcionales:**
        - `priority`: Filtrar por prioridad (high, medium, low)
        - `type`: Tipo de alerta (health, vaccination, growth, productivity)
        - `limit`: Número máximo de alertas (default: 50)
        
        **Útil para:**
        - Dashboard de alertas
        - Notificaciones push
        - Planificación de actividades
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'priority': {'description': 'Filtrar por prioridad', 'type': 'string', 'enum': ['high', 'medium', 'low']},
            'type': {'description': 'Tipo de alerta', 'type': 'string', 'enum': ['health', 'vaccination', 'growth', 'productivity']},
            'limit': {'description': 'Número máximo de alertas', 'type': 'integer', 'default': 50}
        },
        responses={
            200: 'Lista de alertas del sistema',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("system_alerts", ttl_seconds=300)
    @jwt_required()
    def get(self):
        """Obtener alertas y notificaciones del sistema"""
        try:
            priority_filter = request.args.get('priority')
            type_filter = request.args.get('type')
            limit = int(request.args.get('limit', 50))
            
            alerts = []
            current_date = datetime.now().date()
            
            # 1. Alertas de salud - Animales sin control reciente
            if not type_filter or type_filter == 'health':
                thirty_days_ago = current_date - timedelta(days=30)
                
                animals_without_control = db.session.query(
                    Animals.id,
                    Animals.record,
                    func.max(Control.control_date).label('last_control')
                ).outerjoin(Control).filter(
                    Animals.status == AnimalStatus.Vivo
                ).group_by(
                    Animals.id, Animals.record
                ).having(
                    func.coalesce(func.max(Control.control_date), '1900-01-01') < thirty_days_ago
                ).all()
                
                for animal in animals_without_control:
                    days_without_control = (current_date - (animal.last_control or datetime(1900, 1, 1).date())).days
                    
                    priority = 'high' if days_without_control > 60 else 'medium'
                    
                    alerts.append({
                        'id': f'health_{animal.id}',
                        'type': 'health',
                        'priority': priority,
                        'title': f'Control vencido - {animal.record}',
                        'message': f'Animal sin control hace {days_without_control} días',
                        'animal_id': animal.id,
                        'animal_record': animal.record,
                        'action_required': 'Programar control de salud',
                        'created_at': current_date.isoformat(),
                        'icon': '⚠️',
                        'color': 'orange' if priority == 'medium' else 'red'
                    })
            
            # 2. Alertas de estado de salud crítico
            if not type_filter or type_filter == 'health':
                critical_health = db.session.query(
                    Animals.id,
                    Animals.record,
                    Control.healt_status,
                    Control.control_date
                ).join(Control).filter(
                    Animals.status == AnimalStatus.Vivo,
                    Control.healt_status.in_([HealthStatus.Malo, HealthStatus.Regular]),
                    Control.control_date >= current_date - timedelta(days=30)
                ).order_by(desc(Control.control_date)).all()
                
                for animal in critical_health:
                    priority = 'high' if animal.healt_status == HealthStatus.Malo else 'medium'
                    
                    alerts.append({
                        'id': f'critical_health_{animal.id}',
                        'type': 'health',
                        'priority': priority,
                        'title': f'Estado crítico - {animal.record}',
                        'message': f'Estado de salud: {animal.healt_status.value}',
                        'animal_id': animal.id,
                        'animal_record': animal.record,
                        'action_required': 'Evaluación veterinaria urgente',
                        'created_at': animal.control_date.isoformat(),
                        'icon': '🚨',
                        'color': 'red'
                    })
            
            # 3. Alertas de vacunación - Animales que necesitan vacunas
            if not type_filter or type_filter == 'vaccination':
                # Animales sin vacunación reciente (más de 6 meses)
                six_months_ago = current_date - timedelta(days=180)
                
                animals_need_vaccination = db.session.query(
                    Animals.id,
                    Animals.record,
                    func.max(Vaccinations.application_date).label('last_vaccination')
                ).outerjoin(Vaccinations).filter(
                    Animals.status == AnimalStatus.Vivo
                ).group_by(
                    Animals.id, Animals.record
                ).having(
                    func.coalesce(func.max(Vaccinations.application_date), '1900-01-01') < six_months_ago
                ).all()
                
                for animal in animals_need_vaccination:
                    days_without_vaccination = (current_date - (animal.last_vaccination or datetime(1900, 1, 1).date())).days
                    
                    alerts.append({
                        'id': f'vaccination_{animal.id}',
                        'type': 'vaccination',
                        'priority': 'medium',
                        'title': f'Vacunación pendiente - {animal.record}',
                        'message': f'Sin vacunación hace {days_without_vaccination} días',
                        'animal_id': animal.id,
                        'animal_record': animal.record,
                        'action_required': 'Programar vacunación',
                        'created_at': current_date.isoformat(),
                        'icon': '💉',
                        'color': 'yellow'
                    })
            
            # 4. Alertas de crecimiento - Animales con crecimiento anómalo
            if not type_filter or type_filter == 'growth':
                # Animales con pérdida de peso reciente
                recent_controls = db.session.query(
                    Animals.id,
                    Animals.record,
                    Control.weight,
                    Control.control_date,
                    func.lag(Control.weight).over(
                        partition_by=Animals.id,
                        order_by=Control.control_date
                    ).label('previous_weight')
                ).join(Control).filter(
                    Animals.status == AnimalStatus.Vivo,
                    Control.control_date >= current_date - timedelta(days=90)
                ).subquery()
                
                weight_loss_animals = db.session.query(
                    recent_controls.c.id,
                    recent_controls.c.record,
                    recent_controls.c.weight,
                    recent_controls.c.previous_weight,
                    recent_controls.c.control_date
                ).filter(
                    recent_controls.c.previous_weight.isnot(None),
                    recent_controls.c.weight < recent_controls.c.previous_weight * 0.95  # Pérdida > 5%
                ).all()
                
                for animal in weight_loss_animals:
                    weight_loss = animal.previous_weight - animal.weight
                    loss_percentage = (weight_loss / animal.previous_weight) * 100
                    
                    alerts.append({
                        'id': f'weight_loss_{animal.id}',
                        'type': 'growth',
                        'priority': 'high',
                        'title': f'Pérdida de peso - {animal.record}',
                        'message': f'Perdió {weight_loss:.1f}kg ({loss_percentage:.1f}%)',
                        'animal_id': animal.id,
                        'animal_record': animal.record,
                        'action_required': 'Revisar alimentación y salud',
                        'created_at': animal.control_date.isoformat(),
                        'icon': '📉',
                        'color': 'red'
                    })
            
            # 5. Alertas de productividad - Rendimiento bajo del hato
            if not type_filter or type_filter == 'productivity':
                # Calcular promedio de ganancia diaria del último mes
                last_month = current_date - timedelta(days=30)
                
                avg_daily_gain = db.session.query(
                    func.avg(
                        (Control.weight - func.lag(Control.weight).over(
                            partition_by=Animals.id,
                            order_by=Control.control_date
                        )) / 
                        func.extract('days', 
                            Control.control_date - func.lag(Control.control_date).over(
                                partition_by=Animals.id,
                                order_by=Control.control_date
                            )
                        )
                    ).label('daily_gain')
                ).join(Animals).filter(
                    Animals.status == AnimalStatus.Vivo,
                    Control.control_date >= last_month
                ).scalar()
                
                if avg_daily_gain and avg_daily_gain < 0.5:  # Menos de 500g diarios
                    alerts.append({
                        'id': 'low_productivity',
                        'type': 'productivity',
                        'priority': 'medium',
                        'title': 'Productividad baja del hato',
                        'message': f'Ganancia diaria promedio: {avg_daily_gain:.3f}kg',
                        'action_required': 'Revisar programa nutricional',
                        'created_at': current_date.isoformat(),
                        'icon': '📊',
                        'color': 'orange'
                    })
            
            # Filtrar por prioridad si se especifica
            if priority_filter:
                alerts = [alert for alert in alerts if alert['priority'] == priority_filter]
            
            # Ordenar por prioridad y fecha
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            alerts.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['created_at']), reverse=True)
            
            # Limitar resultados
            alerts = alerts[:limit]
            
            # Estadísticas de alertas
            alert_stats = {
                'total': len(alerts),
                'by_priority': {
                    'high': len([a for a in alerts if a['priority'] == 'high']),
                    'medium': len([a for a in alerts if a['priority'] == 'medium']),
                    'low': len([a for a in alerts if a['priority'] == 'low'])
                },
                'by_type': {
                    'health': len([a for a in alerts if a['type'] == 'health']),
                    'vaccination': len([a for a in alerts if a['type'] == 'vaccination']),
                    'growth': len([a for a in alerts if a['type'] == 'growth']),
                    'productivity': len([a for a in alerts if a['type'] == 'productivity'])
                }
            }
            
            return APIResponse.success(
                data={
                    'alerts': alerts,
                    'statistics': alert_stats,
                    'generated_at': current_date.isoformat(),
                    'filters_applied': {
                        'priority': priority_filter,
                        'type': type_filter,
                        'limit': limit
                    }
                },
                message=f"Se generaron {len(alerts)} alertas del sistema"
            )
            
        except Exception as e:
            logger.error(f"Error generando alertas del sistema: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@analytics_ns.route('/reports/custom')
class CustomReports(Resource):
    @analytics_ns.doc(
        'generate_custom_report',
        description='''
        **Generador de informes personalizables**
        
        Crea informes personalizados basados en criterios específicos:
        - Informes de salud animal
        - Reportes de productividad
        - Análisis de costos
        - Informes de inventario
        - Reportes de actividades
        
        **Parámetros requeridos:**
        - `report_type`: Tipo de informe (health, productivity, inventory, activities)
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        
        **Parámetros opcionales:**
        - `animal_ids`: Lista de IDs de animales específicos
        - `breed_ids`: Lista de IDs de razas
        - `format`: Formato de salida (json, summary)
        - `group_by`: Agrupar por (breed, sex, age_group, month)
        
        **Útil para:**
        - Informes ejecutivos
        - Análisis de tendencias
        - Reportes regulatorios
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'report_type': {'description': 'Tipo de informe', 'type': 'string', 'enum': ['health', 'productivity', 'inventory', 'activities'], 'required': True},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string', 'required': True},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string', 'required': True},
            'animal_ids': {'description': 'IDs de animales (separados por coma)', 'type': 'string'},
            'breed_ids': {'description': 'IDs de razas (separados por coma)', 'type': 'string'},
            'format': {'description': 'Formato de salida', 'type': 'string', 'enum': ['json', 'summary'], 'default': 'json'},
            'group_by': {'description': 'Agrupar por', 'type': 'string', 'enum': ['breed', 'sex', 'age_group', 'month']}
        },
        responses={
            200: 'Informe personalizado generado',
            400: 'Parámetros inválidos',
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @jwt_required()
    def post(self):
        """Generar informe personalizado"""
        try:
            data = request.get_json() or {}
            
            # Obtener parámetros de la petición
            report_type = data.get('report_type') or request.args.get('report_type')
            start_date_str = data.get('start_date') or request.args.get('start_date')
            end_date_str = data.get('end_date') or request.args.get('end_date')
            
            if not all([report_type, start_date_str, end_date_str]):
                return APIResponse.validation_error({
                    'required_fields': 'report_type, start_date y end_date son requeridos'
                })
            
            # Validar fechas
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return APIResponse.validation_error({
                    'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'
                })
            
            if start_date > end_date:
                return APIResponse.validation_error({
                    'date_range': 'La fecha de inicio debe ser anterior a la fecha de fin'
                })
            
            # Parámetros opcionales
            animal_ids = data.get('animal_ids') or request.args.get('animal_ids')
            breed_ids = data.get('breed_ids') or request.args.get('breed_ids')
            format_type = data.get('format') or request.args.get('format', 'json')
            group_by = data.get('group_by') or request.args.get('group_by')
            
            # Convertir IDs a listas
            if animal_ids:
                animal_ids = [int(id.strip()) for id in animal_ids.split(',') if id.strip().isdigit()]
            if breed_ids:
                breed_ids = [int(id.strip()) for id in breed_ids.split(',') if id.strip().isdigit()]
            
            # Generar informe según el tipo
            if report_type == 'health':
                report_data = self._generate_health_report(start_date, end_date, animal_ids, breed_ids, group_by)
            elif report_type == 'productivity':
                report_data = self._generate_productivity_report(start_date, end_date, animal_ids, breed_ids, group_by)
            elif report_type == 'inventory':
                report_data = self._generate_inventory_report(start_date, end_date, animal_ids, breed_ids, group_by)
            elif report_type == 'activities':
                report_data = self._generate_activities_report(start_date, end_date, animal_ids, breed_ids, group_by)
            else:
                return APIResponse.validation_error({
                    'report_type': 'Tipo de informe inválido. Use: health, productivity, inventory, activities'
                })
            
            # Formatear respuesta
            if format_type == 'summary':
                report_data = self._format_summary(report_data, report_type)
            
            return APIResponse.success(
                data={
                    'report': report_data,
                    'metadata': {
                        'report_type': report_type,
                        'period': {
                            'start_date': start_date.isoformat(),
                            'end_date': end_date.isoformat(),
                            'days': (end_date - start_date).days
                        },
                        'filters': {
                            'animal_ids': animal_ids,
                            'breed_ids': breed_ids,
                            'group_by': group_by
                        },
                        'generated_at': datetime.now().isoformat(),
                        'generated_by': get_jwt_identity().get('fullname', 'Usuario')
                    }
                },
                message=f"Informe {report_type} generado exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error generando informe personalizado: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    def _generate_health_report(self, start_date, end_date, animal_ids, breed_ids, group_by):
        """Genera informe de salud"""
        # Implementar lógica específica del informe de salud
        return {
            'treatments_summary': 'Resumen de tratamientos',
            'vaccinations_summary': 'Resumen de vacunaciones',
            'health_status_distribution': 'Distribución de estados de salud'
        }
    
    def _generate_productivity_report(self, start_date, end_date, animal_ids, breed_ids, group_by):
        """Genera informe de productividad"""
        # Implementar lógica específica del informe de productividad
        return {
            'weight_gains': 'Ganancias de peso',
            'growth_rates': 'Tasas de crecimiento',
            'performance_metrics': 'Métricas de rendimiento'
        }
    
    def _generate_inventory_report(self, start_date, end_date, animal_ids, breed_ids, group_by):
        """Genera informe de inventario"""
        # Implementar lógica específica del informe de inventario
        return {
            'animal_count': 'Conteo de animales',
            'status_distribution': 'Distribución por estado',
            'breed_composition': 'Composición por raza'
        }
    
    def _generate_activities_report(self, start_date, end_date, animal_ids, breed_ids, group_by):
        """Genera informe de actividades"""
        # Implementar lógica específica del informe de actividades
        return {
            'treatments_log': 'Registro de tratamientos',
            'vaccinations_log': 'Registro de vacunaciones',
            'controls_log': 'Registro de controles'
        }
    
    def _format_summary(self, report_data, report_type):
        """Formatea el informe como resumen ejecutivo"""
        return {
            'executive_summary': f'Resumen ejecutivo del informe {report_type}',
            'key_metrics': 'Métricas clave',
            'recommendations': 'Recomendaciones'
        }

@analytics_ns.route('/animals/<int:animal_id>/medical-history')
class AnimalMedicalHistory(Resource):
    @analytics_ns.doc(
        'get_animal_medical_history',
        description='''
        **Historial médico completo de un animal**
        
        Proporciona el historial médico detallado de un animal específico:
        - Todos los tratamientos aplicados
        - Vacunaciones recibidas
        - Controles de peso y salud
        - Línea de tiempo médica
        - Alertas y recomendaciones
        
        **Parámetros:**
        - `animal_id`: ID del animal
        - `limit`: Número máximo de registros (default: 50)
        - `start_date`: Fecha de inicio (YYYY-MM-DD)
        - `end_date`: Fecha de fin (YYYY-MM-DD)
        
        **Útil para:**
        - Ficha médica individual
        - Seguimiento de tratamientos
        - Análisis de efectividad
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'limit': {'description': 'Número máximo de registros', 'type': 'integer', 'default': 50},
            'start_date': {'description': 'Fecha de inicio (YYYY-MM-DD)', 'type': 'string'},
            'end_date': {'description': 'Fecha de fin (YYYY-MM-DD)', 'type': 'string'}
        },
        responses={
            200: 'Historial médico del animal',
            401: 'Token JWT requerido o inválido',
            404: 'Animal no encontrado',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("animal_medical_history", ttl_seconds=300)
    @jwt_required()
    def get(self, animal_id):
        """Obtener historial médico completo de un animal"""
        try:
            # Verificar que el animal existe
            animal = Animals.query.get(animal_id)
            if not animal:
                return APIResponse.not_found("Animal")
            
            limit = int(request.args.get('limit', 50))
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Filtros de fecha
            date_filter = True
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Obtener tratamientos
            treatments_query = db.session.query(
                Treatments.id,
                Treatments.treatment_date,
                Treatments.diagnosis,
                Treatments.treatment_type,
                User.fullname.label('veterinarian')
            ).join(
                User, User.id == Treatments.animal_id  # Ajustar según relación real
            ).filter(Treatments.animal_id == animal_id)
            
            if start_date:
                treatments_query = treatments_query.filter(Treatments.treatment_date >= start_date)
            if end_date:
                treatments_query = treatments_query.filter(Treatments.treatment_date <= end_date)
            
            treatments = treatments_query.order_by(
                desc(Treatments.treatment_date)
            ).limit(limit).all()
            
            # Obtener vacunaciones
            vaccinations_query = db.session.query(
                Vaccinations.id,
                Vaccinations.application_date,
                Vaccinations.dose,
                Vaccines.vaccine,
                User.fullname.label('applied_by')
            ).join(Vaccines).join(
                User, User.id == Vaccinations.instructor_id
            ).filter(Vaccinations.animal_id == animal_id)
            
            if start_date:
                vaccinations_query = vaccinations_query.filter(Vaccinations.application_date >= start_date)
            if end_date:
                vaccinations_query = vaccinations_query.filter(Vaccinations.application_date <= end_date)
            
            vaccinations = vaccinations_query.order_by(
                desc(Vaccinations.application_date)
            ).limit(limit).all()
            
            # Obtener controles
            controls_query = db.session.query(
                Control.id,
                Control.control_date,
                Control.weight,
                Control.healt_status
            ).filter(Control.animal_id == animal_id)
            
            if start_date:
                controls_query = controls_query.filter(Control.control_date >= start_date)
            if end_date:
                controls_query = controls_query.filter(Control.control_date <= end_date)
            
            controls = controls_query.order_by(
                desc(Control.control_date)
            ).limit(limit).all()
            
            # Crear línea de tiempo médica
            timeline = []
            
            # Agregar tratamientos
            for treatment in treatments:
                timeline.append({
                    'type': 'treatment',
                    'date': treatment.treatment_date.isoformat(),
                    'title': f'Tratamiento: {treatment.diagnosis}',
                    'description': f'Tipo: {treatment.treatment_type}',
                    'details': {
                        'id': treatment.id,
                        'diagnosis': treatment.diagnosis,
                        'treatment_type': treatment.treatment_type,
                        'veterinarian': treatment.veterinarian
                    },
                    'icon': '💊',
                    'color': 'red'
                })
            
            # Agregar vacunaciones
            for vaccination in vaccinations:
                timeline.append({
                    'type': 'vaccination',
                    'date': vaccination.application_date.isoformat(),
                    'title': f'Vacunación: {vaccination.vaccine}',
                    'description': f'Dosis: {vaccination.dose}',
                    'details': {
                        'id': vaccination.id,
                        'vaccine': vaccination.vaccine,
                        'dose': vaccination.dose,
                        'applied_by': vaccination.applied_by
                    },
                    'icon': '💉',
                    'color': 'green'
                })
            
            # Agregar controles
            for control in controls:
                timeline.append({
                    'type': 'control',
                    'date': control.control_date.isoformat(),
                    'title': f'Control de Salud',
                    'description': f'Peso: {control.weight}kg - Estado: {control.healt_status.value}',
                    'details': {
                        'id': control.id,
                        'weight': control.weight,
                        'health_status': control.healt_status.value
                    },
                    'icon': '📊',
                    'color': 'blue'
                })
            
            # Ordenar timeline por fecha
            timeline.sort(key=lambda x: x['date'], reverse=True)
            
            # Calcular estadísticas del animal
            total_treatments = len(treatments)
            total_vaccinations = len(vaccinations)
            total_controls = len(controls)
            
            # Tendencia de peso
            weight_trend = 'stable'
            if len(controls) >= 2:
                recent_weight = controls[0].weight
                older_weight = controls[-1].weight
                if recent_weight > older_weight * 1.05:
                    weight_trend = 'increasing'
                elif recent_weight < older_weight * 0.95:
                    weight_trend = 'decreasing'
            
            # Estado de salud actual
            current_health = controls[0].healt_status.value if controls else 'Sin datos'
            
            medical_history = {
                'animal_info': {
                    'id': animal.id,
                    'record': animal.record,
                    'sex': animal.sex.value,
                    'birth_date': animal.birth_date.isoformat() if animal.birth_date else None,
                    'current_weight': animal.weight,
                    'status': animal.status.value
                },
                'summary': {
                    'total_treatments': total_treatments,
                    'total_vaccinations': total_vaccinations,
                    'total_controls': total_controls,
                    'current_health_status': current_health,
                    'weight_trend': weight_trend,
                    'last_control_date': controls[0].control_date.isoformat() if controls else None
                },
                'timeline': timeline[:limit],
                'treatments': [
                    {
                        'id': t.id,
                        'date': t.treatment_date.isoformat(),
                        'diagnosis': t.diagnosis,
                        'treatment_type': t.treatment_type,
                        'veterinarian': t.veterinarian
                    } for t in treatments
                ],
                'vaccinations': [
                    {
                        'id': v.id,
                        'date': v.application_date.isoformat(),
                        'vaccine': v.vaccine,
                        'dose': v.dose,
                        'applied_by': v.applied_by
                    } for v in vaccinations
                ],
                'controls': [
                    {
                        'id': c.id,
                        'date': c.control_date.isoformat(),
                        'weight': c.weight,
                        'health_status': c.healt_status.value
                    } for c in controls
                ],
                'alerts': self._generate_health_alerts(animal, controls, treatments)
            }
            
            return APIResponse.success(
                data=medical_history,
                message=f"Historial médico de {animal.record} obtenido exitosamente"
            )
            
        except ValueError as e:
            return APIResponse.validation_error(
                {'date_format': 'Formato de fecha inválido. Use YYYY-MM-DD'}
            )
        except Exception as e:
            logger.error(f"Error obteniendo historial médico del animal {animal_id}: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    def _generate_health_alerts(self, animal, controls, treatments):
        """Genera alertas de salud para el animal"""
        alerts = []
        
        # Sin control reciente
        if controls:
            last_control = controls[0].control_date
            days_since_control = (datetime.now().date() - last_control).days
            
            if days_since_control > 30:
                alerts.append({
                    'type': 'warning',
                    'message': f'Sin control hace {days_since_control} días',
                    'priority': 'medium',
                    'recommendation': 'Programar control de salud'
                })
            
            # Estado de salud preocupante
            if controls[0].healt_status in [HealthStatus.Malo, HealthStatus.Regular]:
                alerts.append({
                    'type': 'danger',
                    'message': f'Estado de salud: {controls[0].healt_status.value}',
                    'priority': 'high',
                    'recommendation': 'Evaluación veterinaria urgente'
                })
        else:
            alerts.append({
                'type': 'info',
                'message': 'Sin registros de control',
                'priority': 'low',
                'recommendation': 'Realizar primer control de salud'
            })
        
        # Tratamientos frecuentes
        if len(treatments) > 5:
            alerts.append({
                'type': 'warning',
                'message': f'{len(treatments)} tratamientos registrados',
                'priority': 'medium',
                'recommendation': 'Revisar plan sanitario preventivo'
            })
        
        return alerts

@analytics_ns.route('/production/statistics')
class ProductionStatistics(Resource):
    @analytics_ns.doc(
        'get_production_statistics',
        description='''
        **Estadísticas de producción y rendimiento**
        
        Análisis de productividad del hato ganadero:
        - Tendencias de peso y crecimiento
        - Tasas de conversión alimenticia
        - Métricas de rendimiento por grupo
        - Comparativas de productividad
        
        **Parámetros opcionales:**
        - `period`: Período de análisis (6m, 1y, 2y)
        - `group_by`: Agrupar por (breed, sex, age_group)
        
        **Útil para:**
        - Gráficos de tendencias
        - Análisis de rentabilidad
        - Optimización de alimentación
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'period': {'description': 'Período de análisis', 'type': 'string', 'enum': ['6m', '1y', '2y'], 'default': '1y'},
            'group_by': {'description': 'Agrupar por', 'type': 'string', 'enum': ['breed', 'sex', 'age_group']}
        },
        responses={
            200: ('Estadísticas de producción', production_stats_model),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("production_statistics", ttl_seconds=1800)
    @jwt_required()
    def get(self):
        """Obtener estadísticas de producción y rendimiento"""
        try:
            period = request.args.get('period', '1y')
            group_by = request.args.get('group_by')
            
            # Calcular fecha de inicio según período
            period_days = {
                '6m': 180,
                '1y': 365,
                '2y': 730
            }
            
            start_date = datetime.now() - timedelta(days=period_days.get(period, 365))
            
            # Tendencias de peso (basado en controles)
            weight_trends = db.session.query(
                extract('year', Control.control_date).label('year'),
                extract('month', Control.control_date).label('month'),
                func.avg(Control.weight).label('avg_weight'),
                func.count(Control.id).label('count')
            ).filter(
                Control.control_date >= start_date
            ).group_by(
                extract('year', Control.control_date),
                extract('month', Control.control_date)
            ).order_by('year', 'month').all()
            
            # Crecimiento por animal (comparar primer y último control)
            growth_analysis = db.session.query(
                Animals.id,
                Animals.record,
                Animals.birth_date,
                func.min(Control.weight).label('initial_weight'),
                func.max(Control.weight).label('current_weight'),
                func.min(Control.control_date).label('first_control'),
                func.max(Control.control_date).label('last_control')
            ).join(Control).filter(
                Control.control_date >= start_date,
                Animals.status == AnimalStatus.Vivo
            ).group_by(
                Animals.id, Animals.record, Animals.birth_date
            ).having(
                func.count(Control.id) >= 2
            ).all()
            
            # Calcular tasas de crecimiento
            growth_rates = []
            for animal in growth_analysis:
                days_diff = (animal.last_control - animal.first_control).days
                if days_diff > 0:
                    weight_gain = animal.current_weight - animal.initial_weight
                    daily_gain = weight_gain / days_diff
                    
                    # Calcular edad aproximada
                    age_days = (datetime.now().date() - animal.birth_date).days if animal.birth_date else 0
                    age_months = age_days / 30.44
                    
                    growth_rates.append({
                        'animal_id': animal.id,
                        'record': animal.record,
                        'initial_weight': animal.initial_weight,
                        'current_weight': animal.current_weight,
                        'weight_gain': weight_gain,
                        'daily_gain': round(daily_gain, 3),
                        'period_days': days_diff,
                        'age_months': round(age_months, 1)
                    })
            
            # Estadísticas por grupo si se especifica
            group_stats = {}
            if group_by == 'breed':
                group_stats = db.session.query(
                    Breeds.name,
                    func.avg(Control.weight).label('avg_weight'),
                    func.count(func.distinct(Animals.id)).label('animal_count')
                ).join(Animals).join(Control).filter(
                    Control.control_date >= start_date,
                    Animals.status == AnimalStatus.Vivo
                ).group_by(Breeds.name).all()

                group_stats = {
                    breed: {
                        'avg_weight': round(avg_weight, 2),
                        'animal_count': animal_count
                    }
                    for breed, avg_weight, animal_count in group_stats
                }
            
            elif group_by == 'sex':
                group_stats = db.session.query(
                    Animals.sex,
                    func.avg(Control.weight).label('avg_weight'),
                    func.count(func.distinct(Animals.id)).label('animal_count')
                ).join(Control).filter(
                    Control.control_date >= start_date,
                    Animals.status == AnimalStatus.Vivo
                ).group_by(Animals.sex).all()
                
                group_stats = {
                    sex.value: {
                        'avg_weight': round(avg_weight, 2),
                        'animal_count': animal_count
                    }
                    for sex, avg_weight, animal_count in group_stats
                }
            
            # Métricas de productividad
            total_animals = len(growth_rates)
            avg_daily_gain = sum(gr['daily_gain'] for gr in growth_rates) / total_animals if total_animals > 0 else 0
            best_performers = sorted(growth_rates, key=lambda x: x['daily_gain'], reverse=True)[:5]
            
            production_data = {
                'weight_trends': [
                    {
                        'year': int(year),
                        'month': int(month),
                        'avg_weight': round(avg_weight, 2),
                        'sample_size': count,
                        'period': f"{int(year)}-{int(month):02d}"
                    }
                    for year, month, avg_weight, count in weight_trends
                ],
                'growth_rates': growth_rates,
                'productivity_metrics': {
                    'total_animals_analyzed': total_animals,
                    'average_daily_gain_kg': round(avg_daily_gain, 3),
                    'best_daily_gain_kg': max((gr['daily_gain'] for gr in growth_rates), default=0),
                    'worst_daily_gain_kg': min((gr['daily_gain'] for gr in growth_rates), default=0),
                    'period_analyzed': period
                },
                'best_performers': best_performers,
                'group_statistics': group_stats if group_by else {},
                'summary': {
                    'period': period,
                    'start_date': start_date.isoformat(),
                    'total_controls': sum(count for _, _, _, count in weight_trends),
                    'animals_with_growth_data': total_animals
                }
            }
            
            return APIResponse.success(
                data=production_data,
                message="Estadísticas de producción obtenidas exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de producción: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )
    
    def _get_health_alerts(self):
        """Obtiene alertas de salud importantes"""
        alerts = []
        
        # Animales sin control reciente (más de 30 días)
        month_ago = datetime.now() - timedelta(days=30)
        animals_without_control = db.session.query(Animals).filter(
            ~Animals.id.in_(
                db.session.query(Control.animal_id).filter(
                    Control.control_date >= month_ago
                )
            ),
            Animals.status == AnimalStatus.Vivo
        ).count()
        
        if animals_without_control > 0:
            alerts.append({
                'type': 'warning',
                'message': f'{animals_without_control} animales sin control en los últimos 30 días',
                'priority': 'medium'
            })
        
        # Animales con estado de salud malo o regular
        unhealthy_animals = db.session.query(Control).filter(
            Control.healt_status.in_([HealthStatus.Malo, HealthStatus.Regular])
        ).join(Animals).filter(
            Animals.status == AnimalStatus.Vivo
        ).count()
        
        if unhealthy_animals > 0:
            alerts.append({
                'type': 'danger',
                'message': f'{unhealthy_animals} animales con estado de salud preocupante',
                'priority': 'high'
            })
        
        return alerts
    
    def _get_productivity_summary(self):
        """Obtiene resumen de productividad"""
        # Promedio de peso por grupo de edad
        current_year = datetime.now().year
        
        weight_avg = db.session.query(
            func.avg(Animals.weight).label('avg_weight')
        ).filter(
            Animals.status == AnimalStatus.Vivo
        ).scalar() or 0
        
        # Tasa de crecimiento (basada en controles)
        growth_rate = db.session.query(
            func.avg(Control.weight).label('avg_control_weight')
        ).filter(
            Control.control_date >= datetime(current_year, 1, 1)
        ).scalar() or 0
        
        return {
            'average_weight': round(weight_avg, 2),
            'average_control_weight': round(growth_rate, 2),
            'weight_trend': 'stable'  # Se puede calcular comparando períodos
        }

@analytics_ns.route('/animals/statistics')
class AnimalStatistics(Resource):
    @analytics_ns.doc(
        'get_animal_statistics',
        description='''
        **Estadísticas detalladas de animales**
        
        Proporciona análisis completo del inventario ganadero:
        - Distribución por estado (vivo, vendido, muerto)
        - Distribución por sexo y raza
        - Grupos de edad y distribución de pesos
        - Tendencias de crecimiento
        
        **Ideal para:**
        - Gráficos de torta y barras
        - Análisis de composición del hato
        - Planificación de reproducción
        ''',
        security=['Bearer', 'Cookie'],
        responses={
            200: ('Estadísticas de animales', animal_stats_model),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("animal_statistics", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener estadísticas detalladas de animales"""
        try:
            # Estadísticas por estado
            status_stats = db.session.query(
                Animals.status,
                func.count(Animals.id).label('count')
            ).group_by(Animals.status).all()
            
            # Estadísticas por sexo
            sex_stats = db.session.query(
                Animals.sex,
                func.count(Animals.id).label('count')
            ).group_by(Animals.sex).all()
            
            # Estadísticas por raza
            breed_stats = db.session.query(
                Breeds.name,
                func.count(Animals.id).label('count')
            ).join(Animals).group_by(Breeds.name).order_by(
                desc(func.count(Animals.id))
            ).limit(10).all()
            
            # Grupos de edad
            current_date = datetime.now().date()
            age_groups = {
                'Terneros (0-1 año)': 0,
                'Jóvenes (1-2 años)': 0,
                'Adultos (2-5 años)': 0,
                'Maduros (5+ años)': 0
            }
            
            animals_with_age = db.session.query(Animals.birth_date).filter(
                Animals.status == AnimalStatus.Vivo
            ).all()
            
            for animal in animals_with_age:
                if animal.birth_date:
                    age_years = (current_date - animal.birth_date).days / 365.25
                    if age_years < 1:
                        age_groups['Terneros (0-1 año)'] += 1
                    elif age_years < 2:
                        age_groups['Jóvenes (1-2 años)'] += 1
                    elif age_years < 5:
                        age_groups['Adultos (2-5 años)'] += 1
                    else:
                        age_groups['Maduros (5+ años)'] += 1
            
            # Distribución de pesos
            weight_ranges = {
                '0-200 kg': 0,
                '201-400 kg': 0,
                '401-600 kg': 0,
                '601+ kg': 0
            }
            
            animals_weights = db.session.query(Animals.weight).filter(
                Animals.status == AnimalStatus.Vivo
            ).all()
            
            for animal in animals_weights:
                weight = animal.weight
                if weight <= 200:
                    weight_ranges['0-200 kg'] += 1
                elif weight <= 400:
                    weight_ranges['201-400 kg'] += 1
                elif weight <= 600:
                    weight_ranges['401-600 kg'] += 1
                else:
                    weight_ranges['601+ kg'] += 1
            
            statistics_data = {
                'by_status': {
                    status.value: count for status, count in status_stats
                },
                'by_sex': {
                    sex.value: count for sex, count in sex_stats
                },
                'by_breed': [
                    {'breed': breed, 'count': count} 
                    for breed, count in breed_stats
                ],
                'by_age_group': age_groups,
                'weight_distribution': weight_ranges,
                'total_animals': sum(count for _, count in status_stats),
                'average_weight': db.session.query(
                    func.avg(Animals.weight)
                ).filter(Animals.status == AnimalStatus.Vivo).scalar() or 0
            }
            
            return APIResponse.success(
                data=statistics_data,
                message="Estadísticas de animales obtenidas exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de animales: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )

@analytics_ns.route('/health/statistics')
class HealthStatistics(Resource):
    @analytics_ns.doc(
        'get_health_statistics',
        description='''
        **Estadísticas de salud animal**
        
        Análisis completo del estado sanitario del hato:
        - Tratamientos y vacunaciones por período
        - Distribución de estados de salud
        - Enfermedades más comunes
        - Uso de medicamentos y vacunas
        
        **Parámetros opcionales:**
        - `months`: Número de meses hacia atrás (default: 12)
        - `animal_id`: Filtrar por animal específico
        
        **Útil para:**
        - Gráficos de líneas temporales
        - Análisis de tendencias de salud
        - Planificación de programas sanitarios
        ''',
        security=['Bearer', 'Cookie'],
        params={
            'months': {'description': 'Meses hacia atrás para el análisis', 'type': 'integer', 'default': 12},
            'animal_id': {'description': 'ID de animal específico', 'type': 'integer'}
        },
        responses={
            200: ('Estadísticas de salud', health_stats_model),
            401: 'Token JWT requerido o inválido',
            500: 'Error interno del servidor'
        }
    )
    @PerformanceLogger.log_request_performance
    @cache_query_result("health_statistics", ttl_seconds=600)
    @jwt_required()
    def get(self):
        """Obtener estadísticas de salud animal"""
        try:
            months_back = int(request.args.get('months', 12))
            animal_id = request.args.get('animal_id')
            
            start_date = datetime.now() - timedelta(days=months_back * 30)
            
            # Filtros base
            treatment_query = db.session.query(Treatments).filter(
                Treatments.treatment_date >= start_date
            )
            vaccination_query = db.session.query(Vaccinations).filter(
                Vaccinations.application_date >= start_date
            )
            
            if animal_id:
                treatment_query = treatment_query.filter(Treatments.animal_id == animal_id)
                vaccination_query = vaccination_query.filter(Vaccinations.animal_id == animal_id)
            
            # Tratamientos por mes
            treatments_by_month = db.session.query(
                extract('year', Treatments.treatment_date).label('year'),
                extract('month', Treatments.treatment_date).label('month'),
                func.count(Treatments.id).label('count')
            ).filter(
                Treatments.treatment_date >= start_date
            ).group_by(
                extract('year', Treatments.treatment_date),
                extract('month', Treatments.treatment_date)
            ).order_by('year', 'month').all()
            
            # Vacunaciones por mes
            vaccinations_by_month = db.session.query(
                extract('year', Vaccinations.application_date).label('year'),
                extract('month', Vaccinations.application_date).label('month'),
                func.count(Vaccinations.id).label('count')
            ).filter(
                Vaccinations.application_date >= start_date
            ).group_by(
                extract('year', Vaccinations.application_date),
                extract('month', Vaccinations.application_date)
            ).order_by('year', 'month').all()
            
            # Estados de salud más recientes
            health_status_dist = db.session.query(
                Control.healt_status,
                func.count(Control.id).label('count')
            ).filter(
                Control.control_date >= start_date
            ).group_by(Control.healt_status).all()
            
            # Enfermedades más comunes (basado en diagnósticos)
            common_diseases = db.session.query(
                Treatments.diagnosis,
                func.count(Treatments.id).label('count')
            ).filter(
                Treatments.treatment_date >= start_date
            ).group_by(Treatments.diagnosis).order_by(
                desc(func.count(Treatments.id))
            ).limit(10).all()
            
            # Uso de medicamentos
            medication_usage = db.session.query(
                Medications.name,
                func.count(Treatments.id).label('usage_count')
            ).join(
                # Aquí asumo que hay una relación entre tratamientos y medicamentos
                # Si no existe, se puede crear o usar el campo diagnosis
                Treatments, Treatments.diagnosis.ilike(func.concat('%', Medications.name, '%'))
            ).filter(
                Treatments.treatment_date >= start_date
            ).group_by(Medications.name).order_by(
                desc(func.count(Treatments.id))
            ).limit(10).all()
            
            health_data = {
                'treatments_by_month': [
                    {
                        'year': int(year),
                        'month': int(month),
                        'count': count,
                        'period': f"{int(year)}-{int(month):02d}"
                    }
                    for year, month, count in treatments_by_month
                ],
                'vaccinations_by_month': [
                    {
                        'year': int(year),
                        'month': int(month),
                        'count': count,
                        'period': f"{int(year)}-{int(month):02d}"
                    }
                    for year, month, count in vaccinations_by_month
                ],
                'health_status_distribution': {
                    status.value: count for status, count in health_status_dist
                },
                'common_diseases': [
                    {'diagnosis': diagnosis, 'count': count}
                    for diagnosis, count in common_diseases
                ],
                'medication_usage': [
                    {'medication': medication, 'usage_count': count}
                    for medication, count in medication_usage
                ],
                'summary': {
                    'total_treatments': sum(count for _, _, count in treatments_by_month),
                    'total_vaccinations': sum(count for _, _, count in vaccinations_by_month),
                    'period_months': months_back
                }
            }
            
            return APIResponse.success(
                data=health_data,
                message="Estadísticas de salud obtenidas exitosamente"
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de salud: {str(e)}")
            return APIResponse.error(
                message="Error interno del servidor",
                status_code=500,
                details={'error': str(e)}
            )