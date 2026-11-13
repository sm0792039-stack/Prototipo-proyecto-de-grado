# Cambios y validación de My Remember

La revisión contrastó el ZIP con los tres documentos Word. Se usó v1.2 como referencia principal porque especifica los flujos y reconoce los límites del prototipo. La petición añadía código visible, mensajes en ambos sentidos y opciones de borrado.

## Qué se corrigió y añadió

| Necesidad | Resultado en esta entrega |
| --- | --- |
| Código de vinculación que desaparecía | Código permanente en Inicio y Familia, con controles para copiar/compartir. Continúa visible después del primer vínculo. |
| Registro familiar con código | Admite códigos pegados con espacios, minúsculas o sin guion; mantiene cuentas y familias separadas. |
| Control de invitaciones | El adulto puede renovar su código. El anterior deja de aceptar nuevas cuentas; los miembros vinculados conservan acceso. |
| Comunicación limitada al cuidador | Conversación compartida bidireccional con nombre, fecha y lectura en voz alta. Se rechazan mensajes vacíos o mayores de 500 caracteres. |
| Borrado de mensajes | Borrar para mí oculta solo en la cuenta actual. Borrar para todos está reservado al autor y elimina el original y sus ocultaciones. El historial no duplica el texto del mensaje. |
| Monitoreo familiar | Resumen diario y actividad compartida, con consulta periódica de cambios mientras las pantallas están abiertas. Describe confirmaciones registradas, sin inferir el estado de salud. |
| Frecuencia incorrecta | Una vez genera la ocurrencia del día de alta; semanal respeta su día de semana; diario genera una por día. No se duplican por recargar. |
| Posposición de recordatorios atrasados | Calcula 15 minutos desde la hora actual, cierra avisos anteriores y permite nuevos avisos si vuelve a vencer. Evita envolver un horario a la madrugada al cruzar medianoche. |
| Acciones repetidas | Confirmar o indicar no realizado conserva una única respuesta; un doble envío no duplica el evento de confirmación. |
| Citas ausentes del destacado | Las citas confirmadas se incluyen en la prioridad del día; las canceladas se excluyen. Se rechazan nuevas citas o reprogramaciones en el pasado. |
| Organización del plan | Ambos perfiles pueden gestionar su agenda compartida. La edición conserva confirmaciones anteriores; desactivar recordatorios o cancelar citas conserva sus registros. |
| Aviso mal llamado push | Se presenta como resaltar un recordatorio dentro de la aplicación. No anuncia una notificación externa que no existe. |
| Seguridad básica | CSRF en formularios, logout por POST, validación en servidor, controles de rol/familia, contraseñas de al menos 8 caracteres y límite de intentos de ingreso. |
| Instalación y actualización | SQLite para prueba local sin MySQL; compatibilidad con configuración MySQL previa y migración no destructiva. La entrega excluye secretos, bases personales y entornos virtuales. |
| Información y accesibilidad | Aviso de privacidad accesible antes del registro, opciones de lectura/contraste/tamaño, navegación y controles rotulados. |

## Resultado de la verificación

La copia de entrega, sin `.env` ni bases previas, pasó **36 pruebas automatizadas** con Python 3.12 y SQLite. También se comprobó manualmente el límite de intentos de ingreso y la integridad de claves foráneas SQLite.

En Chromium se recorrió el flujo real con dos cuentas independientes y CSRF activo: registro, copia de código, vinculación, conversación y borrado en ambos perfiles, creación de citas y recordatorios, confirmación y actualización automática del panel familiar. Se revisaron pantallas de 390 y 320 píxeles, textos sin espacios de longitud máxima y Modo Fácil con texto muy grande y alto contraste. No se detectaron errores JavaScript ni fallos de recursos internos en esas comprobaciones.

## Cómo repetir las pruebas

Desde la raíz del proyecto, con el entorno virtual activado:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Las pruebas de `tests/test_app.py` crean una base SQLite en memoria por caso. Usan familias ficticias y no envían información a servicios externos. Cubren:

