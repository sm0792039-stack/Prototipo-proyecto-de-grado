"""Flujos funcionales y aislamiento familiar; no usan datos personales ni MySQL real."""
from datetime import datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
import re
import sys

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models import (
    Actividad, Alerta, Cita, Familia, Mensaje, MensajeOculto,
    Recordatorio, RegistroRecordatorio, Usuario,
)
import utils
import blueprints.adulto as adulto_routes
import blueprints.familiar as familiar_routes

PASSWORD = 'PruebaSegura2026!'
PASSWORD_HASH = generate_password_hash(PASSWORD)
FIXED_NOW = datetime(2026, 11, 11, 12, 0)


@pytest.fixture
def app():
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-only-secret-key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'LOGIN_RATE_LIMIT_ENABLED': False,
        'TIMEZONE': 'America/Bogota',
    })
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def fixed_clock(monkeypatch):
    def set_time(moment):
        monkeypatch.setattr(utils, 'ahora_local', lambda: moment)
        monkeypatch.setattr(adulto_routes, 'ahora_local', lambda: moment, raising=False)
        monkeypatch.setattr(familiar_routes, 'ahora_local', lambda: moment, raising=False)
    set_time(FIXED_NOW)
    return set_time


@pytest.fixture
def families(app):
    """Dos familias independientes; los IDs ayudan a probar intentos cruzados."""
    result = []
    with app.app_context():
        for suffix in ('a', 'b'):
            family = Familia(codigo_familia=f'FAM-TEST{suffix.upper()}234')
            db.session.add(family)
            db.session.flush()
            adult = Usuario(
                nombre_completo=f'Adulto {suffix.upper()}', correo=f'adulto-{suffix}@example.com',
                contrasena_hash=PASSWORD_HASH, rol='adulto_mayor', familia_id=family.id,
            )
            caregiver = Usuario(
                nombre_completo=f'Cuidador {suffix.upper()}', correo=f'cuidador-{suffix}@example.com',
                contrasena_hash=PASSWORD_HASH, rol='familiar', familia_id=family.id,
            )
            db.session.add_all([adult, caregiver])
            db.session.flush()
            result.append(SimpleNamespace(id=family.id, adult=adult.id, caregiver=caregiver.id,
                                          code=family.codigo_familia))
        db.session.commit()
    return result


def logged_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    return client


def registration(email='nueva@example.com', name='Ana Prueba', **extra):
    values = {
        'nombre_completo': name, 'correo': email, 'telefono': '3000000000',
        'contrasena': PASSWORD, 'confirmar_contrasena': PASSWORD,
    }
    values.update(extra)
    return values


def create_reminder(family, **extra):
    values = {
        'familia_id': family.id, 'adulto_mayor_id': family.adult,
        'creado_por_id': family.caregiver, 'nombre': 'Actividad de prueba',
        'tipo': 'actividad', 'hora': time(8), 'repetir': 'diario',
        'fecha_creacion': datetime(2026, 11, 11, 12),
    }
    values.update(extra)
    reminder = Recordatorio(**values)
    db.session.add(reminder)
    db.session.flush()
    return reminder


def create_occurrence(family, **extra):
    reminder = create_reminder(family)
    values = {'recordatorio_id': reminder.id, 'fecha': FIXED_NOW.date(),
              'hora_programada': time(8), 'estado': 'pendiente'}
    values.update(extra)
    occurrence = RegistroRecordatorio(**values)
    db.session.add(occurrence)
    db.session.commit()
    return occurrence


