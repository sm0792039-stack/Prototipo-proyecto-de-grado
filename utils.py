"""Utilidades de acceso, horarios, validación y seguimiento de My Remember."""
import secrets
import string
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import current_app, redirect, url_for, abort
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Recordatorio, RegistroRecordatorio, Alerta, Actividad, Familia

TIPOS_RECORDATORIO = ('medicamento', 'actividad', 'tarea')
REPETICIONES = ('una_vez', 'diario', 'semanal')
TIPOS_ACTIVIDAD = ('completado', 'omitido', 'pospuesto', 'programado', 'mensaje', 'cita', 'alerta')


def ahora_local():
    """Hora civil de la comunidad; las fechas de agenda nunca dependen del host."""
    return datetime.now(ZoneInfo(current_app.config.get('TIMEZONE', 'America/Bogota'))).replace(tzinfo=None)


def hoy_local():
    return ahora_local().date()


def fecha_local_desde_utc(momento):
    """Los timestamps de auditoría se guardan en UTC, sin zona, por compatibilidad."""
    zona = ZoneInfo(current_app.config.get('TIMEZONE', 'America/Bogota'))
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(zona).date()


def requiere_rol(rol_requerido):
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.rol != rol_requerido:
                abort(403)
            return f(*args, **kwargs)
        return envoltura
    return decorador


def generar_codigo_familia():
    """Código compartible de ocho caracteres generado con aleatoriedad segura."""
    alfabeto = ''.join(c for c in string.ascii_uppercase + string.digits if c not in '0O1I')
    while True:
        codigo = 'FAM-' + ''.join(secrets.choice(alfabeto) for _ in range(8))
        if not Familia.query.filter_by(codigo_familia=codigo).first():
            return codigo


def registrar_actividad(familia_id, descripcion, tipo):
    """Confirma la acción y su auditoría dentro de la misma transacción."""
    actividad = Actividad(familia_id=familia_id, descripcion=descripcion[:255], tipo=tipo)
    db.session.add(actividad)
    db.session.commit()
    return actividad


def corresponde_recordatorio(recordatorio, dia):
    inicio = fecha_local_desde_utc(recordatorio.fecha_creacion) if recordatorio.fecha_creacion else hoy_local()
    if dia < inicio:
        return False
    if recordatorio.repetir == 'una_vez':
        return dia == inicio
    if recordatorio.repetir == 'semanal':
        return dia.weekday() == inicio.weekday()
    return True


def asegurar_registros_hoy(familia_id):
    """Una ocurrencia por recordatorio y día; respeta frecuencia y fecha de alta."""
    hoy = hoy_local()
    recordatorios = Recordatorio.query.filter_by(familia_id=familia_id, activo=True).all()
    creado_alguno = False
    for r in recordatorios:
        if not corresponde_recordatorio(r, hoy):
            continue
        if RegistroRecordatorio.query.filter_by(recordatorio_id=r.id, fecha=hoy).first():
            continue
        # El índice único también protege frente a dos pestañas concurrentes.
        try:
            with db.session.begin_nested():
                db.session.add(RegistroRecordatorio(recordatorio_id=r.id, fecha=hoy,
                                                    hora_programada=r.hora, estado='pendiente'))
                db.session.flush()
            creado_alguno = True
        except IntegrityError:
            pass
    if creado_alguno:
        db.session.commit()


