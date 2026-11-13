"""Protecciones de formularios, sesión y acceso de la instalación local."""
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock

from flask import g, render_template, request, session
from flask_login import current_user
from flask_wtf.csrf import CSRFError, CSRFProtect


def configure_security(app):
    if not app.config.get('SECRET_KEY'):
        directory = Path(app.instance_path)
        directory.mkdir(parents=True, exist_ok=True)
        key_file = directory / 'secret_key'
        try:
            fd = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_hex(32))
        app.config['SECRET_KEY'] = key_file.read_text().strip()
        if not app.config['SECRET_KEY']:
            raise RuntimeError('La clave de sesión local está vacía.')

    CSRFProtect(app)
    attempts = defaultdict(deque)
    lock = Lock()

    @app.before_request
    def limit_login():
        if request.endpoint != 'auth.login' or request.method != 'POST':
            return None
        if not app.config.get('LOGIN_RATE_LIMIT_ENABLED', True):
            return None
        key = (request.remote_addr, request.form.get('correo', '').strip().lower()[:120])
        now = time.monotonic()
        with lock:
            # Este límite es por proceso. En producción usar el proxy o Redis.
            if len(attempts) > 5000:
                for old_key in list(attempts):
                    if not attempts[old_key] or attempts[old_key][-1] < now - 600:
                        attempts.pop(old_key, None)
            bucket = attempts[key]
            while bucket and bucket[0] <= now - 600:
                bucket.popleft()
            if len(bucket) >= 10:
                return render_template(
                    'error.html', codigo=429, titulo='Espera unos minutos',
                    mensaje='Hubo varios intentos de ingreso. Inténtalo de nuevo en 10 minutos.',
                ), 429, {'Retry-After': '600'}
            bucket.append(now)
            g.login_rate_key = key

    @app.after_request
    def secure_response(response):
        if current_user.is_authenticated:
            session.permanent = True
            if getattr(g, 'login_rate_key', None) and response.status_code == 302:
                with lock:
                    attempts.pop(g.login_rate_key, None)
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    @app.errorhandler(CSRFError)
    def expired_form(_error):
        return render_template(
            'error.html', codigo=400, titulo='Actualiza el formulario',
            mensaje='Este formulario venció o no pudo verificarse. Vuelve a abrir la página e inténtalo otra vez.',
        ), 400
