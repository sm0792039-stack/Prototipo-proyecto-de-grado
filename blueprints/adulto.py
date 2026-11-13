"""Agenda y seguimiento personal del adulto mayor."""
from datetime import datetime, timedelta, timezone, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user
from sqlalchemy import and_, or_

from extensions import db
from models import RegistroRecordatorio, Recordatorio, Cita, Usuario
from blueprints.comunidad import visible_messages
from utils import (requiere_rol, verificar_alertas, construir_linea_tiempo,
    evento_mas_importante, registrar_actividad, ahora_local, hoy_local,
    validar_recordatorio, validar_cita, validar_fecha_hora_cita,
    actualizar_recordatorio, desactivar_recordatorio, cerrar_alertas)

adulto_bp = Blueprint('adulto', __name__, url_prefix='/adulto')


def _registro_del_adulto(registro_id):
    return (RegistroRecordatorio.query.join(Recordatorio).filter(
        RegistroRecordatorio.id == registro_id,
        Recordatorio.familia_id == current_user.familia_id,
        Recordatorio.adulto_mayor_id == current_user.id,
        Recordatorio.activo.is_(True), RegistroRecordatorio.fecha == hoy_local()).first_or_404())


def _volver_recordatorios():
    destino = 'adulto.inicio' if request.form.get('volver') == 'inicio' else 'adulto.recordatorios'
    return redirect(url_for(destino))


@adulto_bp.route('/inicio')
@requiere_rol('adulto_mayor')
def inicio():
    verificar_alertas(current_user.familia_id)
    hoy, ahora = hoy_local(), ahora_local().time()
    eventos = construir_linea_tiempo(current_user.familia_id, hoy)
    # Solo se destaca un mensaje recibido que no haya sido ocultado/borrado.
    from models import Mensaje
    ultimo_mensaje = (visible_messages(current_user).filter(Mensaje.remitente_id != current_user.id)
        .order_by(Mensaje.fecha_envio.desc(), Mensaje.id.desc()).first())
    return render_template('adulto/inicio.html', eventos=eventos,
        destacado=evento_mas_importante(eventos, ahora), ultimo_mensaje=ultimo_mensaje, hoy=hoy, ahora=ahora)


@adulto_bp.route('/recordatorios')
@requiere_rol('adulto_mayor')
def recordatorios():
    verificar_alertas(current_user.familia_id)
    hoy, ahora = hoy_local(), ahora_local().time()
    eventos = [e for e in construir_linea_tiempo(current_user.familia_id, hoy) if e['tipo'] == 'recordatorio']
    lista = (Recordatorio.query.filter_by(familia_id=current_user.familia_id, activo=True)
             .order_by(Recordatorio.hora).all())
    return render_template('adulto/recordatorios.html', eventos=eventos, ahora=ahora, recordatorios=lista, hoy=hoy)


@adulto_bp.route('/recordatorios/<int:registro_id>/confirmar', methods=['POST'])
@requiere_rol('adulto_mayor')
def confirmar_recordatorio(registro_id):
    registro = _registro_del_adulto(registro_id)
    if registro.estado in ('completado', 'omitido'):
        flash('Este recordatorio ya tiene una respuesta guardada.', 'info')
        return _volver_recordatorios()
    registro.estado = 'completado'
    registro.hora_confirmacion = datetime.now(timezone.utc).replace(tzinfo=None)
    cerrar_alertas(registro)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} completó "{registro.recordatorio.nombre}"', 'completado')
    flash(f'"{registro.recordatorio.nombre}" quedó marcado como hecho.', 'success')
    return _volver_recordatorios()


@adulto_bp.route('/recordatorios/<int:registro_id>/posponer', methods=['POST'])
@requiere_rol('adulto_mayor')
def posponer_recordatorio(registro_id):
    registro = _registro_del_adulto(registro_id)
    if registro.estado in ('completado', 'omitido'):
        flash('Este recordatorio ya tiene una respuesta guardada.', 'info')
        return _volver_recordatorios()
    minutos = current_app.config.get('MINUTOS_POSPONER', 15)
    nueva_fecha_hora = ahora_local() + timedelta(minutes=minutos)
    if nueva_fecha_hora.date() != registro.fecha:
        flash('No es posible posponer este recordatorio más allá de medianoche.', 'warning')
        return _volver_recordatorios()
    registro.hora_programada = nueva_fecha_hora.time().replace(second=0, microsecond=0)
    registro.estado = 'pospuesto'
    cerrar_alertas(registro)
    registro.alerta_descartada = False
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} pospuso "{registro.recordatorio.nombre}" {minutos} minutos', 'pospuesto')
    flash(f'Listo. La nueva hora es {registro.hora_programada.strftime("%H:%M")}.', 'info')
    return _volver_recordatorios()


@adulto_bp.route('/recordatorios/<int:registro_id>/omitir', methods=['POST'])
@requiere_rol('adulto_mayor')
def omitir_recordatorio(registro_id):
    registro = _registro_del_adulto(registro_id)
    if registro.estado not in ('completado', 'omitido'):
        registro.estado = 'omitido'
        registro.hora_confirmacion = datetime.now(timezone.utc).replace(tzinfo=None)
        cerrar_alertas(registro)
        registrar_actividad(current_user.familia_id,
            f'{current_user.nombre_completo} indicó que no realizó "{registro.recordatorio.nombre}"', 'omitido')
        flash('Se guardó que no realizaste este recordatorio. Tu cuidador podrá verlo.', 'info')
    return _volver_recordatorios()


