from app import db

class AnimalFields(db.Model):
    __tablename__ = "animal_fields"
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    duration = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Boolean, nullable=False, default=True)


    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)

    animals = db.relationship('Animals', back_populates='animal_fields')
    fields = db.relationship('Fields', back_populates='animal_fields')

    def to_json(self):
        return {
            'id': self.id,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'duration': self.duration,
            'animal_id': self.animal_id,
            'field_id': self.field_id,
            'fields' : self.fields.to_json()if self.fields else None,
            'animals' : self.animals.to_json()if self.animals else None,
            "status": self.status
        }