def verificar_alertas(familia_id):
    """Genera alertas internas al consultar la aplicación, sin duplicarlas."""
    asegurar_registros_hoy(familia_id)
    ahora = ahora_local()
    umbral = current_app.config.get('UMBRAL_ALERTA_MINUTOS', 30)
    registros = (RegistroRecordatorio.query.join(Recordatorio).filter(
        Recordatorio.familia_id == familia_id, Recordatorio.activo.is_(True),
        RegistroRecordatorio.fecha == ahora.date(),
        RegistroRecordatorio.estado.in_(['pendiente', 'pospuesto']),
        RegistroRecordatorio.alerta_descartada.is_(False)).all())
    cambio = False
    for registro in registros:
        limite = datetime.combine(registro.fecha, registro.hora_programada) + timedelta(minutes=umbral)
        if ahora <= limite or Alerta.query.filter_by(registro_id=registro.id, estado='activa').first():
            continue
        mensaje = f'{registro.recordatorio.nombre} · programado a las {formatear_hora(registro.hora_programada)}'
        db.session.add(Alerta(familia_id=familia_id, registro_id=registro.id, mensaje=mensaje[:255]))
        db.session.add(Actividad(familia_id=familia_id,
            descripcion=f'Alerta: no se ha confirmado "{registro.recordatorio.nombre}"'[:255], tipo='alerta'))
        cambio = True
    if cambio:
        db.session.commit()


def cerrar_alertas(registro):
    registro.alerta_descartada = True
    registro.urgente = False
    Alerta.query.filter_by(registro_id=registro.id, estado='activa').update({'estado': 'descartada'})


def construir_linea_tiempo(familia_id, dia):
    from models import Cita
    if dia == hoy_local():
        asegurar_registros_hoy(familia_id)
    registros = (RegistroRecordatorio.query.join(Recordatorio).filter(
        Recordatorio.familia_id == familia_id,
        or_(Recordatorio.activo.is_(True), RegistroRecordatorio.estado.in_(['completado', 'omitido'])),
        RegistroRecordatorio.fecha == dia).order_by(RegistroRecordatorio.hora_programada).all())
    citas = (Cita.query.filter(Cita.familia_id == familia_id, Cita.fecha == dia,
                              Cita.estado != 'cancelada').order_by(Cita.hora).all())
    eventos = [{
        'tipo': 'recordatorio', 'id': r.id, 'recordatorio_id': r.recordatorio_id,
        'hora': r.hora_programada, 'titulo': r.recordatorio.nombre,
        'subtitulo': r.recordatorio.notas, 'estado': r.estado,
        'icono': r.recordatorio.icono(), 'urgente': r.urgente,
        'inactivo': not r.recordatorio.activo,
    } for r in registros]
    eventos.extend({
        'tipo': 'cita', 'id': c.id, 'recordatorio_id': None, 'hora': c.hora,
        'titulo': c.titulo(), 'subtitulo': c.lugar_nombre, 'estado': c.estado,
        'icono': 'bi-calendar2-heart', 'urgente': False,
    } for c in citas)
    return sorted(eventos, key=lambda e: e['hora'])


def resumen_cumplimiento(eventos):
    recordatorios = [e for e in eventos if e['tipo'] == 'recordatorio']
    resumen = {estado: sum(e['estado'] == estado for e in recordatorios)
               for estado in ('completado', 'pendiente', 'pospuesto', 'omitido')}
    total = len(recordatorios)
    return {'total': total, 'completados': resumen['completado'],
            'pendientes': resumen['pendiente'], 'pospuestos': resumen['pospuesto'],
            'omitidos': resumen['omitido'],
            'porcentaje': round(resumen['completado'] * 100 / total) if total else 0}


def _texto(form, nombre, maximo, obligatorio=False):
    texto = form.get(nombre, '').strip()
    if obligatorio and not texto:
        raise ValueError('Completa los campos obligatorios.')
    if len(texto) > maximo:
        raise ValueError(f'El campo {nombre.replace("_", " ")} admite hasta {maximo} caracteres.')
    return texto


def validar_recordatorio(form):
    valores = {'nombre': _texto(form, 'nombre', 150, True),
               'notas': _texto(form, 'notas', 255) or None,
               'tipo': form.get('tipo', 'medicamento'),
               'repetir': form.get('repetir', 'diario')}
    if valores['tipo'] not in TIPOS_RECORDATORIO or valores['repetir'] not in REPETICIONES:
        raise ValueError('Selecciona un tipo y una frecuencia válidos.')
    try:
        valores['hora'] = datetime.strptime(form.get('hora', ''), '%H:%M').time()
    except ValueError:
        raise ValueError('La hora del recordatorio no es válida.') from None
    return valores


