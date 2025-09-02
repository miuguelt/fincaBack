from app import db
import enum

class Role(enum.Enum):
    Aprendiz = "Aprendiz"
    Instructor = "Instructor"
    Administrador = "Administrador"

class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    identification = db.Column(db.Integer, unique=True, nullable=False)
    fullname = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(10), unique=True, nullable=False)
    address = db.Column(db.String(120), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False)
    status = db.Column(db.Boolean, nullable=False, default=True)
    

    diseases = db.relationship('AnimalDiseases', back_populates='instructors')
    vaccines_as_apprentice = db.relationship('Vaccinations', foreign_keys='Vaccinations.apprentice_id', back_populates='apprentice')
    vaccines_as_instructor = db.relationship('Vaccinations', foreign_keys='Vaccinations.instructor_id', back_populates='instructor')

    def to_json(self):
        return {
            'id': self.id,
            'identification': self.identification,
            'fullname': self.fullname,
            # 'password': self.password,  # NUNCA incluir contraseña en respuestas JSON
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'role': self.role.value,
            'status': self.status
        }