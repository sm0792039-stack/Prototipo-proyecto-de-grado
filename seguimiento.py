"""Actualizaciones discretas entre cuentas de una misma familia."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from models import Actividad, Alerta, Cita, Recordatorio, RegistroRecordatorio, Usuario

seguimiento_bp = Blueprint('seguimiento', __name__)


def version_familia(user):
    from blueprints.comunidad import visible_messages
    from utils import ahora_local
    familia_id = user.familia_id
    ahora = ahora_local()
    # La huella cambia con altas, ediciones y borrados; su contenido no se envía.
    datos = {
        'dia': ahora.date(),
        'codigo': user.familia.codigo_familia,
        'miembros': [(u.id, u.nombre_completo, u.telefono) for u in
                     Usuario.query.filter_by(familia_id=familia_id).order_by(Usuario.id)],
        'mensajes': [(m.id, m.contenido) for m in
                     visible_messages(user).order_by(None).order_by('id').all()],
        'recordatorios': [(r.id, r.nombre, r.hora, r.repetir, r.notas, r.activo) for r in
                          Recordatorio.query.filter_by(familia_id=familia_id).order_by(Recordatorio.id)],
        'registros': [(r.id, r.estado, r.fecha, r.hora_programada, r.urgente,
                       datetime.combine(r.fecha, r.hora_programada) <= ahora) for r in
                      RegistroRecordatorio.query.join(Recordatorio).filter(
                          Recordatorio.familia_id == familia_id,
                          RegistroRecordatorio.fecha >= ahora.date() - timedelta(days=7),
                      ).order_by(RegistroRecordatorio.id)],
        'citas': [(c.id, c.especialidad, c.doctor_nombre, c.fecha, c.hora, c.estado, c.notas,
                   c.lugar_nombre, c.direccion, datetime.combine(c.fecha, c.hora) <= ahora) for c in
                  Cita.query.filter_by(familia_id=familia_id).order_by(Cita.id)],
        'alertas': [(a.id, a.estado) for a in
                    Alerta.query.filter_by(familia_id=familia_id).order_by(Alerta.id)],
        'actividad': [(a.id,) for a in Actividad.query.filter_by(familia_id=familia_id)
                      .order_by(Actividad.id.desc()).limit(50)],
    }
    return sha256(json.dumps(datos, default=str, sort_keys=True).encode()).hexdigest()


@seguimiento_bp.get('/api/estado')
@login_required
def estado():
    from utils import verificar_alertas
    verificar_alertas(current_user.familia_id)
    return jsonify(
        version=version_familia(current_user),
        actualizado_en=datetime.now(ZoneInfo(current_app.config['TIMEZONE'])).isoformat(),
    )
