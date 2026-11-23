/* =============================================================
   Carrusel de noticias destacadas (portada)
   Lee ./data/noticias.json y ./data/plazos.json. Muestra 6 destacadas con cupos:
   hasta 2 ayudas con plazo abierto + agricultura (prioridad cítricos/hortalizas) + 1 de caza.
   Auto-avance cada 6 s; pausa al pasar el ratón, con foco o pestaña oculta.
   Flechas, puntos, teclado (← →) y deslizar en móvil.
   El listado completo está en noticias.html.
   ============================================================= */
(function () {
  'use strict';
  const sec = document.getElementById('noticias');
  const raiz = sec && sec.querySelector('#nc');
  if (!raiz) return;

  const RUTA_JSON = sec.dataset.json || './data/noticias.json';
  const IMG_DEFECTO = sec.dataset.imgDefault || './img/noticia-default.jpg';
  const NUM = 6, INTERVALO = 6000;
  const RUTA_PLAZOS = sec.dataset.plazos || './data/plazos.json';
  const IMG_PLAZO = './norm-subvenciones.jpg';
  // Prioridad de temas agrícolas (días de 'ventaja' sobre la fecha real)
  const PRIO = {'Daños y siniestros':8,'Jóvenes agricultores':6,'Modernización e inversiones':6,'Cítricos':4,'Hortalizas':4,'Frutales':3,'PAC y ayudas':3,'Maquinaria':3,'Fitosanitarios':2,'Fertilización':2,'Riego y agua':2,'Gestión de la explotación':2,'Agricultura ecológica':1,'Mercados y precios':1};
  const CAZA_UTIL = /plazo|veda|orden|temporada|convocatoria|ayuda|subvenci|licencia|precinto|da[ñn]os|jabal/i;
  // Imagen propia por tema (no se usan las fotos de los medios: evita problemas de derechos de autor)
  const IMG_TEMA = {'Daños y siniestros':'./img/informes.jpg','Jóvenes agricultores':'./norm-subvenciones.jpg','Modernización e inversiones':'./norm-subvenciones.jpg','Cítricos':'./img/agricola.jpg','Hortalizas':'./img/planes-abonado.jpg','Frutales':'./img/informes.jpg','Fitosanitarios':'./hero-maquinaria.jpg','Fertilización':'./img/planes-abonado.jpg','Riego y agua':'./img/planes-abonado.jpg','PAC y ayudas':'./norm-pac.jpg','Maquinaria':'./maq-area.jpg','Gestión de la explotación':'./img/cuaderno-campo.jpg','Agricultura ecológica':'./img/agricola.jpg','Mercados y precios':'./img/analisis-datos.jpg','Caza':'./cin-area.jpg'};
  function imagenTema(n){const c=(Array.isArray(n.categorias)&&n.categorias.length?n.categorias:[n.categoria||'General']);for(const x of c){if(IMG_TEMA[x])return IMG_TEMA[x];}return IMG_DEFECTO;}
  // Extracto breve (cita corta con enlace a la fuente)
  function corto(t,max){t=String(t||'').trim();if(t.length<=max)return t;return t.slice(0,max).replace(/\s+\S*$/,'').replace(/[.,;:]$/,'')+'…';}

  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const elTrack = raiz.querySelector('.nc-track');
  const elPuntos = raiz.querySelector('.nc-puntos');
  const elUpd = sec.querySelector('#nt-upd');
  let slides = [], puntos = [], actual = 0, timer = null, pausado = false, slidesTotal = NUM;

  const fmt = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/Madrid' });
  const fmtH = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });
  const fecha = (iso, h) => { const d = new Date(iso); return isNaN(d) ? '' : (h ? fmtH : fmt).format(d).replace(/\./g, ''); };
  const urlSegura = u => { try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : null; } catch (e) { return null; } };
  const crear = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const cats = n => Array.isArray(n.categorias) && n.categorias.length ? n.categorias : [n.categoria || 'General'];

  function crearSlidePlazo(n, i) {
    const a = crear('div', 'nc-slide nc-plazo');
    a.setAttribute('role', 'group');
    a.setAttribute('aria-label', (i + 1) + ' de ' + slidesTotal + ': ayuda con plazo abierto. ' + (n.titulo || ''));
    const img = document.createElement('img'); img.alt = ''; img.decoding = 'async'; img.loading = i === 0 ? 'eager' : 'lazy'; img.src = IMG_PLAZO;
    a.appendChild(img);
    const t = crear('div', 'nc-txt');
    const m = crear('div', 'nc-meta');
    m.appendChild(crear('span', 'nc-cat nc-cat-plazo', 'Plazo abierto'));
    const fin = n.fecha_fin ? 'Hasta el ' + fecha(n.fecha_fin + 'T12:00:00Z') : (n.texto_fin ? 'Plazo: ' + corto(n.texto_fin, 60) : '');
    m.appendChild(crear('span', null, [fin, n.ambito].filter(Boolean).join(' · ')));
    t.appendChild(m);
    t.appendChild(crear('h3', 'nc-tit', corto(n.titulo, 170)));
    const acc = crear('div', 'nc-acc');
    const href = urlSegura(n.url);
    if (href) { const v = crear('a', 'nc-leer', 'Ver convocatoria →'); v.href = href; v.target = '_blank'; v.rel = 'noopener noreferrer'; acc.appendChild(v); }
    const c = crear('a', 'nc-leer nc-leer-cta', 'Te ayudo a tramitarla →'); c.href = '#contacto';
    acc.appendChild(c);
    t.appendChild(acc);
    a.appendChild(t);
    return a;
  }

  function crearSlide(n, i) {
    if (n._plazo) return crearSlidePlazo(n, i);
    const danos = cats(n).includes('Daños y siniestros');
    const a = crear(danos ? 'div' : 'a', 'nc-slide');
    const href = urlSegura(n.url);
    if (href && !danos) { a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    if (danos) a.setAttribute('role', 'group');
    a.setAttribute('aria-label', (i + 1) + ' de ' + slidesTotal + ': ' + (n.titulo || 'Noticia'));
    const img = document.createElement('img');
    img.alt = ''; img.decoding = 'async';
    img.loading = i === 0 ? 'eager' : 'lazy';
    img.src = n._plazo ? IMG_PLAZO : imagenTema(n);
    img.addEventListener('error', () => { if (!img.src.endsWith(IMG_DEFECTO.replace('./', ''))) img.src = IMG_DEFECTO; });
    a.appendChild(img);
    const t = crear('div', 'nc-txt');
    const m = crear('div', 'nc-meta');
    const principal = cats(n).slice().sort((x, y) => (PRIO[y] || 0) - (PRIO[x] || 0))[0];
    m.appendChild(crear('span', 'nc-cat' + (principal === 'Daños y siniestros' ? ' nc-cat-plazo' : ''), principal));
    m.appendChild(crear('span', null, [fecha(n.fecha), n.fuente].filter(Boolean).join(' · ')));
    t.appendChild(m);
    t.appendChild(crear('h3', 'nc-tit', n.titulo || ''));
    if (n.extracto && String(n.extracto).trim()) t.appendChild(crear('p', 'nc-ext', corto(n.extracto, 140)));
    if (danos) {
      const acc = crear('div', 'nc-acc');
      if (href) { const v = crear('a', 'nc-leer', 'Leer noticia →'); v.href = href; v.target = '_blank'; v.rel = 'noopener noreferrer'; acc.appendChild(v); }
      const c = crear('a', 'nc-leer nc-leer-cta', '¿Te ha afectado? Informe de daños →'); c.href = '#contacto'; acc.appendChild(c);
      t.appendChild(acc);
    } else t.appendChild(crear('span', 'nc-leer', 'Leer noticia →'));
    a.appendChild(t);
    return a;
  }

  function ir(i) {
    actual = (i + slides.length) % slides.length;
    elTrack.style.transform = 'translateX(' + (-100 * actual) + '%)';
    slides.forEach((s, k) => {
      const on = k === actual;
      s.classList.toggle('activa', on);
      s.setAttribute('aria-hidden', on ? 'false' : 'true');
      s.tabIndex = on ? 0 : -1;
    });
    puntos.forEach((p, k) => p.setAttribute('aria-current', k === actual ? 'true' : 'false'));
  }
  function arrancar() { parar(); if (!sinMovimiento && !pausado && slides.length > 1) timer = setInterval(() => ir(actual + 1), INTERVALO); }
  function parar() { clearInterval(timer); timer = null; }

  function montar(lista) {
    elTrack.replaceChildren();
    elPuntos.replaceChildren();
    slidesTotal = lista.length;
    slides = lista.map(crearSlide);
    slides.forEach(s => elTrack.appendChild(s));
    puntos = slides.map((s, i) => {
      const b = crear('button', 'nc-punto');
      b.type = 'button';
      b.setAttribute('aria-label', 'Ir a la noticia ' + (i + 1));
      b.addEventListener('click', () => { ir(i); arrancar(); });
      elPuntos.appendChild(b);
      return b;
    });
    const unica = slides.length < 2;
    raiz.querySelectorAll('.nc-flecha').forEach(b => { b.hidden = unica; });
    elPuntos.hidden = unica;
    ir(0); arrancar();
  }

  // Controles
  raiz.querySelector('.nc-prev').addEventListener('click', () => { ir(actual - 1); arrancar(); });
  raiz.querySelector('.nc-next').addEventListener('click', () => { ir(actual + 1); arrancar(); });
  raiz.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') { ir(actual - 1); arrancar(); }
    if (e.key === 'ArrowRight') { ir(actual + 1); arrancar(); }
  });
  raiz.addEventListener('mouseenter', () => { pausado = true; parar(); });
  raiz.addEventListener('mouseleave', () => { pausado = false; arrancar(); });
  raiz.addEventListener('focusin', () => { pausado = true; parar(); });
  raiz.addEventListener('focusout', () => { pausado = false; arrancar(); });
  document.addEventListener('visibilitychange', () => { document.hidden ? parar() : arrancar(); });

  // Deslizar en móvil (evita abrir el enlace si fue un gesto)
  let x0 = null, arrastre = false;
  elTrack.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; arrastre = false; parar(); }, { passive: true });
  elTrack.addEventListener('touchmove', e => { if (x0 != null && Math.abs(e.touches[0].clientX - x0) > 10) arrastre = true; }, { passive: true });
  elTrack.addEventListener('touchend', e => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 45) ir(actual + (dx < 0 ? 1 : -1));
    x0 = null; arrancar();
  });
  elTrack.addEventListener('click', e => { if (arrastre) { e.preventDefault(); arrastre = false; } }, true);

  // Selección con cupos: hasta 2 plazos abiertos, 1 de caza y el resto agricultura
  function seleccionar(noticias, plazos) {
    const hoy = new Date().toISOString().slice(0, 10);
    const abiertos = plazos.filter(p => !p.fecha_fin || p.fecha_fin >= hoy).slice(0, 2).map(p => Object.assign({ _plazo: true }, p));
    const t = n => new Date(n.fecha).getTime() || 0;
    const DIA = 864e5;
    const esCaza = n => cats(n).includes('Caza');
    const agri = noticias.filter(n => !esCaza(n))
      .map(n => ({ n, s: t(n) + DIA * Math.max(0, ...cats(n).map(c => PRIO[c] || 0)) }))
      .sort((a, b) => b.s - a.s).map(x => x.n);
    const caza = noticias.filter(esCaza)
      .map(n => ({ n, s: t(n) + (CAZA_UTIL.test(n.titulo + ' ' + (n.extracto || '')) ? 3 * DIA : 0) }))
      .sort((a, b) => b.s - a.s).map(x => x.n);
    const huecosAgri = NUM - abiertos.length - (caza.length ? 1 : 0);
    const elegidas = agri.slice(0, huecosAgri).concat(caza.slice(0, 1));
    // Si faltan agrícolas, se completa con caza
    for (const n of caza.slice(1)) { if (abiertos.length + elegidas.length >= NUM) break; elegidas.push(n); }
    // Intercala: plazo, noticia, plazo, noticia...
    const out = [];
    const cola = elegidas.slice();
    abiertos.forEach(p => { out.push(p); if (cola.length) out.push(cola.shift()); });
    return out.concat(cola).slice(0, NUM);
  }

  // Carga
  (async function () {
    try {
      const r = await fetch(RUTA_JSON, { cache: 'no-cache' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      let plazos = [];
      try { const rp = await fetch(RUTA_PLAZOS, { cache: 'no-cache' }); if (rp.ok) plazos = (await rp.json()).plazos || []; } catch (e) { /* sin plazos */ }
      const lista = seleccionar(Array.isArray(d.noticias) ? d.noticias : [], plazos);
      if (elUpd) elUpd.replaceChildren(document.createTextNode('Última actualización: '), crear('b', null, fecha(d.actualizado, true) || '—'));
      if (!lista.length) throw new Error('sin noticias');
      montar(lista);
    } catch (e) {
      console.error('Carrusel noticias:', e);
      raiz.hidden = true;
      if (elUpd) elUpd.textContent = 'Última actualización: —';
    }
  })();
})();
