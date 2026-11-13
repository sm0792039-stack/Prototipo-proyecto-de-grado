"""
extensions.py
Instancias de extensiones de Flask compartidas por toda la aplicación.

Se crean en un módulo separado (en vez de dentro de app.py) para evitar
importaciones circulares: tanto models.py como los blueprints necesitan
acceder a "db" y "login_manager" sin depender de app.py.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3


@event.listens_for(Engine, 'connect')
def configurar_sqlite(conexion, _registro):
    if isinstance(conexion, sqlite3.Connection):
        cursor = conexion.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.close()

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para continuar.'
login_manager.login_message_category = 'info'
