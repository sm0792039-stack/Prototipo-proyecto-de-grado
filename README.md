# My Remember — prototipo mejorado

Aplicación web para organizar recordatorios, citas y comunicación entre un adulto mayor y sus familiares o cuidadores. Conserva Flask, SQLAlchemy y las vistas HTML del prototipo; funciona con SQLite para una prueba local y con MySQL para continuar una instalación existente.

La revisión toma los tres Word como referencia funcional y prioriza v1.2, que desarrolla los requisitos con mayor detalle. El resumen de cambios y las pruebas están en [MEJORAS_Y_VALIDACION.md](MEJORAS_Y_VALIDACION.md).

## Instalación nueva para probar

Requisitos: Python 3.10 o superior, `pip` y un navegador actualizado. Se necesita conexión para instalar dependencias. Bootstrap, sus iconos y sus estilos se incluyen localmente; no requieren un CDN durante el uso.

Descomprime el proyecto y abre una terminal dentro de `my_remember`.

**Windows, PowerShell:**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python app.py
```

Si PowerShell impide activar el entorno, puedes ejecutar directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe app.py
```

**macOS o Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python app.py
```

`requirements-lock.txt` fija las versiones verificadas de las dependencias. `requirements.txt` conserva sus rangos para futuras actualizaciones.

Abre **http://localhost:5000**. En una instalación sin configuración previa, la aplicación crea las tablas y guarda los datos en `instance/my_remember.db`. También genera una clave local en `instance/secret_key`. Se conservan al cerrar y volver a abrir el servidor. `Ctrl+C` lo detiene.

No hace falta instalar MySQL para esta prueba. El ZIP no incluye `.env`, bases de datos ni un entorno virtual: se generan o configuran en tu equipo. `.env.example` describe las opciones; copiarlo a `.env` es opcional para una instalación nueva.

## Continuar con una base MySQL existente

1. Guarda un respaldo de la base actual y de tu configuración local.
2. Conserva tu `.env` anterior con `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` y `SECRET_KEY`. No lo reemplaces por `.env.example`.
3. Instala las dependencias de esta versión y ejecuta:

```bash
python create_tables.py
python app.py
```

`create_tables.py` crea las tablas faltantes sin vaciar las existentes. Esta mejora añade `mensajes_ocultos`; no requiere modificar las columnas anteriores. También puedes aplicar únicamente [la migración SQL](database/migrations/001_mensajes_ocultos.sql) desde MySQL:

```bash
mysql -u TU_USUARIO -p NOMBRE_DE_TU_BASE < database/migrations/001_mensajes_ocultos.sql
```

En Windows, ese comando puede ejecutarse en CMD o desde la opción de ejecutar scripts de MySQL Workbench. Más detalles en [database/migrations/README.md](database/migrations/README.md).

`DATABASE_URL` tiene prioridad sobre las variables `DB_*`. Si conservas MySQL, elimina una posible línea `DATABASE_URL=sqlite:///my_remember.db` del `.env` de ejemplo. La base debe existir y el usuario necesita permisos para crear la tabla nueva. La actualización conserva cuentas, códigos, vínculos, mensajes e historial. El esquema SQL completo también es no destructivo, pero selecciona expresamente `my_remember_db`; usa la migración si tu base tiene otro nombre.

## Vincular al adulto mayor y al cuidador

1. Crea primero la cuenta de **Adulto mayor**. El código se muestra permanentemente en Inicio y Familia.
2. Copia o comparte ese código con la persona elegida. Permite consultar el plan, las citas, las confirmaciones y la conversación del grupo.
3. En otro navegador o una ventana privada, crea la cuenta de **Familiar o cuidador** e ingresa el código. Ambos acceden a la misma familia con cuentas distintas.
4. El código permanece disponible aunque ya exista un cuidador. **Renovar código**, disponible para el adulto, impide nuevos registros con el código anterior. Conserva el acceso de los miembros ya vinculados.

La aplicación admite un adulto mayor y varios cuidadores por familia. Los mensajes forman una conversación compartida con todos los integrantes vinculados.

## Uso diario

