-- Migración no destructiva para una base MySQL existente.
-- Recomendado: hacer una copia de seguridad antes de toda actualización.
-- Ejecutar desde la raíz del proyecto, indicando la base correcta:
-- mysql -u TU_USUARIO -p NOMBRE_DE_TU_BASE < database/migrations/001_mensajes_ocultos.sql
-- No elimina cuentas, vínculos, mensajes ni historial. Se puede repetir.

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
