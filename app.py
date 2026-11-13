"""
app.py
Punto de entrada de My Remember.

Ejecutar en desarrollo:
    python app.py
Esto levanta un servidor local en http://localhost:5000
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Flask, render_template
from flask_login import current_user

from config import Config
from extensions import db, login_manager
from utils import formatear_fecha_larga, formatear_fecha_corta, formatear_hora


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    from security import configure_security
    configure_security(app)

    db.init_app(app)
    login_manager.init_app(app)

    # Filtros de plantilla para fechas/horas en español (ver utils.py:
    # se evita strftime('%A'/'%B'/'%p') porque su resultado depende del
    # locale del sistema operativo, que no siempre está disponible).
    app.jinja_env.filters['fecha_larga'] = formatear_fecha_larga
    app.jinja_env.filters['fecha_corta'] = formatear_fecha_corta
    app.jinja_env.filters['hora12'] = formatear_hora

    def fecha_hora_local(valor):
        if not valor:
            return ''
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        local = valor.astimezone(ZoneInfo(app.config['TIMEZONE']))
        return f'{local:%d/%m/%Y} · {formatear_hora(local.time())}'

    app.jinja_env.filters['fecha_hora_local'] = fecha_hora_local

    # Los blueprints importan modelos y utilidades que dependen de "db" y
    # "login_manager"; se importan aquí (dentro de create_app) para
    # asegurar que las extensiones ya existen cuando esos módulos se cargan.
    from blueprints.auth import auth_bp
    from blueprints.adulto import adulto_bp
    from blueprints.familiar import familiar_bp
    from blueprints.comunidad import comunidad_bp
    from seguimiento import seguimiento_bp, version_familia

    app.register_blueprint(auth_bp)
    app.register_blueprint(adulto_bp)
    app.register_blueprint(familiar_bp)
    app.register_blueprint(comunidad_bp)
    app.register_blueprint(seguimiento_bp)

    # CREATE IF NOT EXISTS conserva datos existentes y agrega las tablas nuevas.
    # MySQL se inicializa explícitamente con create_tables.py.
    if app.config.get('AUTO_CREATE_TABLES'):
        with app.app_context():
            if db.engine.url.drivername == 'sqlite':
                db.create_all()

    @app.route('/privacidad')
    def privacidad():
        return render_template('privacidad.html')

    @app.context_processor
    def variables_globales():
        """Disponibles en todas las plantillas sin tener que pasarlas
        explícitamente desde cada vista."""
        return {
            'anio_actual': datetime.now(ZoneInfo(app.config['TIMEZONE'])).year,
            'seguimiento_version': version_familia(current_user) if current_user.is_authenticated else '',
        }

    @app.errorhandler(403)
    def prohibido(_error):
        return render_template('error.html', codigo=403,
                                titulo='Acceso no permitido',
                                mensaje='Tu cuenta no tiene permiso para ver esta página.'), 403

    @app.errorhandler(404)
    def no_encontrado(_error):
        return render_template('error.html', codigo=404,
                                titulo='Página no encontrada',
                                mensaje='La página que buscas no existe o fue movida.'), 404

    @app.errorhandler(400)
    def solicitud_invalida(_error):
        return render_template('error.html', codigo=400, titulo='Revisa la solicitud',
                               mensaje='No se pudo completar la acción. Vuelve a abrir la página.'), 400

    @app.errorhandler(413)
    def solicitud_grande(_error):
        return render_template('error.html', codigo=413, titulo='El texto es demasiado largo',
                               mensaje='Reduce el contenido del formulario e inténtalo otra vez.'), 413

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False)
