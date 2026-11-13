"""Crea tablas faltantes sin eliminar datos; usa la conexión de .env."""
from app import app
from extensions import db

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Tablas creadas o verificadas. Los datos existentes se conservaron.')
