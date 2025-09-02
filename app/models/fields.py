from app import db
import enum

class LandStatus(enum.Enum):
    Disponible = "Disponible"
    Ocupado = "Ocupado"
    Mantenimiento = "Mantenimiento"
    Restringido = "Restringido"
    Dañado = "Dañado"

class Fields(db.Model):
    __tablename__ = "fields"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    ubication = db.Column(db.String(255), nullable=False)
    capacity = db.Column(db.String(255), nullable=False)
    state = db.Column(db.Enum(LandStatus), nullable=False)
    handlings = db.Column(db.String(255), nullable=False)
    guages = db.Column(db.String(255), nullable=False)
    area = db.Column(db.String(255), nullable=False)

    food_type_id = db.Column(db.Integer, db.ForeignKey('food_types.id'), nullable=True)

    animal_fields = db.relationship('AnimalFields', back_populates='fields')
    food_types = db.relationship('FoodTypes', back_populates='fields')
    
    def to_json(self):
        return{
            'id': self.id,
            'name': self.name,
            'ubication': self.ubication,
            'capacity': self.capacity,
            'state': self.state.value,
            'handlings': self.handlings,
            'guages': self.guages,
            'area': self.area,
            'food_type_id': self.food_type_id,
            'food_types': self.food_types.to_json() if self.food_types else None
        }
