/* =============================================================
   Noticias del sector — agregador
   Lee ./data/noticias.json (lo genera una GitHub Action cada 6 h)
   y pinta tarjetas con filtros, buscador y "Cargar más".
   Todo el texto procedente del JSON se inserta con textContent.

   Compatibilidad (no modificar):
   - Los nombres de campo del JSON y de categoría son exactamente los
     indicados, con tildes y mayúsculas. Un script externo genera el archivo.
   - "imagen" puede venir como null: se usa la imagen por defecto.
   - "extracto" puede venir vacío: entonces no se muestra ese bloque.
   - Las fechas vienen en ISO UTC; se muestran en hora de España.
   - Fuentes posibles: ASAJA Alicante, ASAJA Murcia, CARM - Agricultura,
     MAPA, Federación de Caza Región de Murcia, Federación de Caza
     Comunidad Valenciana, Real Federación Española de Caza.
   ============================================================= */
(function () {
  'use strict';

  // ---- Configuración ------------------------------------------------
  const seccion = document.getElementById('noticias');
  if (!seccion) return;
  // Rutas relativas (se pueden cambiar con data-json / data-img-default en la sección)
  const RUTA_JSON = seccion.dataset.json || './data/noticias.json';
  const IMG_DEFECTO = seccion.dataset.imgDefault || './img/noticia-default.jpg';
  const POR_PAGINA = 6;
  // Imagen propia por tema (no se usan las fotos de los medios: evita problemas de derechos de autor)
  const IMG_TEMA = {'Cítricos':'./img/agricola.jpg','Hortalizas':'./img/planes-abonado.jpg','Frutales':'./img/informes.jpg','Fitosanitarios':'./hero-maquinaria.jpg','Fertilización':'./img/planes-abonado.jpg','Riego y agua':'./img/planes-abonado.jpg','PAC y ayudas':'./norm-pac.jpg','Maquinaria':'./maq-area.jpg','Gestión de la explotación':'./img/cuaderno-campo.jpg','Agricultura ecológica':'./img/agricola.jpg','Mercados y precios':'./img/analisis-datos.jpg','Caza':'./cin-area.jpg'};
  function imagenTema(n){const c=(Array.isArray(n.categorias)&&n.categorias.length?n.categorias:[n.categoria||'General']);for(const x of c){if(IMG_TEMA[x])return IMG_TEMA[x];}return IMG_DEFECTO;}
  // Extracto breve (cita corta con enlace a la fuente)
  function corto(t,max){t=String(t||'').trim();if(t.length<=max)return t;return t.slice(0,max).replace(/\s+\S*$/,'').replace(/[.,;:]$/,'')+'…';}

  // Lista de categorías (nombres exactos que genera el script externo)
  const CATEGORIAS = ['Todas', 'Cítricos', 'Hortalizas', 'Frutales', 'Fitosanitarios', 'Fertilización', 'Riego y agua', 'PAC y ayudas', 'Maquinaria', 'Gestión de la explotación', 'Agricultura ecológica', 'Mercados y precios', 'Caza', 'General'];

  // ---- Referencias al DOM -------------------------------------------
  const elGrid = seccion.querySelector('#nt-grid');
  const elFiltros = seccion.querySelector('#nt-filtros');
  const elBuscar = seccion.querySelector('#nt-q');
  const elEstado = seccion.querySelector('#nt-estado');
  const elMas = seccion.querySelector('#nt-mas');
  const elUpd = seccion.querySelector('#nt-upd');

  // ---- Estado -------------------------------------------------------
  let todas = [];          // noticias ordenadas (más reciente primero)
  let filtradas = [];      // resultado de filtro + búsqueda
  let mostradas = 0;       // cuántas se están viendo
  let categoria = 'Todas';
  let consulta = '';

  // ---- Utilidades ---------------------------------------------------
  // Las fechas llegan en ISO UTC: se muestran siempre en hora de España
  const fmtFecha = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/Madrid' });
  const fmtFechaHora = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });

  // "1 oct. 2026" -> "1 oct 2026" (quita el punto de la abreviatura)
  function formatearFecha(iso, conHora) {
    const d = new Date(iso);
    if (isNaN(d)) return '';
    return (conHora ? fmtFechaHora : fmtFecha).format(d).replace(/\./g, '');
  }

  // Normaliza para buscar sin tildes ni mayúsculas
  function normalizar(s) {
    return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  // Solo se aceptan enlaces http/https (evita javascript: y similares)
  function urlSegura(u) {
    try {
      const url = new URL(u, location.href);
      return (url.protocol === 'http:' || url.protocol === 'https:') ? url.href : null;
    } catch (e) { return null; }
  }

  // Devuelve siempre una lista de categorías (acepta también el antiguo campo "categoria")
  function listaCategorias(n) {
    if (Array.isArray(n.categorias) && n.categorias.length) return n.categorias.filter(Boolean).map(String);
    if (n.categoria) return [String(n.categoria)];
    return ['General'];
  }

  function crear(tag, clase, texto) {
    const el = document.createElement(tag);
    if (clase) el.className = clase;
    if (texto != null) el.textContent = texto;
    return el;
  }

  // ---- Filtros (pastillas) ------------------------------------------
  function pintarFiltros() {
    CATEGORIAS.forEach(function (cat) {
      const b = crear('button', 'nt-pill', cat);
      b.type = 'button';
      b.setAttribute('aria-pressed', cat === categoria ? 'true' : 'false');
      b.addEventListener('click', function () {
        categoria = cat;
        elFiltros.querySelectorAll('.nt-pill').forEach(function (p) {
          p.setAttribute('aria-pressed', p.textContent === cat ? 'true' : 'false');
        });
        aplicar();
      });
      elFiltros.appendChild(b);
    });
  }

  // ---- Estado cargando: tarjetas esqueleto --------------------------
  function pintarEsqueleto(n) {
    elGrid.replaceChildren();
    for (let i = 0; i < n; i++) {
      const c = crear('div', 'nt-card nt-skel');
      c.setAttribute('aria-hidden', 'true');
      c.appendChild(crear('div', 'nt-img'));
      const b = crear('div', 'nt-body');
      [['30%', 18], ['92%', 14], ['78%', 14], ['100%', 11], ['60%', 11]].forEach(function (s) {
        const l = crear('div', 'sk'); l.style.width = s[0]; l.style.height = s[1] + 'px'; b.appendChild(l);
      });
      c.appendChild(b);
      elGrid.appendChild(c);
    }
    elGrid.setAttribute('aria-busy', 'true');
  }

  // ---- Tarjeta de noticia -------------------------------------------
  function crearTarjeta(n) {
    const href = urlSegura(n.url);
    const a = crear('a', 'nt-card');
    if (href) {
      a.href = href;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    }
    a.setAttribute('aria-label', (n.titulo || 'Noticia') + ' — ' + (n.fuente || '') + ' (se abre en una pestaña nueva)');

    // Imagen con reserva si falta o falla
    const fig = crear('div', 'nt-img');
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.decoding = 'async';
    img.alt = '';
    img.src = imagenTema(n);
    img.addEventListener('error', function () {
      if (!img.src.endsWith(IMG_DEFECTO.replace('./', ''))) img.src = IMG_DEFECTO;
    });
    fig.appendChild(img);
    a.appendChild(fig);

    const cuerpo = crear('div', 'nt-body');
    const meta = crear('div', 'nt-meta');
    // Máximo 2 etiquetas de categoría por tarjeta
    const etiquetas = document.createElement('span');
    etiquetas.className = 'nt-cats';
    listaCategorias(n).slice(0, 2).forEach(function (c) { etiquetas.appendChild(crear('span', 'nt-cat', c)); });
    meta.appendChild(etiquetas);
    const t = crear('time', 'nt-fecha', formatearFecha(n.fecha));
    if (n.fecha) t.dateTime = n.fecha;
    meta.appendChild(t);
    cuerpo.appendChild(meta);
    cuerpo.appendChild(crear('h3', 'nt-tit', n.titulo || ''));
    // Si el extracto viene vacío, no se muestra el bloque
    if (n.extracto && String(n.extracto).trim()) cuerpo.appendChild(crear('p', 'nt-ext', corto(n.extracto, 140)));
    const pie = crear('div', 'nt-pie');
    pie.appendChild(crear('span', 'nt-fuente', n.fuente || ''));
    pie.appendChild(crear('span', 'nt-leer', 'Seguir leyendo →'));
    cuerpo.appendChild(pie);
    a.appendChild(cuerpo);
    return a;
  }

  // ---- Filtrado + búsqueda ------------------------------------------
  function aplicar() {
    const q = normalizar(consulta.trim());
    filtradas = todas.filter(function (n) {
      // El filtro muestra la noticia si su nombre está en la lista "categorias"
      if (categoria !== 'Todas' && !listaCategorias(n).some(function (c) { return normalizar(c) === normalizar(categoria); })) return false;
      if (!q) return true;
      // Busca en titular, extracto y fuente (sin distinguir tildes ni mayúsculas)
      return normalizar(n.titulo).includes(q) || normalizar(n.extracto).includes(q) || normalizar(n.fuente).includes(q);
    });
    mostradas = 0;
    elGrid.replaceChildren();
    if (!filtradas.length) {
      mostrarEstado('No hay noticias que coincidan con tu búsqueda o filtro.', false);
    } else {
      ocultarEstado();
      cargarMas();
    }
    actualizarBoton();
  }

  // Añade las siguientes 12 tarjetas
  function cargarMas() {
    const lote = filtradas.slice(mostradas, mostradas + POR_PAGINA);
    const frag = document.createDocumentFragment();
    lote.forEach(function (n) { frag.appendChild(crearTarjeta(n)); });
    elGrid.appendChild(frag);
    mostradas += lote.length;
    actualizarBoton();
  }

  function actualizarBoton() {
    elMas.hidden = mostradas >= filtradas.length;
  }

  function mostrarEstado(texto, esError) {
    elEstado.textContent = texto;
    elEstado.classList.toggle('error', !!esError);
    elEstado.hidden = false;
  }
  function ocultarEstado() { elEstado.hidden = true; elEstado.textContent = ''; }

  // ---- Buscador (con pequeño retardo para no repintar en cada tecla) --
  let temporizador;
  elBuscar.addEventListener('input', function () {
    clearTimeout(temporizador);
    temporizador = setTimeout(function () { consulta = elBuscar.value; aplicar(); }, 200);
  });
  elMas.addEventListener('click', cargarMas);

  // ---- Carga del JSON -----------------------------------------------
  async function iniciar() {
    pintarFiltros();
    pintarEsqueleto(6);
    try {
      const resp = await fetch(RUTA_JSON, { cache: 'no-cache' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const datos = await resp.json();
      const lista = Array.isArray(datos.noticias) ? datos.noticias : [];
      // Ordenar de más reciente a más antigua
      todas = lista.slice().sort(function (a, b) { return new Date(b.fecha) - new Date(a.fecha); });
      // Última actualización
      const upd = formatearFecha(datos.actualizado, true);
      elUpd.replaceChildren(document.createTextNode('Última actualización: '), crear('b', null, upd || '—'));
      elGrid.removeAttribute('aria-busy');
      aplicar();
    } catch (e) {
      console.error('Noticias:', e);
      elGrid.replaceChildren();
      elGrid.removeAttribute('aria-busy');
      elMas.hidden = true;
      elUpd.textContent = 'Última actualización: —';
      mostrarEstado('No se han podido cargar las noticias. Inténtalo más tarde.', true);
    }
  }

  iniciar();
})();
