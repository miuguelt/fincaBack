from app import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any, List
from app.models.base_model import BaseModel, TimestampMixin

class TreatmentMedications(BaseModel, TimestampMixin):
    """Modelo de relación entre tratamientos y medicamentos optimizado para namespaces"""
    __tablename__ = 'treatment_medications'
    
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    treatment_id = db.Column(db.Integer, db.ForeignKey('treatments.id'), nullable=False)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)

    # Relaciones optimizadas
    treatments = db.relationship('Treatments', back_populates='medication_treatments', lazy='joined')
    medications = db.relationship('Medications', back_populates='treatments', lazy='joined')

    # Configuraciones del modelo base
    _filterable_fields = ['treatment_id', 'medication_id']
    _sortable_fields = ['id', 'created_at']
    _required_fields = ['treatment_id', 'medication_id']
    _unique_fields = [('treatment_id', 'medication_id')]
    
    # Índices para optimización de consultas
    __table_args__ = (
        db.Index('idx_treatment_medications_treatment', 'treatment_id'),
        db.Index('idx_treatment_medications_medication', 'medication_id'),
        db.UniqueConstraint('treatment_id', 'medication_id', name='uq_treatment_medication'),
    )

    def to_json(self, include_relations: List[str] = None) -> Dict[str, Any]:
        """
        Serializa el objeto TreatmentMedication a un diccionario JSON, permitiendo la inclusión
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
        return f'<TreatmentMedication {self.id}: Treatment {self.treatment_id} - Medication {self.medication_id}>'