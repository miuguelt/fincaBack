from app import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel

class Breeds(BaseModel):
    """Modelo para razas de animales optimizado para namespaces"""
    __tablename__ = 'breeds'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False)

    # Relaciones optimizadas
    animals = db.relationship('Animals', back_populates='breed', lazy='dynamic')
    species = db.relationship('Species', back_populates='breeds', lazy='joined')

    # Configuraciones del modelo base
    _searchable_fields = ['name']
    _filterable_fields = ['species_id', 'name']
    _sortable_fields = ['id', 'name']
    _required_fields = ['name', 'species_id']
    _unique_fields = [('name', 'species_id')]  # Combinación única
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_breeds_species', 'species_id'),
        db.Index('idx_breeds_name', 'name'),
        db.Index('idx_breeds_name_species', 'name', 'species_id'),
    )
    
    def _validate_instance(self):
        """Validaciones específicas para razas"""
        errors = []
        
        # Validar nombre
        if not self.name or not self.name.strip():
            errors.append("El nombre de la raza es requerido")
        elif len(self.name.strip()) < 2:
            errors.append("El nombre de la raza debe tener al menos 2 caracteres")
        
        # Validar que la especie existe
        if self.species_id:
            from app.models.species import Species
            if not Species.query.get(self.species_id):
                errors.append("La especie especificada no existe")
        
        if errors:
            from app.models.base_model import ValidationError
            raise ValidationError("; ".join(errors))
    
    @classmethod
    def validate_for_namespace(cls, data: Dict[str, Any]) -> List[str]:
        """Validación específica para uso en namespaces"""
        from app.utils.model_validators import ValidationRules
        
        errors = []
        
        # Validar nombre
        if 'name' in data:
            errors.extend(ValidationRules.validate_string_length(
                data['name'], "nombre de la raza", min_length=2, max_length=255
            ))
        
        # Validar que la especie existe
        if 'species_id' in data:
            from app.models.species import Species
            errors.extend(ValidationRules.validate_foreign_key_exists(
                data['species_id'], Species, "especie"
            ))
        
        return errors

    def to_json(self, include_relations: List[str] = None, namespace_format: bool = False) -> Dict[str, Any]:
        """
        Serialización JSON optimizada para namespaces.
        
        Args:
            include_relations: Relaciones a incluir
            namespace_format: Si usar formato específico para namespaces
        """
        if namespace_format:
            result = {
                'id': self.id,
                'breed': self.name,  # Usar 'breed' como en el namespace existente
                'species_id': self.species_id,
            }
            
            # Incluir información de la especie si está disponible
            if self.species:
                result['species'] = {
                    'id': self.species.id,
                    'name': self.species.name
                }
            
            # Incluir estadísticas de animales si se solicita
            if include_relations and 'animals_count' in include_relations:
                result['animals_count'] = self.animals.count()
            
            return result
        else:
            # Usar serialización base
            return super().to_json(include_relations)
    
    @classmethod
    def get_optimized_query(cls, include_relations: List[str] = None):
        """Consulta optimizada con eager loading para namespaces"""
        query = cls.query
        
        # Siempre incluir species para evitar consultas N+1
        query = query.options(joinedload(cls.species))
        
        return query
    
    @classmethod
    def get_statistics_for_namespace(cls) -> Dict[str, Any]:
        """Estadísticas optimizadas para namespaces"""
        stats = cls.get_statistics()
        
        try:
            # Top 5 razas con más animales
            top_breeds = db.session.query(
                cls.name, 
                func.count('Animals.id').label('animal_count')
            ).outerjoin(cls.animals).group_by(cls.name).order_by(
                func.count('Animals.id').desc()
            ).limit(5).all()
            
            stats['top_breeds_by_animals'] = [
                {'breed': breed, 'animal_count': count}
                for breed, count in top_breeds
            ]
            
            # Distribución por especies
            species_distribution = db.session.query(
                'Species.name',
                func.count(cls.id).label('breed_count')
            ).join(cls.species).group_by('Species.name').all()
            
            stats['breeds_by_species'] = [
                {'species': species, 'breed_count': count}
                for species, count in species_distribution
            ]
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculando estadísticas de razas: {e}")
            stats['calculation_errors'] = str(e)
        
        return stats
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<Breed {self.id}: {self.name}>'