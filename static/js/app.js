/* My Remember: accesibilidad, vinculación y actualización de la familia. */
document.addEventListener('DOMContentLoaded', function () {
  inicializarModoFacil();
  inicializarLecturaEnVozAlta();
  inicializarCodigoFamilia();
  inicializarMensajes();
  inicializarConfirmaciones();
  inicializarSeguimiento();
});

function inicializarModoFacil() {
  const raiz = document.documentElement;
  const leer = function (clave) { try { return localStorage.getItem(clave); } catch (_) { return null; } };
  const guardar = function (clave, valor) { try { localStorage.setItem(clave, valor); } catch (_) { /* Preferencia solo durante esta visita. */ } };
  const botones = document.querySelectorAll('[data-tamano]');
  function aplicarTamano(tamano) {
    raiz.classList.toggle('texto-grande', tamano === 'grande');
    raiz.classList.toggle('texto-muy-grande', tamano === 'muy-grande');
    botones.forEach(function (boton) {
      const activo = boton.dataset.tamano === tamano;
      boton.classList.toggle('active', activo);
      boton.setAttribute('aria-pressed', String(activo));
    });
  }
  aplicarTamano(leer('mr_tamano_texto') || 'normal');
  botones.forEach(function (boton) {
    boton.addEventListener('click', function () {
      aplicarTamano(boton.dataset.tamano);
      guardar('mr_tamano_texto', boton.dataset.tamano);
    });
  });
  const interruptor = document.getElementById('interruptorContraste');
  const contraste = leer('mr_alto_contraste') === 'on';
  raiz.classList.toggle('alto-contraste', contraste);
  if (interruptor) {
    interruptor.checked = contraste;
    interruptor.addEventListener('change', function () {
      raiz.classList.toggle('alto-contraste', interruptor.checked);
      guardar('mr_alto_contraste', interruptor.checked ? 'on' : 'off');
    });
  }
}

function inicializarLecturaEnVozAlta() {
  document.querySelectorAll('.btn-hablar').forEach(function (boton) {
    if (!('speechSynthesis' in window)) {
      boton.disabled = true;
      boton.title = 'La lectura en voz alta no está disponible en este navegador.';
      return;
    }
    boton.addEventListener('click', function () {
      if (!boton.dataset.texto) return;
      window.speechSynthesis.cancel();
      const mensaje = new SpeechSynthesisUtterance(boton.dataset.texto);
      mensaje.lang = 'es-CO';
      mensaje.rate = 0.9;
      window.speechSynthesis.speak(mensaje);
    });
  });
}

function inicializarCodigoFamilia() {
  const campo = document.getElementById('codigoFamilia');
  const estado = document.getElementById('estadoCodigo');
  if (!campo || !estado) return;
  async function copiar() {
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error('manual');
      await navigator.clipboard.writeText(campo.value);
      estado.textContent = 'Código copiado. Ya puedes pegarlo en un mensaje para tu familiar.';
    } catch (_) {
      campo.focus();
      campo.select();
      campo.setSelectionRange(0, campo.value.length);
      let copiado = false;
      try { copiado = document.execCommand('copy'); } catch (_) { /* Selección manual disponible. */ }
      estado.textContent = copiado ? 'Código copiado. Compártelo con alguien de confianza.' : 'El código quedó seleccionado. Mantén pulsado o usa Copiar para compartirlo.';
    }
  }
  document.querySelectorAll('[data-copiar-codigo]').forEach(function (boton) { boton.addEventListener('click', copiar); });
  document.querySelectorAll('[data-compartir-codigo]').forEach(function (boton) {
    boton.addEventListener('click', async function () {
      if (!navigator.share) { await copiar(); return; }
      try {
        await navigator.share({title: 'Acompáñame en My Remember', text: 'Mi código de familia es ' + campo.value + '. Crea tu cuenta de Familiar / Cuidador en ' + window.location.origin + '/registro/familiar para acompañarme.'});
        estado.textContent = 'Tu código está listo para compartir.';
      } catch (error) { if (error.name !== 'AbortError') await copiar(); }
    });
  });
}

function inicializarMensajes() {
  document.querySelectorAll('textarea[data-contador]').forEach(function (campo) {
    const contador = document.getElementById(campo.dataset.contador);
    function actualizar() { if (contador) contador.textContent = campo.value.length + ' / ' + campo.maxLength + ' caracteres'; }
    campo.addEventListener('input', actualizar);
    actualizar();
  });
  document.querySelectorAll('[data-mensaje]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      const campo = document.getElementById('contenido');
      if (!campo || campo.disabled) return;
      campo.value = boton.dataset.mensaje;
      campo.dispatchEvent(new Event('input', {bubbles: true}));
      campo.focus();
    });
  });
}

function inicializarConfirmaciones() {
  document.querySelectorAll('form[data-confirm]').forEach(function (formulario) {
    formulario.addEventListener('submit', function (evento) {
      if (!window.confirm(formulario.dataset.confirm)) evento.preventDefault();
    });
  });
}

function inicializarSeguimiento() {
  const url = document.body.dataset.estadoUrl;
  if (!url) return;
  const versionInicial = document.body.dataset.estadoVersion;
  const aviso = document.getElementById('novedades');
  const boton = document.getElementById('actualizarDatos');
  const estado = document.getElementById('estadoActualizacion');
  let consultando = false;
  let hayNovedades = false;
  // Las ediciones permanecen en la página; nunca se recarga un formulario con cambios.
  function editando() {
    if (document.querySelector('.modal.show, .offcanvas.show')) return true;
    const foco = document.activeElement;
    if (foco && foco.matches('input,textarea,select,[contenteditable="true"]')) return true;
    return Array.from(document.querySelectorAll('form input:not([type="hidden"]),form textarea,form select')).some(function (campo) {
      if (campo.type === 'checkbox' || campo.type === 'radio') return campo.checked !== campo.defaultChecked;
      if (campo.tagName === 'SELECT') return Array.from(campo.options).some(function (opcion) { return opcion.selected !== opcion.defaultSelected && !(campo.selectedIndex === 0 && !Array.from(campo.options).some(function (o) { return o.defaultSelected; })); });
      return campo.value !== campo.defaultValue;
    });
  }
  function actualizar() {
    if (editando()) {
      if (estado) estado.textContent = 'Termina de editar o envía tu mensaje antes de actualizar. Tu texto se conserva.';
      return;
    }
    window.location.reload();
  }
  if (boton) boton.addEventListener('click', actualizar);
  async function consultar() {
    if (consultando || document.hidden || !navigator.onLine) return;
    consultando = true;
    try {
      const respuesta = await fetch(url, {cache: 'no-store', credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!respuesta.ok || !respuesta.headers.get('content-type')?.includes('application/json')) return;
      const datos = await respuesta.json();
      if (String(datos.version) !== String(versionInicial)) {
        hayNovedades = true;
        if (editando()) { if (aviso) aviso.hidden = false; }
        else actualizar();
      }
    } catch (_) { /* La página actual sigue disponible si se pierde conexión. */ }
    finally { consultando = false; }
  }
  window.setInterval(consultar, 30000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) consultar(); });
  document.addEventListener('focusout', function () {
    if (hayNovedades && aviso) aviso.hidden = false;
  });
}
