"""Conversación familiar y código de invitación, compartidos por ambos roles.

El grupo conserva el alcance del piloto: un adulto mayor y varios cuidadores.
Todas las lecturas y escrituras se limitan a la familia de la sesión.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Actividad, Mensaje, MensajeOculto, Usuario
from utils import generar_codigo_familia


comunidad_bp = Blueprint('comunidad', __name__)


def normalizar_codigo(codigo):
    """Admite un código pegado con espacios, minúsculas o sin el guion."""
    compacto = ''.join(codigo.upper().split()).replace('-', '').replace('–', '').replace('—', '')
    if compacto.startswith('FAM'):
        return 'FAM-' + compacto[3:]
    return compacto


def visible_messages(usuario):
    """Consulta base: nunca devolver mensajes de otras familias u ocultos."""
    return Mensaje.query.filter(
        Mensaje.familia_id == usuario.familia_id,
        ~Mensaje.ocultaciones.any(usuario_id=usuario.id),
    )


def guardar_mensaje(usuario, contenido):
    """Valida y guarda mensaje e historial en una única transacción."""
    contenido = contenido.strip()
    if not contenido:
        raise ValueError('Escribe un mensaje antes de enviarlo.')
    if len(contenido) > 500:
        raise ValueError('El mensaje puede tener hasta 500 caracteres.')
    if not Usuario.query.filter(
        Usuario.familia_id == usuario.familia_id, Usuario.id != usuario.id,
    ).first():
        raise ValueError('Primero vincula a un familiar o cuidador con tu código de familia.')
    mensaje = Mensaje(
        familia_id=usuario.familia_id, remitente_id=usuario.id, contenido=contenido,
    )
    db.session.add(mensaje)
    # No copiar el contenido en el historial: al borrar para todos no debe
    # sobrevivir una segunda copia del texto en esa pantalla.
    db.session.add(Actividad(
        familia_id=usuario.familia_id,
        descripcion=f'{usuario.nombre_completo} envió un mensaje a su familia',
        tipo='mensaje',
    ))
    db.session.commit()
    return mensaje


@comunidad_bp.route('/mensajes')
@login_required
def mensajes():
    pagination = visible_messages(current_user).order_by(
        Mensaje.fecha_envio.desc(), Mensaje.id.desc(),
    ).paginate(page=request.args.get('page', 1, type=int), per_page=50, error_out=False)
    otros = Usuario.query.filter(
        Usuario.familia_id == current_user.familia_id, Usuario.id != current_user.id,
    ).order_by(Usuario.nombre_completo).all()
    return render_template(
        'comunidad/mensajes.html', mensajes=list(reversed(pagination.items)),
        pagination=pagination, otros_miembros=otros, puede_enviar=bool(otros),
    )


@comunidad_bp.route('/mensajes/enviar', methods=['POST'])
@login_required
def enviar_mensaje():
    try:
        guardar_mensaje(current_user, request.form.get('contenido', ''))
    except ValueError as error:
        flash(str(error), 'danger')
    else:
        flash('Mensaje enviado a tu familia.', 'success')
    return redirect(url_for('comunidad.mensajes'))


@comunidad_bp.route('/mensajes/<int:mensaje_id>/eliminar', methods=['POST'])
@login_required
def eliminar_mensaje(mensaje_id):
    mensaje = Mensaje.query.filter_by(
        id=mensaje_id, familia_id=current_user.familia_id,
    ).first_or_404()
    alcance = request.form.get('alcance', '')
    if alcance == 'para_todos':
        if mensaje.remitente_id != current_user.id:
            abort(403)
        db.session.delete(mensaje)
        db.session.commit()
        flash('Mensaje eliminado para todos los miembros de tu familia.', 'success')
    elif alcance == 'para_mi':
        if db.session.get(MensajeOculto, (mensaje.id, current_user.id)) is None:
            db.session.add(MensajeOculto(mensaje_id=mensaje.id, usuario_id=current_user.id))
            try:
                db.session.commit()
            except IntegrityError:
                # Un doble clic o dos pestañas pueden ocultar la misma fila.
                db.session.rollback()
        flash('Mensaje eliminado de tu vista. Tu familia puede seguir viéndolo.', 'info')
    else:
        abort(400)
    return redirect(url_for('comunidad.mensajes'))


@comunidad_bp.route('/familia/codigo/renovar', methods=['POST'])
@login_required
def regenerar_codigo():
    if not current_user.es_adulto_mayor():
        abort(403)
    current_user.familia.codigo_familia = generar_codigo_familia()
    db.session.commit()
    flash(
        'Tu nuevo código ya está disponible. El anterior dejó de funcionar; '
        'tus familiares vinculados conservan el acceso.', 'success',
    )
    return redirect(url_for('adulto.familia'))
