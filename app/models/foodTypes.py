from app import db

class FoodTypes(db.Model):
    __tablename__ = 'food_types'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    food_type = db.Column(db.String(255), nullable=False)
    sowing_date = db.Column(db.Date, nullable=False)
    harvest_date = db.Column(db.Date, nullable=True)
    area = db.Column(db.Integer, nullable=False)
    handlings = db.Column(db.String(255), nullable=False)
    gauges = db.Column(db.String(255), nullable=False)

    fields = db.relationship('Fields', back_populates='food_types')

    def to_json(self):
        return {
            'id': self.id,
            'food_type': self.food_type,
            'sowing_date': self.sowing_date.strftime('%Y-%m-%d'),
            'harvest_date': self.harvest_date.strftime('%Y-%m-%d'),
            'area': self.area,
            'handlings': self.handlings,
            'gauges': self.gauges
        }