@adulto_bp.route('/recordatorios/nuevo', methods=['POST'])
@requiere_rol('adulto_mayor')
def nuevo_recordatorio():
    try:
        valores = validar_recordatorio(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('adulto.recordatorios'))
    recordatorio = Recordatorio(familia_id=current_user.familia_id, adulto_mayor_id=current_user.id,
        creado_por_id=current_user.id, **valores)
    db.session.add(recordatorio)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} agregó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio guardado.', 'success')
    return redirect(url_for('adulto.recordatorios'))


@adulto_bp.route('/recordatorios/<int:recordatorio_id>/editar', methods=['POST'])
@requiere_rol('adulto_mayor')
def editar_recordatorio(recordatorio_id):
    recordatorio = Recordatorio.query.filter_by(id=recordatorio_id, familia_id=current_user.familia_id,
        adulto_mayor_id=current_user.id, activo=True).first_or_404()
    try:
        valores = validar_recordatorio(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('adulto.recordatorios'))
    actualizar_recordatorio(recordatorio, valores)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} actualizó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio actualizado.', 'success')
    return redirect(url_for('adulto.recordatorios'))


@adulto_bp.route('/recordatorios/<int:recordatorio_id>/eliminar', methods=['POST'])
@requiere_rol('adulto_mayor')
def eliminar_recordatorio(recordatorio_id):
    recordatorio = Recordatorio.query.filter_by(id=recordatorio_id, familia_id=current_user.familia_id,
        adulto_mayor_id=current_user.id, activo=True).first_or_404()
    desactivar_recordatorio(recordatorio)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} desactivó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio eliminado. Se conserva su historial.', 'info')
    return redirect(url_for('adulto.recordatorios'))


@adulto_bp.route('/citas')
@requiere_rol('adulto_mayor')
def citas():
    hoy, ahora = hoy_local(), ahora_local().time()
    tab = 'pasadas' if request.args.get('tab') == 'pasadas' else 'proximas'
    consulta = Cita.query.filter_by(familia_id=current_user.familia_id)
    if tab == 'pasadas':
        consulta = consulta.filter(or_(Cita.fecha < hoy, and_(Cita.fecha == hoy, Cita.hora < ahora), Cita.estado == 'cancelada'))
        lista = consulta.order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    else:
        consulta = consulta.filter(Cita.estado != 'cancelada',
            or_(Cita.fecha > hoy, and_(Cita.fecha == hoy, Cita.hora >= ahora)))
        lista = consulta.order_by(Cita.fecha, Cita.hora).all()
    return render_template('adulto/citas.html', citas=lista, tab=tab, hoy=hoy, manana=hoy + timedelta(days=1))


@adulto_bp.route('/citas/nueva', methods=['POST'])
@requiere_rol('adulto_mayor')
def nueva_cita():
    try:
        valores = validar_cita(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('adulto.citas'))
    cita = Cita(familia_id=current_user.familia_id, adulto_mayor_id=current_user.id,
                creado_por_id=current_user.id, **valores)
    db.session.add(cita)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} agendó una cita de {cita.especialidad}', 'cita')
    flash('Cita médica guardada.', 'success')
    return redirect(url_for('adulto.citas'))


@adulto_bp.route('/citas/<int:cita_id>/editar', methods=['POST'])
@requiere_rol('adulto_mayor')
def editar_cita(cita_id):
    cita = Cita.query.filter_by(id=cita_id, familia_id=current_user.familia_id).first_or_404()
    try:
        valores = validar_cita(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('adulto.citas'))
    for campo, valor in valores.items():
        setattr(cita, campo, valor)
    cita.estado = 'confirmada'
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} actualizó la cita de {cita.especialidad}', 'cita')
    flash('Cita actualizada.', 'success')
    return redirect(url_for('adulto.citas'))


@adulto_bp.route('/citas/<int:cita_id>/reprogramar', methods=['POST'])
@requiere_rol('adulto_mayor')
def reprogramar_cita(cita_id):
    cita = Cita.query.filter_by(id=cita_id, familia_id=current_user.familia_id).first_or_404()
    try:
        valores = validar_fecha_hora_cita(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('adulto.citas'))
    cita.fecha, cita.hora, cita.estado = valores['fecha'], valores['hora'], 'confirmada'
    registrar_actividad(current_user.familia_id,
        f'Se reprogramó la cita de {cita.especialidad} para el {cita.fecha.strftime("%d/%m/%Y")}', 'cita')
    flash('Tu cita fue reprogramada correctamente.', 'success')
    return redirect(url_for('adulto.citas'))


@adulto_bp.route('/citas/<int:cita_id>/eliminar', methods=['POST'])
@requiere_rol('adulto_mayor')
def eliminar_cita(cita_id):
    cita = Cita.query.filter_by(id=cita_id, familia_id=current_user.familia_id).first_or_404()
    if cita.estado != 'cancelada':
        cita.estado = 'cancelada'
        registrar_actividad(current_user.familia_id,
            f'{current_user.nombre_completo} canceló la cita de {cita.especialidad}', 'cita')
    flash('Cita cancelada. Se conserva en el historial.', 'info')
    return redirect(url_for('adulto.citas'))


@adulto_bp.route('/familia')
@requiere_rol('adulto_mayor')
def familia():
    from models import Mensaje
    contactos = Usuario.query.filter_by(familia_id=current_user.familia_id, rol='familiar').all()
    mensajes = visible_messages(current_user).order_by(Mensaje.fecha_envio.desc(), Mensaje.id.desc()).limit(50).all()
    return render_template('adulto/familia.html', contactos=contactos, mensajes=mensajes)
