"""
blueprints/auth.py
Selección de perfil, registro, inicio de sesión y cierre de sesión.

Flujo de vinculación familiar:
  1. El adulto mayor se registra primero -> se crea una Familia nueva y
     recibe un "código de familia" único (ej: FAM-7XQ2K).
  2. Cada familiar/cuidador se registra ingresando ese código -> queda
     vinculado a la misma Familia y puede ver/acompañar al mismo adulto
     mayor desde su propia cuenta.
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Usuario, Familia
from utils import generar_codigo_familia
from blueprints.comunidad import normalizar_codigo

auth_bp = Blueprint('auth', __name__)


def _valores_formulario():
    """Conservar los datos útiles al corregir, sin devolver las contraseñas."""
    return {clave: valor for clave, valor in request.form.items()
            if clave not in {'contrasena', 'confirmar_contrasena', 'csrf_token'}}


def _errores_cuenta(nombre, correo, telefono, contrasena, confirmar):
    errores = []
    if not 2 <= len(nombre) <= 120:
        errores.append('El nombre debe tener entre 2 y 120 caracteres.')
    if len(correo) > 120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', correo):
        errores.append('Escribe un correo electrónico válido de hasta 120 caracteres.')
    if not 8 <= len(contrasena) <= 256:
        errores.append('La contraseña debe tener entre 8 y 256 caracteres.')
    if contrasena != confirmar:
        errores.append('Las contraseñas no coinciden.')
    if len(telefono) > 30 or (telefono and not re.fullmatch(r'[\d\s+().-]+', telefono)):
        errores.append('El teléfono debe tener hasta 30 caracteres y contener solo números y signos telefónicos.')
    if correo and Usuario.query.filter_by(correo=correo).first():
        errores.append('Ya existe una cuenta registrada con ese correo.')
    return errores


@auth_bp.route('/')
def index():
    """Página de entrada: selección de perfil para nuevos usuarios, o
    redirección directa al panel correspondiente si ya hay sesión."""
    if current_user.is_authenticated:
        destino = 'adulto.inicio' if current_user.es_adulto_mayor() else 'familiar.panel'
        return redirect(url_for(destino))
    return render_template('auth/seleccionar_perfil.html')


@auth_bp.route('/registro/adulto', methods=['GET', 'POST'])
def registro_adulto():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre_completo', '').strip()
        correo = request.form.get('correo', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        contrasena = request.form.get('contrasena', '')
        confirmar = request.form.get('confirmar_contrasena', '')

        errores = _errores_cuenta(nombre, correo, telefono, contrasena, confirmar)

        if errores:
            for error in errores:
                flash(error, 'danger')
            return render_template('auth/registro_adulto.html', valores=_valores_formulario())

        familia = Familia(codigo_familia=generar_codigo_familia())
        db.session.add(familia)

        usuario = Usuario(
            nombre_completo=nombre, correo=correo, telefono=telefono,
            rol='adulto_mayor', avatar_inicial=nombre[0].upper(),
            avatar_color='#2E9E93', familia=familia,
        )
        usuario.set_password(contrasena)
        db.session.add(usuario)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('No se pudo crear la cuenta. Revisa si el correo ya fue registrado e inténtalo de nuevo.', 'danger')
            return render_template('auth/registro_adulto.html', valores=_valores_formulario()), 409

        login_user(usuario)
        flash(
            f'¡Bienvenido/a a My Remember! Tu código de familia es {familia.codigo_familia}. '
            'Compártelo con tus familiares para que puedan acompañarte desde la plataforma.',
            'success',
        )
        return redirect(url_for('adulto.inicio'))

    return render_template('auth/registro_adulto.html', valores={})


@auth_bp.route('/registro/familiar', methods=['GET', 'POST'])
def registro_familiar():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre_completo', '').strip()
        correo = request.form.get('correo', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        parentesco = request.form.get('parentesco', '').strip()
        codigo_familia = normalizar_codigo(request.form.get('codigo_familia', ''))
        contrasena = request.form.get('contrasena', '')
        confirmar = request.form.get('confirmar_contrasena', '')
        es_contacto_emergencia = request.form.get('es_contacto_emergencia') == 'on'

        familia = Familia.query.filter_by(codigo_familia=codigo_familia).first()

        errores = _errores_cuenta(nombre, correo, telefono, contrasena, confirmar)
        if len(parentesco) > 50:
            errores.append('El parentesco debe tener hasta 50 caracteres.')
        if not codigo_familia or len(codigo_familia) > 20:
            errores.append('Escribe el código que aparece en la cuenta del adulto mayor.')
        elif not familia or not familia.adulto_mayor():
            errores.append('No encontramos ninguna familia con ese código. Verifícalo con tu ser querido.')

        if errores:
            for error in errores:
                flash(error, 'danger')
            return render_template('auth/registro_familiar.html', valores=_valores_formulario())

        usuario = Usuario(
            nombre_completo=nombre, correo=correo, telefono=telefono,
            rol='familiar', parentesco=parentesco or 'Familiar',
            avatar_inicial=nombre[0].upper(), avatar_color='#E2A33B',
            es_contacto_emergencia=es_contacto_emergencia, familia_id=familia.id,
        )
        usuario.set_password(contrasena)
        db.session.add(usuario)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('No se pudo crear la cuenta. Revisa si el correo ya fue registrado e inténtalo de nuevo.', 'danger')
            return render_template('auth/registro_familiar.html', valores=_valores_formulario()), 409

        adulto = familia.adulto_mayor()
        nombre_adulto = adulto.nombre_completo if adulto else 'tu familiar'
        login_user(usuario)
        flash(f'¡Bienvenido/a a My Remember! Ya estás acompañando a {nombre_adulto}.', 'success')
        return redirect(url_for('familiar.panel'))

    return render_template('auth/registro_familiar.html', valores={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        contrasena = request.form.get('contrasena', '')
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario and usuario.check_password(contrasena):
            login_user(usuario)
            destino = 'adulto.inicio' if usuario.es_adulto_mayor() else 'familiar.panel'
            return redirect(url_for(destino))

        flash('Correo o contraseña incorrectos. Inténtalo de nuevo.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Cerraste sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))
