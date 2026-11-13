# Actualización de una instalación existente

La mejora de mensajes agrega únicamente la tabla `mensajes_ocultos`. Los modelos
anteriores no necesitan columnas nuevas. La eliminación para todos elimina el
mensaje original y sus ocultaciones; la eliminación para mí conserva el original
para los otros integrantes de la familia.

Antes de actualizar una base existente, guarde un respaldo. A continuación:

```bash
mysql -u TU_USUARIO -p NOMBRE_DE_TU_BASE < database/migrations/001_mensajes_ocultos.sql
```

La migración es idempotente y no borra datos. Para bases vacías puede utilizar
`database/schema.sql` o el comando de inicialización de la aplicación. El esquema
SQL ya no contiene `DROP TABLE`: ejecutarlo no reinicia ni vacía la base existente.
En SQLite, la creación de tablas por SQLAlchemy agrega también la tabla nueva.

Los códigos de familia anteriores siguen siendo válidos hasta que el adulto mayor
pulse **Renovar código**. Esa acción invalida invitaciones anteriores, sin cambiar
la familia ni el acceso de quienes ya estaban vinculados. Los mensajes del
prototipo anterior se conservan en la conversación compartida de su familia.
