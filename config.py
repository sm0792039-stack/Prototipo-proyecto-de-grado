"""Configuración local y MySQL sin credenciales incluidas en el proyecto."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).with_name('.env'))


def database_uri():
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    # Conserva la configuración MySQL de las instalaciones anteriores.
    if os.environ.get('DB_NAME'):
        return URL.create(
            'mysql+pymysql', username=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', ''),
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', '3306')),
            database=os.environ['DB_NAME'], query={'charset': 'utf8mb4'},
        )
    return 'sqlite:///my_remember.db'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    AUTO_CREATE_TABLES = True
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Bogota')
    UMBRAL_ALERTA_MINUTOS = 30
    MINUTOS_POSPONER = 15
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('COOKIE_SECURE', '0') == '1'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    MAX_CONTENT_LENGTH = 128 * 1024
    WTF_CSRF_TIME_LIMIT = 12 * 60 * 60
    LOGIN_RATE_LIMIT_ENABLED = True
