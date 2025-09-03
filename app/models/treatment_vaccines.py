from app import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class TreatmentVaccines(BaseModel, TimestampMixin):
    """Modelo de relación entre tratamientos y vacunas optimizado para namespaces"""
    __tablename__ = 'treatment_vaccines'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatments.id'), nullable=False)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)

    # Relaciones optimizadas
    treatments = db.relationship('Treatments', back_populates='vaccines_treatments', lazy='joined')
    vaccines = db.relationship('Vaccines', back_populates='treatments', lazy='joined')

    # Configuraciones del modelo base
    _filterable_fields = ['treatment_id', 'vaccine_id']
    _sortable_fields = ['id', 'created_at']
    _required_fields = ['treatment_id', 'vaccine_id']
    _unique_fields = [('treatment_id', 'vaccine_id')]
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_treatment_vaccines_treatment', 'treatment_id'),
        db.Index('idx_treatment_vaccines_vaccine', 'vaccine_id'),
        db.UniqueConstraint('treatment_id', 'vaccine_id', name='uq_treatment_vaccine'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto TreatmentVaccine a un diccionario JSON, permitiendo la inclusión
        selectiva de relaciones para optimizar la carga de datos.

        Args:
            include_relations (List[str], optional): Lista de nombres de relaciones
                a incluir en la serialización. Defaults to None.

        Returns:
            Dict[str, Any]: Diccionario con los datos de la relación.
        """
        return self.to_dict(include_relations=include_relations)
    
    def __repr__(self):
        """Representación string del modelo"""
        return f'<TreatmentVaccine {self.id}: Treatment {self.treatment_id} - Vaccine {self.vaccine_id}>'