"""Plan compartido, seguimiento y auditoría para familiares/cuidadores."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user
from sqlalchemy import and_, or_

from extensions import db
from models import Recordatorio, RegistroRecordatorio, Cita, Mensaje, Actividad, Alerta
from blueprints.comunidad import visible_messages
from utils import (requiere_rol, verificar_alertas, construir_linea_tiempo,
    registrar_actividad, tiempo_transcurrido, ahora_local, hoy_local, resumen_cumplimiento,
    validar_recordatorio, validar_cita, actualizar_recordatorio, desactivar_recordatorio,
    TIPOS_ACTIVIDAD)

familiar_bp = Blueprint('familiar', __name__, url_prefix='/familiar')


@familiar_bp.route('/panel')
@requiere_rol('familiar')
def panel():
    familia_id = current_user.familia_id
    verificar_alertas(familia_id)
    hoy = hoy_local()
    eventos = construir_linea_tiempo(familia_id, hoy)
    resumen = resumen_cumplimiento(eventos)
    alertas = (Alerta.query.filter_by(familia_id=familia_id, estado='activa')
               .order_by(Alerta.fecha_creacion.desc()).all())
    ultimo = (RegistroRecordatorio.query.join(Recordatorio).filter(
        Recordatorio.familia_id == familia_id, RegistroRecordatorio.estado == 'completado')
        .order_by(RegistroRecordatorio.hora_confirmacion.desc()).first())
    estado = 'atencion' if alertas or resumen['omitidos'] else ('sin_plan' if not resumen['total'] else 'sin_alertas')
    return render_template('familiar/panel.html', eventos=eventos, alertas=alertas,
        adulto=current_user.familia.adulto_mayor(), estado_general=estado,
        texto_ultima_confirmacion=tiempo_transcurrido(ultimo.hora_confirmacion if ultimo else None),
        resumen=resumen, hoy=hoy, ultima_actualizacion=ahora_local())


@familiar_bp.route('/plan-cuidado')
@requiere_rol('familiar')
def plan_cuidado():
    hoy, ahora = hoy_local(), ahora_local().time()
    recordatorios = (Recordatorio.query.filter_by(familia_id=current_user.familia_id, activo=True)
                     .order_by(Recordatorio.hora).all())
    citas = (Cita.query.filter(Cita.familia_id == current_user.familia_id, Cita.estado != 'cancelada',
        or_(Cita.fecha > hoy, and_(Cita.fecha == hoy, Cita.hora >= ahora)))
        .order_by(Cita.fecha, Cita.hora).all())
    return render_template('familiar/plan_cuidado.html', recordatorios=recordatorios, citas=citas, hoy=hoy)


@familiar_bp.route('/plan-cuidado/recordatorio/nuevo', methods=['POST'])
@requiere_rol('familiar')
def nuevo_recordatorio():
    adulto = current_user.familia.adulto_mayor()
    if not adulto:
        flash('No hay un adulto mayor vinculado a esta familia.', 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    try:
        valores = validar_recordatorio(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    recordatorio = Recordatorio(familia_id=current_user.familia_id, adulto_mayor_id=adulto.id,
                               creado_por_id=current_user.id, **valores)
    db.session.add(recordatorio)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} agregó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio guardado.', 'success')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/plan-cuidado/recordatorio/<int:recordatorio_id>/editar', methods=['POST'])
@requiere_rol('familiar')
def editar_recordatorio(recordatorio_id):
    recordatorio = Recordatorio.query.filter_by(id=recordatorio_id,
        familia_id=current_user.familia_id, activo=True).first_or_404()
    try:
        valores = validar_recordatorio(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    actualizar_recordatorio(recordatorio, valores)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} actualizó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio actualizado.', 'success')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/plan-cuidado/recordatorio/<int:recordatorio_id>/eliminar', methods=['POST'])
@requiere_rol('familiar')
def eliminar_recordatorio(recordatorio_id):
    recordatorio = Recordatorio.query.filter_by(id=recordatorio_id,
        familia_id=current_user.familia_id, activo=True).first_or_404()
    desactivar_recordatorio(recordatorio)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} desactivó el recordatorio "{recordatorio.nombre}"', 'programado')
    flash('Recordatorio eliminado. Se conserva su historial.', 'info')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/plan-cuidado/cita/nueva', methods=['POST'])
@requiere_rol('familiar')
def nueva_cita():
    adulto = current_user.familia.adulto_mayor()
    if not adulto:
        flash('No hay un adulto mayor vinculado a esta familia.', 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    try:
        valores = validar_cita(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    cita = Cita(familia_id=current_user.familia_id, adulto_mayor_id=adulto.id,
                creado_por_id=current_user.id, **valores)
    db.session.add(cita)
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} agendó una cita de {cita.especialidad}', 'cita')
    flash('Cita médica guardada.', 'success')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/plan-cuidado/cita/<int:cita_id>/editar', methods=['POST'])
@requiere_rol('familiar')
def editar_cita(cita_id):
    cita = Cita.query.filter_by(id=cita_id, familia_id=current_user.familia_id).first_or_404()
    try:
        valores = validar_cita(request.form)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('familiar.plan_cuidado'))
    for campo, valor in valores.items():
        setattr(cita, campo, valor)
    cita.estado = 'confirmada'
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} actualizó la cita de {cita.especialidad}', 'cita')
    flash('Cita actualizada.', 'success')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/plan-cuidado/cita/<int:cita_id>/eliminar', methods=['POST'])
@requiere_rol('familiar')
def eliminar_cita(cita_id):
    cita = Cita.query.filter_by(id=cita_id, familia_id=current_user.familia_id).first_or_404()
    if cita.estado != 'cancelada':
        cita.estado = 'cancelada'
        registrar_actividad(current_user.familia_id,
            f'{current_user.nombre_completo} canceló la cita de {cita.especialidad}', 'cita')
    flash('Cita cancelada. Se conserva su historial.', 'info')
    return redirect(url_for('familiar.plan_cuidado'))


@familiar_bp.route('/historial')
@requiere_rol('familiar')
def historial():
    filtros = {campo: request.args.get(campo, '').strip() for campo in ('desde', 'hasta', 'tipo')}
    consulta = Actividad.query.filter_by(familia_id=current_user.familia_id)
    fechas = {}
    for campo in ('desde', 'hasta'):
        if not filtros[campo]:
            continue
        try:
            fecha = datetime.strptime(filtros[campo], '%Y-%m-%d').date()
            if fecha.year > 9998:
                raise ValueError('Fecha fuera de rango')
            fechas[campo] = fecha
        except ValueError:
            filtros[campo] = ''
            flash('Se ignoró una fecha de filtro no válida.', 'warning')
    if 'desde' in fechas and 'hasta' in fechas and fechas['desde'] > fechas['hasta']:
        flash('La fecha inicial no puede ser posterior a la fecha final.', 'warning')
        fechas = {}
        filtros['desde'] = filtros['hasta'] = ''
    zona = ZoneInfo(current_app.config.get('TIMEZONE', 'America/Bogota'))
    for campo, fecha in fechas.items():
        if campo == 'hasta':
            fecha += timedelta(days=1)
        limite = datetime.combine(fecha, time.min, tzinfo=zona).astimezone(timezone.utc).replace(tzinfo=None)
        consulta = consulta.filter(Actividad.fecha_hora >= limite) if campo == 'desde' else consulta.filter(Actividad.fecha_hora < limite)
    if filtros['tipo'] in TIPOS_ACTIVIDAD:
        consulta = consulta.filter_by(tipo=filtros['tipo'])
    else:
        filtros['tipo'] = ''
    actividades = consulta.order_by(Actividad.fecha_hora.desc(), Actividad.id.desc()).limit(200).all()
    mensajes = visible_messages(current_user).order_by(Mensaje.fecha_envio.desc(), Mensaje.id.desc()).limit(50).all()
    return render_template('familiar/historial.html', actividades=actividades, mensajes=mensajes,
                           filtros=filtros, tipos=TIPOS_ACTIVIDAD)


@familiar_bp.route('/historial/mensaje', methods=['POST'])
@requiere_rol('familiar')
def enviar_mensaje():
    # Compatibilidad con formularios de versiones anteriores.
    from blueprints.comunidad import enviar_mensaje as enviar_compartido
    return enviar_compartido()


@familiar_bp.route('/alertas/<int:alerta_id>/recordatorio-push', methods=['POST'])
@requiere_rol('familiar')
def enviar_recordatorio_push(alerta_id):
    alerta = Alerta.query.filter_by(id=alerta_id, familia_id=current_user.familia_id).first_or_404()
    registro = alerta.registro
    if alerta.estado != 'activa' or not registro or registro.estado not in ('pendiente', 'pospuesto') or registro.fecha != hoy_local():
        flash('Esta alerta ya no requiere un recordatorio.', 'info')
        return redirect(url_for('familiar.panel'))
    registro.urgente = True
    registrar_actividad(current_user.familia_id,
        f'{current_user.nombre_completo} resaltó el recordatorio "{registro.recordatorio.nombre}"', 'alerta')
    flash('Se resaltó el recordatorio en la pantalla de tu familiar.', 'success')
    return redirect(url_for('familiar.panel'))


@familiar_bp.route('/alertas/<int:alerta_id>/descartar', methods=['POST'])
@requiere_rol('familiar')
def descartar_alerta(alerta_id):
    alerta = Alerta.query.filter_by(id=alerta_id, familia_id=current_user.familia_id).first_or_404()
    alerta.estado = 'descartada'
    if alerta.registro:
        alerta.registro.alerta_descartada = True
        alerta.registro.urgente = False
    db.session.commit()
    flash('Alerta descartada. El recordatorio conserva su estado.', 'info')
    return redirect(url_for('familiar.panel'))