def validar_cita(form):
    valores = {'especialidad': _texto(form, 'especialidad', 100, True),
               'doctor_nombre': _texto(form, 'doctor_nombre', 120) or None,
               'lugar_nombre': _texto(form, 'lugar_nombre', 150) or None,
               'direccion': _texto(form, 'direccion', 255) or None,
               'notas': _texto(form, 'notas', 2000) or None}
    valores.update(validar_fecha_hora_cita(form))
    return valores


def validar_fecha_hora_cita(form):
    try:
        fecha = datetime.strptime(form.get('fecha', ''), '%Y-%m-%d').date()
        hora = datetime.strptime(form.get('hora', ''), '%H:%M').time()
    except ValueError:
        raise ValueError('La fecha o la hora de la cita no es válida.') from None
    if datetime.combine(fecha, hora) <= ahora_local():
        raise ValueError('Selecciona una fecha y hora futuras para la cita.')
    return {'fecha': fecha, 'hora': hora}


def actualizar_recordatorio(recordatorio, valores):
    cambio_horario = recordatorio.hora != valores['hora']
    for campo, valor in valores.items():
        setattr(recordatorio, campo, valor)
    registro = RegistroRecordatorio.query.filter_by(recordatorio_id=recordatorio.id,
                                                    fecha=hoy_local()).first()
    if registro and registro.estado in ('pendiente', 'pospuesto'):
        if not corresponde_recordatorio(recordatorio, hoy_local()):
            # Cambiar la frecuencia puede quitar la ocurrencia de hoy. Nunca
            # se elimina una respuesta ya completada u omitida del historial.
            cerrar_alertas(registro)
            db.session.delete(registro)
        elif cambio_horario:
            registro.hora_programada = recordatorio.hora
            registro.estado = 'pendiente'
            registro.alerta_descartada = False
            registro.urgente = False
            Alerta.query.filter_by(registro_id=registro.id, estado='activa').update({'estado': 'descartada'})


def desactivar_recordatorio(recordatorio):
    recordatorio.activo = False
    for registro in recordatorio.registros:
        if registro.estado in ('pendiente', 'pospuesto'):
            cerrar_alertas(registro)


_DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
_MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def formatear_fecha_larga(fecha):
    return f'{_DIAS_ES[fecha.weekday()]}, {fecha.day} de {_MESES_ES[fecha.month - 1]}'


def formatear_fecha_corta(fecha):
    return f'{fecha.day} de {_MESES_ES[fecha.month - 1]}'


def formatear_hora(hora):
    periodo = 'a. m.' if hora.hour < 12 else 'p. m.'
    return f'{hora.hour % 12 or 12}:{hora.minute:02d} {periodo}'


def tiempo_transcurrido(momento):
    if momento is None:
        return 'sin registros aún'
    ahora = datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    segundos = max(0, (ahora - momento).total_seconds())
    if segundos < 60:
        return 'hace un momento'
    minutos = int(segundos // 60)
    if minutos < 60:
        return f'hace {minutos} min'
    horas = int(minutos // 60)
    if horas < 24:
        return f'hace {horas} h'
    dias = int(horas // 24)
    return f'hace {dias} día{"s" if dias != 1 else ""}'


def evento_mas_importante(eventos, ahora):
    # Una cita cuya hora ya pasó permanece en la agenda, pero no desplaza
    # una tarea por atender ni la siguiente cita de hoy.
    pendientes = [e for e in eventos if
        (e['tipo'] == 'recordatorio' and e['estado'] in ('pendiente', 'pospuesto')) or
        (e['tipo'] == 'cita' and e['estado'] in ('pendiente', 'confirmada') and e['hora'] >= ahora)]
    if not pendientes:
        return None
    vencidos = [e for e in pendientes if e['hora'] <= ahora]
    return vencidos[0] if vencidos else pendientes[0]