- **Adulto mayor:** Inicio reúne las actividades y citas del día. En Recordatorios puede confirmar con **Ya lo hice**, aplazar 15 minutos o indicar **No lo hice**; también puede organizar sus recordatorios y citas. En Familia consulta contactos, código y mensajes.
- **Familiar o cuidador:** Seguimiento muestra confirmaciones, pendientes, pospuestos y avisos; Plan de cuidado permite crear, editar y desactivar recordatorios o cancelar citas conservando el historial. Historial permite filtrar las actividades.
- **Mensajes:** ambos perfiles pueden enviar hasta 500 caracteres. **Borrar para mí** oculta el mensaje solo en esa cuenta. El autor puede **Borrar para todos** y elimina el mensaje de la conversación del grupo. Una persona no puede borrar para todos un mensaje enviado por otra.
- **Modo Fácil:** tamaño de texto, alto contraste y lectura en voz alta, según el soporte del navegador. Las preferencias visuales se guardan en ese navegador.

Las fechas y horarios usan `America/Bogota`. Los datos anteriores se conservan sin desplazar sus timestamps; revisa las horas históricas si tu instalación anterior usaba otra zona o guardaba horas locales en campos de auditoría. “Una vez” corresponde al día de creación; “Semanal”, al mismo día de la semana del alta; “Diario”, a cada día desde el alta. Esta versión no permite elegir una fecha inicial futura. Posponer un recordatorio atrasado cuenta 15 minutos desde ahora; si eso cruza medianoche, la aplicación informa que no puede aplazarlo al día siguiente.

Los cambios se consultan aproximadamente cada 30 segundos en las pantallas de seguimiento y conversación abiertas. La actualización respeta formularios en edición. El aviso **Resaltar recordatorio** se muestra dentro de la aplicación. **No hay notificaciones push, SMS ni correo con la aplicación cerrada.** La ausencia de una confirmación no demuestra que se incumplió un tratamiento.

## Datos de demostración, opcionales

Solo para una base de prueba:

```bash
python seed.py
```

| Perfil | Correo |
| --- | --- |
| Adulto mayor | `maria@familiagarcia.com` |
| Familiar | `laura@familiagarcia.com` |
| Cuidador | `juan@familiagarcia.com` |

Contraseña de estas tres cuentas: `Remember2026`. Código de demostración: `FAM-MARGARITAS1`. Son ejemplos ficticios; los medicamentos y sus notas no constituyen indicaciones médicas. El script conserva una familia de demostración que ya exista.

## Pruebas automatizadas

Con el entorno virtual activado:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

La suite usa SQLite temporal, cuentas ficticias y horarios controlados. No modifica la base de trabajo. Comprueba registro y código, comunicación en ambos sentidos, borrado, aislamiento entre familias, frecuencias, aplazamiento, confirmaciones, citas y protección de formularios. No acredita pruebas con MySQL real, con la comunidad o resultados clínicos.

## Preparar un servidor

`python app.py` inicia Flask sin modo de depuración y sirve para la prueba local. Para un servidor, configura una `SECRET_KEY` privada y estable, usa HTTPS mediante un proxy y establece `COOKIE_SECURE=1`. Puedes generar una clave en tu propia terminal:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Guárdala en el `.env` privado o en las variables del servidor. Para ejecutar la aplicación detrás del proxy:

```bash
waitress-serve --host=127.0.0.1 --port=5000 app:app
```

Para una prueba HTTP local deja `COOKIE_SECURE=0`; una cookie marcada como segura requiere HTTPS. Los dispositivos distintos deben conectarse al mismo servidor publicado; `localhost` siempre representa el equipo desde el que se abre el navegador.

Antes de usar datos personales reales, el responsable del piloto debe completar los datos de contacto y las finalidades del aviso de privacidad, definir autorizaciones y gestión de acceso, preparar respaldos y verificar la instalación HTTPS. La página de privacidad es una base informativa y requiere la configuración del operador. Las protecciones implementadas no constituyen por sí solas una certificación legal o de accesibilidad.

El límite de intentos de ingreso es por proceso; un despliegue distribuido necesita un límite compartido en el proxy o servicio equivalente. La recuperación de contraseña por correo y la desvinculación de miembros desde la interfaz siguen pendientes. Esta aplicación no diagnostica, no prescribe y no reemplaza la atención médica.
