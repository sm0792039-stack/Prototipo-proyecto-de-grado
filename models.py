"""
models.py
Modelos de datos de My Remember (SQLAlchemy sobre SQLite o MySQL).

Cada clase corresponde a una tabla descrita en database/schema.sql.
Mantener ambos archivos sincronizados si se agrega o modifica un campo.

Alcance del modelo: se asume UN (1) adulto mayor por grupo familiar,
acompañado de uno o varios familiares/cuidadores. Esta simplificación
se ajusta al alcance definido para la prueba piloto en el Conjunto
Residencial Las Margaritas, Etapa 3.
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager


def utc_now():
    """UTC sin zona para conservar los DATETIME de instalaciones previas."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Familia(db.Model):
    """Agrupa a un adulto mayor con sus familiares/cuidadores vinculados
    mediante un código compartido (codigo_familia)."""
    __tablename__ = 'familias'

    id = db.Column(db.Integer, primary_key=True)
    codigo_familia = db.Column(db.String(20), unique=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=utc_now, nullable=False)

    usuarios = db.relationship('Usuario', backref='familia', lazy=True,
                                cascade='all, delete-orphan')

    def adulto_mayor(self):
        """Devuelve el usuario con rol 'adulto_mayor' de esta familia."""
        for u in self.usuarios:
            if u.rol == 'adulto_mayor':
                return u
        return None

    def familiares(self):
        """Devuelve la lista de usuarios con rol 'familiar' de esta familia."""
        return [u for u in self.usuarios if u.rol == 'familiar']


class Usuario(UserMixin, db.Model):
    """Cuenta de acceso a la plataforma. El campo 'rol' determina si la
    persona ve la experiencia de Adulto Mayor o la de Familiar/Cuidador."""
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('adulto_mayor', 'familiar', name='rol_usuario'), nullable=False)
    parentesco = db.Column(db.String(50), nullable=True)  # Ej: "Hija", "Cuidador"
    telefono = db.Column(db.String(30), nullable=True)
    avatar_inicial = db.Column(db.String(2), nullable=True)
    avatar_color = db.Column(db.String(20), nullable=True)
    es_contacto_emergencia = db.Column(db.Boolean, default=False, nullable=False)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=utc_now, nullable=False)

    recordatorios_creados = db.relationship('Recordatorio', backref='creador',
                                             foreign_keys='Recordatorio.creado_por_id')
    mensajes_enviados = db.relationship('Mensaje', backref='remitente', lazy=True)
    ocultaciones_mensajes = db.relationship(
        'MensajeOculto', backref='usuario', cascade='all, delete-orphan', lazy=True,
    )

    def set_password(self, password):
        self.contrasena_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contrasena_hash, password)

    def es_adulto_mayor(self):
        return self.rol == 'adulto_mayor'

    def es_familiar(self):
        return self.rol == 'familiar'


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


class Recordatorio(db.Model):
    """Un recordatorio recurrente (medicamento, actividad o tarea)
    definido por el adulto mayor o por un familiar/cuidador."""
    __tablename__ = 'recordatorios'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    adulto_mayor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.Enum('medicamento', 'actividad', 'tarea', name='tipo_recordatorio'),
                      default='medicamento', nullable=False)
    hora = db.Column(db.Time, nullable=False)
    repetir = db.Column(db.Enum('una_vez', 'diario', 'semanal', name='repetir_recordatorio'),
                         default='diario', nullable=False)
    notas = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=utc_now, nullable=False)

    adulto_mayor = db.relationship('Usuario', foreign_keys=[adulto_mayor_id])
    registros = db.relationship('RegistroRecordatorio', backref='recordatorio', lazy=True,
                                 cascade='all, delete-orphan')

    def icono(self):
        return {'medicamento': 'bi-capsule', 'actividad': 'bi-person-walking',
                'tarea': 'bi-check2-square'}.get(self.tipo, 'bi-bell')


