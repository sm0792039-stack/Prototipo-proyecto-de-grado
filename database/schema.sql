-- =========================================================================
-- My Remember — Esquema de base de datos (MySQL)
-- Proyecto de grado: Ingeniería de Sistemas — TEINCO — 2026
-- Semillero SIIANTEC — Laura Daniela Merchán Gil / Juan David Sánchez Monroy
--
-- Cómo usar este archivo:
--   mysql -u root -p < database/schema.sql
-- Esto crea la base de datos "my_remember_db" y todas sus tablas vacías.
-- Para cargar datos de demostración, después ejecutar:  python seed.py
-- =========================================================================

CREATE DATABASE IF NOT EXISTS my_remember_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE my_remember_db;

-- -------------------------------------------------------------------------
-- familias: agrupa a un adulto mayor con sus familiares/cuidadores
-- -------------------------------------------------------------------------
-- Este esquema crea tablas faltantes y conserva los datos existentes.
-- Las ampliaciones de una instalación previa se documentan en migrations/.

CREATE TABLE IF NOT EXISTS familias (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    codigo_familia  VARCHAR(20)  NOT NULL UNIQUE COMMENT 'Código para vincular familiares, ej: FAM-7XQ2K',
    fecha_creacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- usuarios: cuentas de acceso (adulto mayor o familiar/cuidador)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo         VARCHAR(120) NOT NULL,
    correo                  VARCHAR(120) NOT NULL UNIQUE,
    contrasena_hash         VARCHAR(255) NOT NULL,
    rol                     ENUM('adulto_mayor','familiar') NOT NULL,
    parentesco              VARCHAR(50)  NULL COMMENT 'Ej: Hija, Hijo, Cuidador (solo para rol=familiar)',
    telefono                VARCHAR(30)  NULL,
    avatar_inicial          VARCHAR(2)   NULL,
    avatar_color            VARCHAR(20)  NULL,
    es_contacto_emergencia  TINYINT(1)   NOT NULL DEFAULT 0,
    familia_id              INT          NOT NULL,
    fecha_registro          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuarios_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    INDEX idx_usuarios_familia (familia_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- recordatorios: medicamentos, actividades o tareas recurrentes
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recordatorios (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    familia_id        INT NOT NULL,
    adulto_mayor_id   INT NOT NULL,
    nombre            VARCHAR(150) NOT NULL,
    tipo              ENUM('medicamento','actividad','tarea') NOT NULL DEFAULT 'medicamento',
    hora              TIME NOT NULL,
    repetir           ENUM('una_vez','diario','semanal') NOT NULL DEFAULT 'diario',
    notas             VARCHAR(255) NULL,
    activo            TINYINT(1) NOT NULL DEFAULT 1,
    creado_por_id     INT NULL,
    fecha_creacion    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recordatorios_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    CONSTRAINT fk_recordatorios_adulto
        FOREIGN KEY (adulto_mayor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_recordatorios_creador
        FOREIGN KEY (creado_por_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_recordatorios_familia (familia_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- registros_recordatorio: una fila por CADA OCURRENCIA DIARIA de un
-- recordatorio (permite llevar historial de cumplimiento día a día)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS registros_recordatorio (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    recordatorio_id     INT NOT NULL,
    fecha               DATE NOT NULL,
    hora_programada     TIME NOT NULL,
    estado              ENUM('pendiente','completado','pospuesto','omitido') NOT NULL DEFAULT 'pendiente',
    hora_confirmacion   DATETIME NULL,
    alerta_descartada   TINYINT(1) NOT NULL DEFAULT 0,
    urgente             TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Se activa cuando el familiar resalta el recordatorio en la aplicación',
    CONSTRAINT fk_registro_recordatorio
        FOREIGN KEY (recordatorio_id) REFERENCES recordatorios(id) ON DELETE CASCADE,
    UNIQUE KEY uq_registro_dia (recordatorio_id, fecha),
    INDEX idx_registro_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- citas: citas médicas del adulto mayor
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS citas (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    familia_id        INT NOT NULL,
    adulto_mayor_id   INT NOT NULL,
    especialidad      VARCHAR(100) NOT NULL,
    doctor_nombre     VARCHAR(120) NULL,
    fecha             DATE NOT NULL,
    hora              TIME NOT NULL,
    lugar_nombre      VARCHAR(150) NULL,
    direccion         VARCHAR(255) NULL,
    estado            ENUM('confirmada','pendiente','cancelada') NOT NULL DEFAULT 'confirmada',
    notas             TEXT NULL,
    creado_por_id     INT NULL,
    fecha_creacion    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_citas_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    CONSTRAINT fk_citas_adulto
        FOREIGN KEY (adulto_mayor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_citas_creador
        FOREIGN KEY (creado_por_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_citas_familia_fecha (familia_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- mensajes: mensajes afectivos familiares ("Estoy Contigo")
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensajes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    familia_id      INT NOT NULL,
    remitente_id    INT NOT NULL,
    contenido       VARCHAR(500) NOT NULL,
    fecha_envio     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mensajes_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    CONSTRAINT fk_mensajes_remitente
        FOREIGN KEY (remitente_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_mensajes_familia_fecha (familia_id, fecha_envio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- mensajes_ocultos: eliminación de un mensaje solamente para una cuenta
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensajes_ocultos (
    mensaje_id        INT NOT NULL,
    usuario_id        INT NOT NULL,
    fecha_ocultacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (mensaje_id, usuario_id),
    CONSTRAINT fk_ocultos_mensaje
        FOREIGN KEY (mensaje_id) REFERENCES mensajes(id) ON DELETE CASCADE,
    CONSTRAINT fk_ocultos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- actividad_historial: bitácora de eventos para la pantalla de Historial
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS actividad_historial (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    familia_id      INT NOT NULL,
    descripcion     VARCHAR(255) NOT NULL,
    tipo            ENUM('completado','omitido','pospuesto','programado','mensaje','cita','alerta') NOT NULL,
    fecha_hora      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_actividad_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    INDEX idx_actividad_familia_fecha (familia_id, fecha_hora)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- alertas: avisos automáticos por recordatorios no confirmados
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alertas (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    familia_id      INT NOT NULL,
    registro_id     INT NULL,
    mensaje         VARCHAR(255) NOT NULL,
    estado          ENUM('activa','descartada') NOT NULL DEFAULT 'activa',
    fecha_creacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alertas_familia
        FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE,
    CONSTRAINT fk_alertas_registro
        FOREIGN KEY (registro_id) REFERENCES registros_recordatorio(id) ON DELETE CASCADE,
    INDEX idx_alertas_familia_estado (familia_id, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
