from app import db 
import enum

class HealtStatus(enum.Enum):
    Excelente = "Excelente"
    Bueno = "Bueno"
    Regular = "Regular"
    Malo = "Malo"

class Control(db.Model):
    __tablename__ = 'control'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    checkup_date = db.Column(db.Date, nullable=False)
    healt_status = db.Column(db.Enum(HealtStatus), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)

    animals = db.relationship('Animals', back_populates='controls', lazy='joined')

    def to_json(self):
        return {
            'id': self.id,
            'checkup_date': self.checkup_date.strftime('%Y-%m-%d'),
            'healt_status': self.healt_status.value,
            'description': self.description,
            'animal_id': self.animal_id,
            'animals': self.animals.to_json() if self.animals else None
        }