- Alta de adulto, aparición permanente del código y vinculación posterior del cuidador.
- Validación del registro y renovación de invitaciones conservando miembros existentes.
- Mensajes enviados por ambos roles, borrado individual/global y prohibición de borrar para todos mensajes ajenos.
- Aislamiento entre familias al leer pantallas, modificar registros, citas, alertas o mensajes, y consultar la huella de actualización.
- Recurrencia una vez/diaria/semanal, conversión de fecha UTC a Bogotá y ausencia de ocurrencias duplicadas.
- Alertas después del umbral, posposición desde ahora, protección al cruzar medianoche y respuestas terminales sin duplicar historial.
- Edición de horarios pendientes conservando registros ya confirmados, citas futuras y cancelación sin pérdida de historial.
- CSRF, rutas por rol, cierre de sesión por POST y acceso al aviso de privacidad.

La configuración de pruebas desactiva CSRF para aislar los flujos funcionales; un caso separado lo activa y verifica tanto el rechazo sin token como la aceptación de un token válido. El límite de intentos se desactiva en estas pruebas para evitar que interfiera con los registros ficticios.

La ejecución utiliza SQLite y el cliente de pruebas de Flask. No equivale a validar el motor MySQL, la instalación Windows, la disponibilidad de un servidor o la experiencia de las personas de la comunidad. Las comprobaciones de navegador de la entrega deben interpretarse dentro del entorno en que se ejecutaron.

## Prueba de aceptación con dos navegadores

Usa una ventana normal y otra privada, o dos navegadores, apuntando al mismo servidor. Empieza con datos ficticios.

1. En la primera ventana, registra al adulto. Verifica el código en Inicio y Familia y recarga para confirmar que continúa visible.
2. En la segunda ventana, registra al cuidador con ese código. Comprueba el nombre del adulto en Seguimiento y el nombre del cuidador en Familia. El código del adulto debe seguir disponible.
3. Envía un mensaje desde cada ventana. Comprueba autor, contenido y aparición en la conversación del otro perfil; espera hasta 30 segundos o recarga.
4. En el receptor, elige Borrar para mí. El mensaje debe desaparecer solo allí. Desde el autor, borra un mensaje propio para todos y verifica que desaparece en ambas cuentas. El receptor no debe tener permiso de borrado global de un mensaje ajeno.
5. Desde el cuidador, crea un recordatorio y una cita futura. Comprueba que aparecen en la agenda del adulto. Confirma el recordatorio como adulto y verifica el cambio en el panel familiar. Prueba la posposición con otro recordatorio pendiente.
6. Crea un recordatorio de actividad ficticia con más de 30 minutos de retraso. Al consultar la aplicación debe generarse un aviso familiar. Resáltalo, comprueba la señal dentro de la pantalla del adulto y después confirma la actividad.
7. Prueba texto muy grande, alto contraste, lectura en voz alta, teclado y una pantalla móvil. Comprueba que las acciones siguen accesibles.
8. Renueva el código desde la cuenta del adulto. El código anterior debe fallar para una nueva inscripción; el cuidador existente debe conservar acceso.
9. Cierra sesión y vuelve a ingresar. Verifica que la información persiste y que cada perfil accede a su propia familia.

Una prueba con medicamentos ficticios comprueba el software; no representa una recomendación de tratamiento ni verifica la toma real de medicamentos.

## Límites que permanecen

- Un adulto mayor por familia y varios cuidadores. La conversación es de grupo y sus integrantes comparten el plan y la información mostrada.
- No hay Web Push, SMS o correo con la aplicación cerrada. Las verificaciones y actualizaciones dependen de consultas al servidor mientras alguien usa la aplicación.
- No existe selector de una fecha de inicio futura para recordatorios. Una vez y semanal se anclan al día de creación. No se traslada una posposición al día siguiente.
- Renovar una invitación no revoca cuentas ya vinculadas. La interfaz no incluye todavía desvinculación de miembros ni recuperación de contraseña por correo.
- El aviso de privacidad requiere datos y procedimientos del responsable del piloto. Un código compartido no sustituye las autorizaciones que correspondan para datos sensibles.
- El límite de intentos de ingreso funciona por proceso. El operador debe preparar HTTPS, permisos de base, respaldos y controles operativos antes de un uso público.
- No se realizó validación de campo ni evaluación clínica. Tampoco se declara certificación WCAG o cumplimiento legal integral. My Remember no diagnostica, no prescribe y no se conecta a las agendas de las EPS.

Los documentos plantean una implementación comunitaria, pero v1.2 describe los resultados previos como pruebas de laboratorio. Estas mejoras preparan un prototipo verificable para continuar la evaluación; no acreditan despliegue comunitario ni los beneficios sociales esperados en el proyecto.