def test_registration_code_remains_visible_after_caregiver_joins(app):
    adult_client = app.test_client()
    response = adult_client.post('/registro/adulto', data=registration(), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        adult = Usuario.query.filter_by(correo='nueva@example.com').one()
        code, family_id = adult.familia.codigo_familia, adult.familia_id
    assert code.encode() in adult_client.get('/adulto/inicio').data
    assert code.encode() in adult_client.get('/adulto/familia').data

    caregiver_client = app.test_client()
    response = caregiver_client.post('/registro/familiar', data=registration(
        email='hija@example.com', name='Hija Prueba', parentesco='Hija',
        codigo_familia='  ' + code.lower().replace('-', '') + '  ',
    ), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(correo='hija@example.com').one().familia_id == family_id
        assert Familia.query.count() == 1
    page = adult_client.get('/adulto/familia').data
    assert code.encode() in page
    assert b'Hija Prueba' in page
    # La visibilidad ya no depende del aviso temporal de bienvenida.
    assert code.encode() in adult_client.get('/adulto/inicio').data


def test_invalid_family_code_does_not_create_account(app):
    response = app.test_client().post('/registro/familiar', data=registration(
        codigo_familia='FAM-NOEXISTE', parentesco='Cuidador',
    ), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Usuario.query.count() == 0
        assert Familia.query.count() == 0


@pytest.mark.parametrize('invalid', [
    {'correo': 'no-es-correo'}, {'nombre_completo': 'A'},
    {'contrasena': '1234567', 'confirmar_contrasena': '1234567'},
    {'correo': 'x' * 121 + '@example.com'},
])
def test_registration_validates_on_server(app, invalid):
    app.test_client().post('/registro/adulto', data=registration(**invalid))
    with app.app_context():
        assert Usuario.query.count() == 0
        assert Familia.query.count() == 0


def test_both_roles_can_send_and_read_messages(app, families):
    family = families[0]
    adult = logged_client(app, family.adult)
    caregiver = logged_client(app, family.caregiver)
    assert adult.post('/mensajes/enviar', data={'contenido': 'Respuesta del adulto'}).status_code == 302
    assert caregiver.post('/mensajes/enviar', data={'contenido': 'Saludo del cuidador'}).status_code == 302
    for client in (adult, caregiver):
        page = client.get('/mensajes')
        assert page.status_code == 200
        assert b'Respuesta del adulto' in page.data
        assert b'Saludo del cuidador' in page.data
        assert b'Adulto A' in page.data
        assert b'Cuidador A' in page.data
    with app.app_context():
        assert Mensaje.query.filter_by(familia_id=family.id).count() == 2
        assert not any('Respuesta del adulto' in activity.descripcion
                       for activity in Actividad.query.all())


def test_message_delete_for_me_and_for_everyone_have_distinct_permissions(app, families):
    family = families[0]
    adult = logged_client(app, family.adult)
    caregiver = logged_client(app, family.caregiver)
    adult.post('/mensajes/enviar', data={'contenido': 'Texto que se va a eliminar'})
    with app.app_context():
        message_id = Mensaje.query.one().id
    route = f'/mensajes/{message_id}/eliminar'
    assert caregiver.post(route, data={'alcance': 'para_todos'}).status_code == 403
    assert caregiver.post(route, data={'alcance': 'para_mi'}).status_code == 302
    assert caregiver.post(route, data={'alcance': 'para_mi'}).status_code == 302
    assert b'Texto que se va a eliminar' not in caregiver.get('/mensajes').data
    assert b'Texto que se va a eliminar' in adult.get('/mensajes').data
    with app.app_context():
        assert Mensaje.query.count() == 1
        assert MensajeOculto.query.count() == 1
    assert adult.post(route, data={'alcance': 'para_todos'}).status_code == 302
    for client in (adult, caregiver):
        assert b'Texto que se va a eliminar' not in client.get('/mensajes').data
    assert b'Texto que se va a eliminar' not in adult.get('/adulto/inicio').data
    with app.app_context():
        assert Mensaje.query.count() == 0
        assert MensajeOculto.query.count() == 0


@pytest.mark.parametrize('content', ['', '   ', 'x' * 501])
def test_message_content_validation(app, families, content):
    client = logged_client(app, families[0].adult)
    assert client.post('/mensajes/enviar', data={'contenido': content}).status_code == 302
    with app.app_context():
        assert Mensaje.query.count() == 0


def test_unlinked_adult_cannot_send_to_nonexistent_family_members(app):
    client = app.test_client()
    client.post('/registro/adulto', data=registration())
    client.post('/mensajes/enviar', data={'contenido': 'Sin destinatario'})
    with app.app_context():
        assert Mensaje.query.count() == 0


def test_family_isolation_for_messages_and_care_actions(app, families, fixed_clock):
    own, other = families
    with app.app_context():
        occurrence = create_occurrence(other)
        message = Mensaje(familia_id=other.id, remitente_id=other.adult,
                          contenido='MENSAJE PRIVADO OTRA FAMILIA')
        appointment = Cita(familia_id=other.id, adulto_mayor_id=other.adult,
                          especialidad='CITA PRIVADA', fecha=FIXED_NOW.date() + timedelta(days=1), hora=time(10))
        db.session.add_all([message, appointment])
        db.session.flush()
        alert = Alerta(familia_id=other.id, registro_id=occurrence.id, mensaje='ALERTA PRIVADA')
        db.session.add(alert)
        db.session.commit()
        reminder_id, occurrence_id, message_id = occurrence.recordatorio_id, occurrence.id, message.id
        appointment_id, alert_id = appointment.id, alert.id
    adult = logged_client(app, own.adult)
    caregiver = logged_client(app, own.caregiver)
    for client, page in ((adult, '/adulto/inicio'), (adult, '/adulto/citas'),
                         (adult, '/mensajes'), (caregiver, '/familiar/panel'),
                         (caregiver, '/familiar/plan-cuidado'), (caregiver, '/mensajes')):
        response = client.get(page)
        assert response.status_code == 200
        assert b'MENSAJE PRIVADO OTRA FAMILIA' not in response.data
        assert b'CITA PRIVADA' not in response.data
        assert b'ALERTA PRIVADA' not in response.data
    operations = [
        (adult, f'/mensajes/{message_id}/eliminar', {'alcance': 'para_mi'}),
        (adult, f'/mensajes/{message_id}/eliminar', {'alcance': 'para_todos'}),
        (adult, f'/adulto/recordatorios/{occurrence_id}/confirmar', {}),
        (adult, f'/adulto/recordatorios/{occurrence_id}/posponer', {}),
        (adult, f'/adulto/citas/{appointment_id}/reprogramar', {'fecha': '2026-12-01', 'hora': '10:00'}),
        (caregiver, f'/familiar/plan-cuidado/recordatorio/{reminder_id}/eliminar', {}),
        (caregiver, f'/familiar/plan-cuidado/cita/{appointment_id}/eliminar', {}),
        (caregiver, f'/familiar/alertas/{alert_id}/descartar', {}),
    ]
    for client, path, data in operations:
        assert client.post(path, data=data).status_code == 404, path
    with app.app_context():
        assert db.session.get(RegistroRecordatorio, occurrence_id).estado == 'pendiente'
        assert db.session.get(Recordatorio, reminder_id).activo
        assert db.session.get(Cita, appointment_id).estado == 'confirmada'
        assert db.session.get(Mensaje, message_id) is not None
        assert MensajeOculto.query.count() == 0


def test_code_renewal_is_adult_only_and_keeps_existing_members(app, families):
    family = families[0]
    caregiver = logged_client(app, family.caregiver)
    adult = logged_client(app, family.adult)
    assert caregiver.post('/familia/codigo/renovar').status_code == 403
    assert adult.post('/familia/codigo/renovar').status_code == 302
    with app.app_context():
        new_code = db.session.get(Familia, family.id).codigo_familia
        assert new_code != family.code
        assert db.session.get(Usuario, family.caregiver).familia_id == family.id
    newcomer = app.test_client()
    newcomer.post('/registro/familiar', data=registration(codigo_familia=family.code))
    with app.app_context():
        assert Usuario.query.filter_by(correo='nueva@example.com').first() is None
    newcomer.post('/registro/familiar', data=registration(codigo_familia=new_code))
    with app.app_context():
        assert Usuario.query.filter_by(correo='nueva@example.com').one().familia_id == family.id
    assert caregiver.get('/familiar/panel').status_code == 200


def test_once_daily_and_weekly_create_only_due_occurrences(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        once = create_reminder(family, nombre='Una vez', repetir='una_vez')
        daily = create_reminder(family, nombre='Diario', repetir='diario')
        weekly = create_reminder(family, nombre='Semanal', repetir='semanal')
        db.session.commit()
        ids = once.id, daily.id, weekly.id
        for days, expected in ((0, set(ids)), (1, {daily.id}), (7, {daily.id, weekly.id})):
            moment = FIXED_NOW + timedelta(days=days)
            fixed_clock(moment)
            utils.asegurar_registros_hoy(family.id)
            utils.asegurar_registros_hoy(family.id)
            rows = RegistroRecordatorio.query.filter_by(fecha=moment.date()).all()
            assert {row.recordatorio_id for row in rows} == expected
            assert len(rows) == len(expected)
        fixed_clock(FIXED_NOW - timedelta(days=1))
        utils.asegurar_registros_hoy(family.id)
        assert RegistroRecordatorio.query.filter_by(fecha=utils.hoy_local()).count() == 0


def test_frequency_uses_bogota_date_for_utc_creation(app, families, fixed_clock):
    with app.app_context():
        reminder = create_reminder(families[0], repetir='una_vez',
                                  fecha_creacion=datetime(2026, 11, 12, 2, 30))
        assert utils.corresponde_recordatorio(reminder, datetime(2026, 11, 11).date())
        assert not utils.corresponde_recordatorio(reminder, datetime(2026, 11, 12).date())


def test_postpone_overdue_from_now_then_confirm_is_idempotent(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        occurrence = create_occurrence(family)
        occurrence.urgente = True
        db.session.add(Alerta(familia_id=family.id, registro_id=occurrence.id, mensaje='Atrasado'))
        db.session.commit()
        occurrence_id = occurrence.id
    client = logged_client(app, family.adult)
    path = f'/adulto/recordatorios/{occurrence_id}'
    assert client.post(path + '/posponer').status_code == 302
    with app.app_context():
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        assert occurrence.estado == 'pospuesto'
        assert occurrence.hora_programada == time(12, 15)
        assert Alerta.query.filter_by(registro_id=occurrence_id, estado='activa').count() == 0
    response = client.post(path + '/confirmar', headers={'Referer': 'https://example.invalid/external'})
    assert response.status_code == 302
    assert not response.location.startswith('https://example.invalid')
    with app.app_context():
        first_time = db.session.get(RegistroRecordatorio, occurrence_id).hora_confirmacion
    fixed_clock(FIXED_NOW + timedelta(minutes=5))
    client.post(path + '/confirmar')
    client.post(path + '/posponer')
    with app.app_context():
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        assert occurrence.estado == 'completado'
        assert occurrence.hora_confirmacion == first_time
        assert not occurrence.urgente
        assert Actividad.query.filter_by(familia_id=family.id, tipo='completado').count() == 1


def test_postpone_near_midnight_does_not_wrap_to_morning(app, families, fixed_clock):
    with app.app_context():
        occurrence = create_occurrence(families[0], hora_programada=time(23, 40))
        occurrence_id = occurrence.id
    fixed_clock(FIXED_NOW.replace(hour=23, minute=55))
    client = logged_client(app, families[0].adult)
    assert client.post(f'/adulto/recordatorios/{occurrence_id}/posponer').status_code == 302
    with app.app_context():
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        assert occurrence.estado == 'pendiente'
        assert occurrence.hora_programada == time(23, 40)


@pytest.mark.parametrize('invalid', [
    {'tipo': 'inyeccion_no_valida'}, {'repetir': 'mensual'},
    {'hora': '25:70'}, {'nombre': 'x' * 151},
])
def test_invalid_reminder_is_rejected_before_database(app, families, invalid):
    form = {'nombre': 'Caminar', 'tipo': 'actividad', 'hora': '08:00', 'repetir': 'diario'}
    form.update(invalid)
    client = logged_client(app, families[0].caregiver)
    assert client.post('/familiar/plan-cuidado/recordatorio/nuevo', data=form).status_code == 302
    with app.app_context():
        assert Recordatorio.query.count() == 0


def test_past_appointments_rejected_future_preserved_on_cancel(app, families, fixed_clock):
    family = families[0]
    client = logged_client(app, family.caregiver)
    path = '/familiar/plan-cuidado/cita/nueva'
    for day, hour in (('2026-11-10', '13:00'), ('2026-11-11', '11:59')):
        assert client.post(path, data={'especialidad': 'Consulta', 'fecha': day, 'hora': hour}).status_code == 302
    with app.app_context():
        assert Cita.query.count() == 0
    client.post(path, data={'especialidad': 'Consulta', 'fecha': '2026-11-12', 'hora': '13:00'})
    with app.app_context():
        appointment_id = Cita.query.one().id
    client.post(f'/familiar/plan-cuidado/cita/{appointment_id}/eliminar')
    with app.app_context():
        appointment = db.session.get(Cita, appointment_id)
        assert appointment is not None
        assert appointment.estado == 'cancelada'


def test_confirmed_appointment_is_featured_and_cancelled_is_excluded(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        db.session.add_all([
            Cita(familia_id=family.id, adulto_mayor_id=family.adult,
                 especialidad='Consulta prioritaria', fecha=FIXED_NOW.date(), hora=time(13), estado='confirmada'),
            Cita(familia_id=family.id, adulto_mayor_id=family.adult,
                 especialidad='Consulta cancelada', fecha=FIXED_NOW.date(), hora=time(12, 30), estado='cancelada'),
        ])
        db.session.commit()
    page = logged_client(app, family.adult).get('/adulto/inicio')
    assert page.status_code == 200
    assert b'Consulta prioritaria' in page.data.split(b'Tu d')[0]
    assert b'Consulta cancelada' not in page.data


def test_status_version_only_changes_for_own_family(app, families, fixed_clock):
    own, other = families
    own_client = logged_client(app, own.caregiver)
    other_client = logged_client(app, other.adult)
    assert app.test_client().get('/api/estado').status_code in (302, 401)
    response = own_client.get('/api/estado')
    assert response.status_code == 200
    state = response.get_json()
    assert 'version' in state and 'actualizado_en' in state
    other_client.post('/mensajes/enviar', data={'contenido': 'NOVEDAD PRIVADA B'})
    unchanged = own_client.get('/api/estado')
    assert unchanged.get_json()['version'] == state['version']
    assert b'NOVEDAD PRIVADA B' not in unchanged.data
    assert families[1].code.encode() not in unchanged.data
    logged_client(app, own.adult).post('/mensajes/enviar', data={'contenido': 'NOVEDAD PROPIA A'})
    assert own_client.get('/api/estado').get_json()['version'] != state['version']


def test_csrf_rejects_mutation_without_token_and_accepts_valid_form(app):
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    form = registration()
    assert client.post('/registro/adulto', data=form).status_code == 400
    with app.app_context():
        assert Usuario.query.count() == 0
    page = client.get('/registro/adulto').get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    assert token is not None, 'El formulario necesita un token CSRF utilizable sin JavaScript.'
    form['csrf_token'] = token.group(1)
    assert client.post('/registro/adulto', data=form).status_code == 302
    with app.app_context():
        assert Usuario.query.count() == 1


def test_logout_requires_post_and_restricts_pages_after_logout(app, families):
    client = logged_client(app, families[0].adult)
    assert client.get('/logout').status_code == 405
    assert client.get('/adulto/inicio').status_code == 200
    assert client.post('/logout').status_code == 302
    assert client.get('/adulto/inicio').status_code == 302
    assert client.get('/mensajes').status_code == 302


def test_roles_cannot_use_other_roles_care_actions(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        occurrence_id = create_occurrence(family).id
    adult = logged_client(app, family.adult)
    caregiver = logged_client(app, family.caregiver)
    assert adult.get('/familiar/panel').status_code == 403
    assert adult.post('/familiar/plan-cuidado/recordatorio/nuevo', data={}).status_code == 403
    assert caregiver.get('/adulto/inicio').status_code == 403
    assert caregiver.post(f'/adulto/recordatorios/{occurrence_id}/confirmar').status_code == 403


def test_privacy_page_is_available_before_registration(app):
    assert app.test_client().get('/privacidad').status_code == 200


def test_alert_threshold_has_no_early_or_duplicate_alerts(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        occurrence_id = create_occurrence(family).id
        fixed_clock(FIXED_NOW.replace(hour=8, minute=30))
        utils.verificar_alertas(family.id)
        assert Alerta.query.count() == 0
        fixed_clock(FIXED_NOW.replace(hour=8, minute=31))
        utils.verificar_alertas(family.id)
        utils.verificar_alertas(family.id)
        assert Alerta.query.filter_by(registro_id=occurrence_id, estado='activa').count() == 1
        assert Actividad.query.filter_by(familia_id=family.id, tipo='alerta').count() == 1


def test_explicit_not_done_stays_terminal_and_is_visible_to_caregiver(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        occurrence_id = create_occurrence(family).id
    adult = logged_client(app, family.adult)
    path = f'/adulto/recordatorios/{occurrence_id}'
    adult.post(path + '/omitir')
    adult.post(path + '/omitir')
    adult.post(path + '/confirmar')
    adult.post(path + '/posponer')
    with app.app_context():
        assert db.session.get(RegistroRecordatorio, occurrence_id).estado == 'omitido'
        assert Actividad.query.filter_by(familia_id=family.id, tipo='omitido').count() == 1
        assert Actividad.query.filter_by(familia_id=family.id, tipo='completado').count() == 0
    page = logged_client(app, family.caregiver).get('/familiar/panel')
    assert page.status_code == 200
    assert b'Actividad de prueba' in page.data
    assert b'No realizado' in page.data or b'No lo hice' in page.data or b'Omitido' in page.data


def test_reminder_edits_move_pending_due_time_and_keep_completed_records(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        occurrence = create_occurrence(family)
        reminder_id, occurrence_id = occurrence.recordatorio_id, occurrence.id
    caregiver = logged_client(app, family.caregiver)
    form = {'nombre': 'Actividad de prueba', 'tipo': 'actividad', 'hora': '14:00', 'repetir': 'diario'}
    path = f'/familiar/plan-cuidado/recordatorio/{reminder_id}/editar'
    assert caregiver.post(path, data=form).status_code == 302
    with app.app_context():
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        assert occurrence.hora_programada == time(14)
        assert occurrence.estado == 'pendiente'
    adult = logged_client(app, family.adult)
    adult.post(f'/adulto/recordatorios/{occurrence_id}/confirmar')
    form['hora'] = '15:00'
    caregiver.post(path, data=form)
    with app.app_context():
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        assert occurrence.estado == 'completado'
        assert occurrence.hora_programada == time(14)
        assert db.session.get(Recordatorio, reminder_id).hora == time(15)
        assert RegistroRecordatorio.query.filter_by(recordatorio_id=reminder_id).count() == 1


@pytest.mark.parametrize('state', ['pendiente', 'completado'])
def test_frequency_edit_removes_only_unanswered_non_due_occurrence(app, families, fixed_clock, state):
    family = families[0]
    with app.app_context():
        occurrence = create_occurrence(family, estado=state)
        occurrence.recordatorio.fecha_creacion = datetime(2026, 11, 10, 12)
        if state == 'pendiente':
            db.session.add(Alerta(familia_id=family.id, registro_id=occurrence.id, mensaje='Aviso anterior'))
        db.session.commit()
        occurrence_id, reminder_id = occurrence.id, occurrence.recordatorio_id
    caregiver = logged_client(app, family.caregiver)
    response = caregiver.post(f'/familiar/plan-cuidado/recordatorio/{reminder_id}/editar', data={
        'nombre': 'Actividad de prueba', 'tipo': 'actividad', 'hora': '08:00', 'repetir': 'semanal',
    })
    assert response.status_code == 302
    with app.app_context():
        utils.asegurar_registros_hoy(family.id)
        occurrence = db.session.get(RegistroRecordatorio, occurrence_id)
        if state == 'pendiente':
            assert occurrence is None
        else:
            assert occurrence is not None
            assert occurrence.estado == 'completado'
        assert Alerta.query.filter_by(estado='activa').count() == 0
