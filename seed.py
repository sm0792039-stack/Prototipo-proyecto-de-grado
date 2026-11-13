"""
seed.py
Carga datos de demostración para My Remember: una familia completa
(adulto mayor + 2 familiares) con recordatorios, citas, un mensaje y
actividad de ejemplo, tal como aparece en los mockups del proyecto.

Requisito previo: haber creado las tablas con database/schema.sql

Uso:
    python seed.py
"""
from datetime import date, time, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import create_app
from extensions import db
from models import Familia, Usuario, Recordatorio, RegistroRecordatorio, Cita, Mensaje, Actividad
from utils import hoy_local

CODIGO_DEMO = 'FAM-MARGARITAS1'
CLAVE_DEMO = 'Remember2026'

app = create_app()

with app.app_context():
    if Familia.query.filter_by(codigo_familia=CODIGO_DEMO).first():
        print('Los datos de demostración ya existen. No se realizó ningún cambio.')
        raise SystemExit(0)

    # --- Familia y usuarios -------------------------------------------------
    familia = Familia(codigo_familia=CODIGO_DEMO)
    db.session.add(familia)
    db.session.flush()  # asigna familia.id sin cerrar la transacción

    maria = Usuario(
        nombre_completo='María García', correo='maria@familiagarcia.com',
        rol='adulto_mayor', telefono='+57 300 111 2233',
        avatar_inicial='M', avatar_color='#2E9E93', familia_id=familia.id,
    )
    maria.set_password(CLAVE_DEMO)

    laura = Usuario(
        nombre_completo='Laura García', correo='laura@familiagarcia.com',
        rol='familiar', parentesco='Hija', telefono='+57 300 222 3344',
        avatar_inicial='L', avatar_color='#E2A33B', es_contacto_emergencia=True,
        familia_id=familia.id,
    )
    laura.set_password(CLAVE_DEMO)

    juan = Usuario(
        nombre_completo='Juan Pérez', correo='juan@familiagarcia.com',
        rol='familiar', parentesco='Cuidador', telefono='+57 300 333 4455',
        avatar_inicial='J', avatar_color='#163B5C', familia_id=familia.id,
    )
    juan.set_password(CLAVE_DEMO)

    db.session.add_all([maria, laura, juan])
    db.session.flush()

    # --- Recordatorios --------------------------------------------------------
    r_manana = Recordatorio(
        familia_id=familia.id, adulto_mayor_id=maria.id,
        nombre='Losartán (Medicamento A)', tipo='medicamento', hora=time(8, 0),
        repetir='diario', notas='1 tableta - presión arterial', creado_por_id=laura.id,
    )
    r_tarde = Recordatorio(
        familia_id=familia.id, adulto_mayor_id=maria.id,
        nombre='Metformina (Medicamento B)', tipo='medicamento', hora=time(14, 0),
        repetir='diario', notas='1 tableta después del almuerzo', creado_por_id=laura.id,
    )
    r_noche = Recordatorio(
        familia_id=familia.id, adulto_mayor_id=maria.id,
        nombre='Losartán (Medicamento A)', tipo='medicamento', hora=time(20, 0),
        repetir='diario', notas='1 tableta - presión arterial', creado_por_id=laura.id,
    )
    r_vitamina = Recordatorio(
        familia_id=familia.id, adulto_mayor_id=maria.id,
        nombre='Vitamina C', tipo='medicamento', hora=time(7, 0),
        repetir='diario', notas='1 tableta masticable', creado_por_id=juan.id,
    )
    r_caminata = Recordatorio(
        familia_id=familia.id, adulto_mayor_id=maria.id,
        nombre='Caminata en el jardín', tipo='actividad', hora=time(16, 0),
        repetir='diario', notas='20 minutos, con acompañamiento', creado_por_id=juan.id,
    )
    db.session.add_all([r_manana, r_tarde, r_noche, r_vitamina, r_caminata])
    db.session.flush()

    # --- Registro de hoy ya cumplido (la vitamina de la mañana) --------------
    hoy = hoy_local()
    zona = ZoneInfo(app.config['TIMEZONE'])
    confirmacion_utc = datetime.combine(hoy, time(7, 5), tzinfo=zona).astimezone(timezone.utc).replace(tzinfo=None)
    registro_vitamina = RegistroRecordatorio(
        recordatorio_id=r_vitamina.id, fecha=hoy, hora_programada=time(7, 0),
        estado='completado', hora_confirmacion=confirmacion_utc,
    )
    db.session.add(registro_vitamina)

    # --- Citas médicas --------------------------------------------------------
    cita_cardiologia = Cita(
        familia_id=familia.id, adulto_mayor_id=maria.id, especialidad='Cardiología',
        doctor_nombre='Dr. García', fecha=hoy + timedelta(days=1), hora=time(9, 0),
        lugar_nombre='Clinic X', direccion='Calle Principal 123, Bogotá',
        estado='confirmada', creado_por_id=laura.id,
    )
    cita_dental = Cita(
        familia_id=familia.id, adulto_mayor_id=maria.id, especialidad='Odontología',
        doctor_nombre='Dra. Ramírez', fecha=hoy + timedelta(days=3), hora=time(11, 30),
        lugar_nombre='Clínica Dental Sol', direccion='Avenida del Sol 456, Piso 2, Bogotá',
        estado='confirmada', creado_por_id=laura.id,
    )
    cita_pasada = Cita(
        familia_id=familia.id, adulto_mayor_id=maria.id, especialidad='Medicina General',
        doctor_nombre='Dr. Higuera', fecha=hoy - timedelta(days=10), hora=time(10, 0),
        lugar_nombre='Centro de Salud Las Margaritas', direccion='Cra 78 # 38-12, Kennedy, Bogotá',
        estado='confirmada', creado_por_id=juan.id,
    )
    db.session.add_all([cita_cardiologia, cita_dental, cita_pasada])

    # --- Mensaje afectivo -------------------------------------------------
    mensaje = Mensaje(
        familia_id=familia.id, remitente_id=laura.id,
        contenido='Mamá, recuerda que mañana tienes tu cita con el cardiólogo. ¡Te quiero mucho!',
    )
    db.session.add(mensaje)

    # --- Historial de ejemplo -------------------------------------------------
    db.session.add_all([
        Actividad(familia_id=familia.id, descripcion='Tomó la Vitamina C', tipo='completado',
                  fecha_hora=confirmacion_utc),
        Actividad(familia_id=familia.id, descripcion='Laura envió un mensaje de cariño', tipo='mensaje'),
        Actividad(familia_id=familia.id, descripcion='Juan agendó la cita de Odontología', tipo='cita'),
    ])

    db.session.commit()

    print('Datos de demostración creados correctamente.\n')
    print(f'Código de familia: {CODIGO_DEMO}')
    print('Cuentas de prueba (todas con la contraseña "%s"):' % CLAVE_DEMO)
    print('  Adulto mayor      -> maria@familiagarcia.com')
    print('  Familiar (hija)   -> laura@familiagarcia.com')
    print('  Familiar (cuidador) -> juan@familiagarcia.com')
