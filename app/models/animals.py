from app import db 
import enum

class Sex (enum.Enum):
    Hembra = 'Hembra'
    Macho = 'Macho'

class AnimalStatus(enum.Enum):
    Vivo = 'Vivo'
    Vendido = 'Vendido'
    Muerto = 'Muerto'
    
class Animals(db.Model):
    __tablename__ = 'animals'
    id = db.Column(db.Integer, primary_key=True)
    sex = db.Column(db.Enum(Sex), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    weight = db.Column(db.Integer, nullable=False)
    record = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum(AnimalStatus), default=AnimalStatus.Vivo)

    breeds_id = db.Column(db.Integer, db.ForeignKey('breeds.id'), nullable=False) 
    idFather = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=True)
    idMother = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=True)

    breed = db.relationship('Breeds', back_populates='animals', lazy='joined')
    father = db.relationship('Animals', remote_side=[id], foreign_keys=[idFather])
    mother = db.relationship('Animals', remote_side=[id], foreign_keys=[idMother])

    treatments = db.relationship('Treatments', back_populates='animals')
    vaccinations = db.relationship('Vaccinations', back_populates='animals')
    diseases = db.relationship('AnimalDiseases', back_populates='animals')
    controls = db.relationship('Control', back_populates='animals')
    genetic_improvements = db.relationship('GeneticImprovements', back_populates='animals')
    animal_fields = db.relationship('AnimalFields', back_populates='animals')

    
    def to_json(self, include_relations=True):
        """Convertir el animal a JSON con opción de incluir relaciones"""
        try:
            result = {
                'idAnimal': self.id,
                'birth_date': self.birth_date.strftime('%Y-%m-%d') if self.birth_date else None,
                'weight': self.weight,
                'breed': self.breed.to_json() if self.breed else None,
                'sex': self.sex.value if self.sex else None,
                'status': self.status.value if self.status else None,
                'record': self.record,
                'idFather': self.idFather,
                'idMother': self.idMother
            }
            
            # Incluir relaciones padre/madre solo si se solicita y para evitar recursión infinita
            if include_relations:
                result.update({
                    'father': self.father.to_json(include_relations=False) if self.father else None,
                    'mother': self.mother.to_json(include_relations=False) if self.mother else None
                })
            
            return result
            
        except Exception as e:
            # En caso de error, devolver datos básicos
            return {
                'idAnimal': self.id,
                'record': self.record or f'Animal-{self.id}',
                'error': f'Error serializing animal: {str(e)}'
            }
