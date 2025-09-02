from app import db

class Species(db.Model):
    __tablename__ = 'species'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    
    breeds = db.relationship('Breeds', back_populates='species')

    def to_json(self): 
        return {
            'id': self.id,
            'name': self.name
        }