class RegistroRecordatorio(db.Model):
    """Una ocurrencia concreta (de un día puntual) de un Recordatorio.
    Separar esto del Recordatorio permite llevar historial día a día:
    al consultar la aplicación se genera un registro 'pendiente' por cada
    recordatorio activo aplicable al día, y ese registro cambia de estado cuando el adulto mayor
    confirma, pospone u omite la acción."""
    __tablename__ = 'registros_recordatorio'
    __table_args__ = (
        db.UniqueConstraint('recordatorio_id', 'fecha', name='uq_registro_dia'),
    )

    id = db.Column(db.Integer, primary_key=True)
    recordatorio_id = db.Column(db.Integer, db.ForeignKey('recordatorios.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_programada = db.Column(db.Time, nullable=False)
    estado = db.Column(db.Enum('pendiente', 'completado', 'pospuesto', 'omitido',
                                name='estado_registro'), default='pendiente', nullable=False)
    hora_confirmacion = db.Column(db.DateTime, nullable=True)
    alerta_descartada = db.Column(db.Boolean, default=False, nullable=False)
    urgente = db.Column(db.Boolean, default=False, nullable=False)

    alertas = db.relationship('Alerta', backref='registro', lazy=True,
                               cascade='all, delete-orphan')


class Cita(db.Model):
    """Una cita médica del adulto mayor."""
    __tablename__ = 'citas'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    adulto_mayor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    especialidad = db.Column(db.String(100), nullable=False)
    doctor_nombre = db.Column(db.String(120), nullable=True)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    lugar_nombre = db.Column(db.String(150), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    estado = db.Column(db.Enum('confirmada', 'pendiente', 'cancelada', name='estado_cita'),
                        default='confirmada', nullable=False)
    notas = db.Column(db.Text, nullable=True)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=utc_now, nullable=False)

    adulto_mayor = db.relationship('Usuario', foreign_keys=[adulto_mayor_id])

    def titulo(self):
        return f'{self.especialidad} · {self.doctor_nombre}' if self.doctor_nombre else self.especialidad


class Mensaje(db.Model):
    """Mensaje compartido entre el adulto mayor y sus cuidadores vinculados."""
    __tablename__ = 'mensajes'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    remitente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    contenido = db.Column(db.String(500), nullable=False)
    fecha_envio = db.Column(db.DateTime, default=utc_now, nullable=False)
    ocultaciones = db.relationship(
        'MensajeOculto', backref='mensaje', cascade='all, delete-orphan', lazy=True,
    )


class MensajeOculto(db.Model):
    """Borrar para mí no modifica la copia visible de las otras personas."""
    __tablename__ = 'mensajes_ocultos'

    mensaje_id = db.Column(
        db.Integer, db.ForeignKey('mensajes.id', ondelete='CASCADE'), primary_key=True,
    )
    usuario_id = db.Column(
        db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True,
    )
    fecha_ocultacion = db.Column(db.DateTime, default=utc_now, nullable=False)


class Actividad(db.Model):
    """Registro de historial: cada acción relevante (medicamento tomado,
    mensaje enviado, cita creada, alerta generada) queda anotada aquí
    para alimentar la pantalla de Historial del familiar/cuidador."""
    __tablename__ = 'actividad_historial'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.Enum('completado', 'omitido', 'pospuesto', 'programado', 'mensaje',
                              'cita', 'alerta', name='tipo_actividad'), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=utc_now, nullable=False)

    _ICONOS = {
        'completado': 'bi-check-lg', 'omitido': 'bi-x-lg', 'pospuesto': 'bi-clock',
        'programado': 'bi-calendar-plus', 'mensaje': 'bi-heart-fill',
        'cita': 'bi-calendar2-heart', 'alerta': 'bi-exclamation-triangle-fill',
    }

    def icono(self):
        return self._ICONOS.get(self.tipo, 'bi-info-circle')


class Alerta(db.Model):
    """Aviso generado automáticamente cuando un recordatorio no fue
    confirmado dentro del umbral de tiempo definido (ver
    Config.UMBRAL_ALERTA_MINUTOS)."""
    __tablename__ = 'alertas'

    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familias.id'), nullable=False)
    registro_id = db.Column(db.Integer, db.ForeignKey('registros_recordatorio.id'), nullable=True)
    mensaje = db.Column(db.String(255), nullable=False)
    estado = db.Column(db.Enum('activa', 'descartada', name='estado_alerta'),
                        default='activa', nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=utc_now, nullable=False)
