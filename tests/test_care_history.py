"""Regresiones de continuidad del historial y selección del próximo evento."""
from datetime import time

from flask import template_rendered

from extensions import db
from models import Cita, Recordatorio, RegistroRecordatorio
import utils
from test_app import (app, families, fixed_clock, FIXED_NOW, create_occurrence,
                      logged_client)


def test_deactivation_keeps_terminal_counts_without_inactive_pending_actions(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        rows = []
        for estado in ('completado', 'omitido', 'pendiente', 'pospuesto'):
            occurrence = create_occurrence(family, estado=estado)
            occurrence.recordatorio.nombre = f'Recordatorio {estado}'
            rows.append((occurrence.id, occurrence.recordatorio_id))
        db.session.commit()
    caregiver = logged_client(app, family.caregiver)
    for _, reminder_id in rows:
        response = caregiver.post(f'/familiar/plan-cuidado/recordatorio/{reminder_id}/eliminar')
        assert response.status_code == 302
    with app.app_context():
        assert Recordatorio.query.filter_by(familia_id=family.id, activo=True).count() == 0
        assert RegistroRecordatorio.query.count() == 4, 'Las respuestas y registros originales se conservan.'
        events = utils.construir_linea_tiempo(family.id, FIXED_NOW.date())
        assert {event['estado'] for event in events} == {'completado', 'omitido'}
        assert all(event['inactivo'] for event in events)
        assert utils.resumen_cumplimiento(events) == {
            'total': 2, 'completados': 1, 'pendientes': 0,
            'pospuestos': 0, 'omitidos': 1, 'porcentaje': 50,
        }
    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    template_rendered.connect(capture, app)
    try:
        page = caregiver.get('/familiar/panel')
    finally:
        template_rendered.disconnect(capture, app)
    assert page.status_code == 200
    assert contexts[-1]['resumen']['completados'] == 1
    assert contexts[-1]['resumen']['omitidos'] == 1
    adult = logged_client(app, family.adult)
    # Ni siquiera una petición manual reactiva un recordatorio eliminado.
    for occurrence_id, _ in rows:
        assert adult.post(f'/adulto/recordatorios/{occurrence_id}/confirmar').status_code == 404


def test_past_appointment_never_hides_overdue_reminder_or_next_appointment(app, families, fixed_clock):
    family = families[0]
    with app.app_context():
        overdue = create_occurrence(family)
        overdue.recordatorio.nombre = 'Actividad pendiente real'
        db.session.add_all([
            Cita(familia_id=family.id, adulto_mayor_id=family.adult,
                 especialidad='Consulta terminada temprano', fecha=FIXED_NOW.date(), hora=time(7), estado='confirmada'),
            Cita(familia_id=family.id, adulto_mayor_id=family.adult,
                 especialidad='Consulta siguiente', fecha=FIXED_NOW.date(), hora=time(13), estado='confirmada'),
        ])
        db.session.commit()
        events = utils.construir_linea_tiempo(family.id, FIXED_NOW.date())
        assert any(event['titulo'] == 'Consulta terminada temprano' for event in events)
        assert utils.evento_mas_importante(events, FIXED_NOW.time())['titulo'] == 'Actividad pendiente real'
        overdue.estado = 'completado'
        db.session.commit()
        events = utils.construir_linea_tiempo(family.id, FIXED_NOW.date())
        assert utils.evento_mas_importante(events, FIXED_NOW.time())['titulo'] == 'Consulta siguiente'
        assert utils.evento_mas_importante(events, time(14)) is None
