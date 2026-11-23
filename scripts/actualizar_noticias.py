"""
Agregador de noticias: lee los RSS de config.json y genera data/noticias.json.
- Acumula noticias (no sobrescribe): conserva las de los últimos N días.
- Si una fuente falla, se mantienen sus noticias anteriores.
- Asigna categoría por palabras clave.
Uso: python scripts/actualizar_noticias.py
"""
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "scripts" / "config.json"
SALIDA = RAIZ / "data" / "noticias.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (agregador de noticias agrarias; GitHub Actions)"}
AHORA = datetime.now(timezone.utc)


def limpiar_html(texto):
    """Quita etiquetas HTML, entidades y espacios sobrantes."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def recortar(texto, n):
    if len(texto) <= n:
        return texto
    return texto[:n].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def compilar_categorias(categorias):
    """Convierte las palabras clave en expresiones regulares.
    'naranja*' = empieza por; 'pac' = palabra exacta."""
    compiladas = []
    for nombre, palabras in categorias.items():
        patrones = []
        for p in palabras:
            p = re.escape(p.lower()).replace(r"\*", r"\w*")
            patrones.append(r"(?<!\w)" + p + r"(?!\w)")
        compiladas.append((nombre, re.compile("|".join(patrones))))
    return compiladas


def categorizar(texto, categorias, por_defecto, siempre=None):
    """Devuelve TODAS las categorías que coinciden (lista)."""
    texto = texto.lower()
    encontradas = [nombre for nombre, patron in categorias if patron.search(texto)]
    if siempre and siempre not in encontradas:
        encontradas.insert(0, siempre)
    return encontradas or [por_defecto]


# Zona de trabajo: provincia de Alicante (sobre todo Vega Baja, Elche y Crevillent)
# y Murcia limítrofe. Una noticia de siniestros fuera de la zona no se destaca.
ZONA = re.compile(
    r"vega baja|bajo segura|orihuela|callosa|almorad|dolores|catral|\bcox\b|redov[aá]n|rafal|benej[uú]zar|"
    r"benferri|bigastro|jacarilla|algorfa|daya|formentera del segura|rojales|guardamar|torrevieja|"
    r"pilar de la horadada|san fulgencio|benij[oó]far|granja de rocamora|albatera|san isidro|"
    r"crevillen|elche|\belx\b|alicante|alacant|r[ií]o segura|beniel|santomera|abanilla|fortuna",
    re.I)


def aplicar_zona(texto, cats):
    """Marca si la noticia es de la zona; quita 'Daños y siniestros' si el siniestro es de fuera."""
    local = bool(ZONA.search(texto))
    if "Daños y siniestros" in cats and not (local or re.search(r"valencian", texto, re.I)):
        cats = [c for c in cats if c != "Daños y siniestros"] or ["General"]
    return cats, local


def compilar_exclusion(cfg):
    """Prepara el filtro de temas descartados (p. ej. pesca).
    'ignorar_frases' se borran antes de comprobar, para que el nombre del
    Ministerio de Agricultura, Pesca y Alimentación no descarte noticias agrícolas."""
    palabras = cfg.get("excluir_si_contiene", [])
    if not palabras:
        return None
    patron = compilar_categorias({"_": palabras})[0][1]
    frases = [re.compile(re.escape(f.lower())) for f in cfg.get("ignorar_frases", [])]
    return patron, frases


POLITICA = re.compile(
    r"partido popular|\bpp\b|psoe|\bvox\b|podemos|sumar|compromís|compromis|feij[oó]o|pedro s[aá]nchez|"
    r"tellado|abascal|elecciones|campaña electoral|votar|mitin|candidat", re.I)


def es_excluida(texto, categorias_noticia, exclusion):
    if POLITICA.search(texto):  # la web es técnica y neutral: nada de política de partidos
        return True
    """True si la noticia trata de un tema descartado y no es de caza."""
    if not exclusion or "Caza" in categorias_noticia:
        return False
    patron, frases = exclusion
    texto = texto.lower()
    for f in frases:
        texto = f.sub(" ", texto)
    return bool(patron.search(texto))


def fecha_iso(entrada):
    """Fecha de la noticia; None si el feed no la trae (p. ej. MAPA)."""
    for campo in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entrada.get(campo)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def extraer_imagen(entrada):
    for campo in ("media_content", "media_thumbnail"):
        for m in entrada.get(campo, []) or []:
            if m.get("url"):
                return m["url"]
    for enl in entrada.get("links", []):
        if enl.get("rel") == "enclosure" and str(enl.get("type", "")).startswith("image"):
            return enl.get("href")
    contenido = entrada.get("summary", "")
    if entrada.get("content"):
        contenido += entrada["content"][0].get("value", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', contenido)
    return html.unescape(m.group(1)) if m else None


def imagen_de_pagina(url):
    """Si el feed no trae imagen, busca la imagen de portada de la noticia
    (etiqueta og:image / twitter:image que el propio medio publica para compartirla)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        cab = r.text[:200000]
        for patron in (r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)',
                       r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)'):
            m = re.search(patron, cab, re.I)
            if m:
                return requests.compat.urljoin(url, html.unescape(m.group(1)).strip())
    except Exception:
        pass
    return None


# Enlaces oficiales que se buscan dentro de una noticia (para no enlazar a la fuente intermedia)
OFICIALES = [
    ("infosubvenciones.es", "BDNS"), ("pap.hacienda.gob.es/bdnstrans", "BDNS"),
    ("dogv.gva.es", "DOGV"), ("boe.es", "BOE"), ("borm.es", "BORM"), ("sede.gva.es", "Sede GVA"),
    ("agroambient.gva.es", "Conselleria de Agricultura"), ("gva.es", "Generalitat Valenciana"),
    ("mapa.gob.es", "Ministerio de Agricultura"), ("fega.gob.es", "FEGA"), ("carm.es", "CARM"),
    ("diputacionalicante.es", "Diputación de Alicante"), ("dip-alicante.es", "Diputación de Alicante"),
]


def enlaces_oficiales(url, maximo=8):
    """Abre la noticia y devuelve [(url_oficial, organismo, texto_del_enlace)] de publicaciones oficiales."""
    salida, vistos = [], set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        cuerpo = r.text
        m = re.search(r"<article.*?</article>", cuerpo, re.S | re.I)  # solo el texto de la noticia
        cuerpo = m.group(0) if m else cuerpo
        for href, texto in re.findall(r'<a[^>]+href=["\'](https?://[^"\'#]+)["\'][^>]*>(.*?)</a>', cuerpo, re.S | re.I):
            href = html.unescape(href)
            org = next((n for d, n in OFICIALES if d in href.lower()), None)
            if not org or href in vistos:
                continue
            vistos.add(href)
            texto = limpiar_html(texto)
            salida.append((href, org, texto))
            if len(salida) >= maximo:
                break
    except Exception:
        pass
    return salida


def leer_fuente(fuente, categorias, cfg, exclusion=None):
    # verify=False solo para fuentes oficiales con certificado mal configurado (p. ej. MAPA)
    resp = requests.get(fuente["url"], headers=HEADERS, timeout=30,
                        verify=not fuente.get("certificado_no_verificable"))
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        raise ValueError("el feed no contiene noticias (¿no es RSS?)")

    filtros = fuente.get("solo_si_contiene", [])
    limite = fuente.get("max_noticias", cfg.get("max_por_fuente", 15))
    noticias = []
    for e in feed.entries:
        if len(noticias) >= limite:  # el feed viene de más reciente a más antigua
            break
        url = e.get("link")
        titulo = limpiar_html(e.get("title"))
        if not url or not titulo:
            continue
        resumen = limpiar_html(e.get("summary", ""))
        etiquetas = " ".join(t.get("term", "") for t in e.get("tags", []) or [])
        texto_completo = f"{titulo} {resumen} {etiquetas}"

        # Filtro de fuente (p. ej. CARM: solo la consejería de Agricultura)
        if filtros and not any(f.lower() in texto_completo.lower() for f in filtros):
            continue
        # Quitamos el texto del filtro para que no influya en la categoría
        for f in filtros:
            resumen = re.sub(re.escape(f), "", resumen, flags=re.I).strip(" -|·")

        cats = categorizar(f"{titulo} {resumen}", categorias,
                           fuente.get("categoria_por_defecto", "General"),
                           fuente.get("categoria_siempre"))
        if es_excluida(f"{titulo} {resumen}", cats, exclusion):
            continue
        cats, local = aplicar_zona(f"{titulo} {resumen}", cats)
        # Fuentes de fuera de la zona (p. ej. Murcia): solo lo que afecte a la zona
        if fuente.get("solo_zona") and not local:
            continue
        # Fuentes que publican de todo: solo si contienen alguna de estas palabras
        alguna = fuente.get("contiene_alguna")
        if alguna and not any(w.lower() in texto_completo.lower() for w in alguna):
            continue
        # Medios generalistas: solo noticias que encajen en algún tema
        if fuente.get("descartar_general") and cats == ["General"]:
            continue

        if fuente.get("solo_enlace_oficial"):
            # La fuente solo sirve de aviso: se publican las disposiciones oficiales que enlaza
            # (título = texto oficial del enlace; enlace = DOGV, BOE, BDNS...)
            for href, org, texto in enlaces_oficiales(url):
                if len(texto) < 30:
                    continue
                t = recortar(texto, 220)
                c2 = categorizar(t, categorias, "General")
                if c2 == ["General"] or es_excluida(t, c2, exclusion):
                    continue
                c2, loc2 = aplicar_zona(t, c2)
                if fuente.get("solo_zona") and not loc2:
                    continue
                noticias.append({
                    "id": hashlib.sha1(href.encode()).hexdigest()[:16], "titulo": t, "extracto": "",
                    "fecha": fecha_iso(e), "fuente": org, "origen": fuente["nombre"], "url": href,
                    "imagen": None, "categorias": c2, "local": loc2,
                })
            continue
        # Filtros por fuente: temas permitidos y palabras a evitar
        if fuente.get("solo_categorias") and not set(cats) & set(fuente["solo_categorias"]):
            continue
        if fuente.get("excluir_palabras") and re.search(fuente["excluir_palabras"], texto_completo, re.I):
            continue
        nombre_fuente = fuente["nombre"]
        noticias.append({
            "id": hashlib.sha1(url.encode()).hexdigest()[:16],
            "titulo": titulo,
            "extracto": recortar(resumen, cfg["longitud_extracto"]),
            "fecha": fecha_iso(e),  # datetime o None; se resuelve en main()
            "fuente": nombre_fuente,
            "origen": fuente["nombre"],
            "url": url,
            "imagen": extraer_imagen(e),
            "categorias": cats,
            "local": local,
        })
    return noticias


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    categorias = compilar_categorias(cfg["categorias"])
    exclusion = compilar_exclusion(cfg)

    # Noticias anteriores (para acumular)
    anteriores = {}
    if SALIDA.exists():
        try:
            for n in json.loads(SALIDA.read_text(encoding="utf-8")).get("noticias", []):
                if n.get("fuente") == "Ejemplo":  # descarta los datos de prueba
                    continue
                # Aplica también el filtro de temas a las noticias ya guardadas
                if es_excluida(f"{n.get('titulo','')} {n.get('extracto','')}",
                               n.get("categorias", []), exclusion):
                    continue
                anteriores[n["id"]] = n
        except (json.JSONDecodeError, KeyError):
            print("Aviso: noticias.json anterior no válido; se regenera.")

    # Se retiran las noticias de fuentes que ya no están en config.json
    activas = {f["nombre"] for f in cfg["fuentes"]}
    anteriores = {k: n for k, n in anteriores.items() if n.get("origen", n.get("fuente")) in activas}
    # Recalcula los temas de las guardadas (por si se han cambiado las palabras clave)
    fijas = {f["nombre"]: f.get("categoria_siempre") for f in cfg["fuentes"]}
    anteriores = {k: n for k, n in anteriores.items()
                  if not es_excluida(f"{n.get('titulo','')} {n.get('extracto','')}", [], None)}
    for n in anteriores.values():
        texto = f"{n.get('titulo','')} {n.get('extracto','')}"
        n["categorias"], n["local"] = aplicar_zona(
            texto, categorizar(texto, categorias, "General", fijas.get(n.get("origen", n.get("fuente")))))
    por_nombre = {f["nombre"]: f for f in cfg["fuentes"]}

    def sigue_valida(n):
        f = por_nombre.get(n.get("origen", n.get("fuente")), {})
        txt = f"{n.get('titulo','')} {n.get('extracto','')}".lower()
        if f.get("contiene_alguna") and not any(w.lower() in txt for w in f["contiene_alguna"]):
            return False
        if f.get("solo_categorias") and not set(n["categorias"]) & set(f["solo_categorias"]):
            return False
        if f.get("excluir_palabras") and re.search(f["excluir_palabras"], txt, re.I):
            return False
        if f.get("solo_enlace_oficial") and len(n.get("titulo", "")) < 30:
            return False
        return True
    anteriores = {k: n for k, n in anteriores.items() if sigue_valida(n)}
    solo_zona = {f["nombre"] for f in cfg["fuentes"] if f.get("solo_zona")}
    anteriores = {k: n for k, n in anteriores.items()
                  if not (n.get("origen", n.get("fuente")) in solo_zona and not n.get("local"))}

    errores = 0
    for fuente in cfg["fuentes"]:
        try:
            nuevas = leer_fuente(fuente, categorias, cfg, exclusion)
            for i, n in enumerate(nuevas):
                if not n.get("imagen"):
                    previa = anteriores.get(n["id"], {})
                    n["imagen"] = previa.get("imagen") if "imagen_buscada" in previa else imagen_de_pagina(n["url"])
                    n["imagen_buscada"] = True
                if n["fecha"] is None:
                    # Sin fecha en el feed: se conserva la de la primera vez que se vio;
                    # si es nueva, "ahora" (restando minutos para mantener el orden del feed)
                    previa = anteriores.get(n["id"], {}).get("fecha")
                    n["fecha"] = previa or (AHORA - timedelta(minutes=i)).isoformat(timespec="seconds").replace("+00:00", "Z")
                else:
                    n["fecha"] = n["fecha"].isoformat().replace("+00:00", "Z")
                anteriores[n["id"]] = n
            print(f"OK    {fuente['nombre']}: {len(nuevas)} noticias")
        except Exception as ex:  # una fuente caída no detiene el resto
            errores += 1
            print(f"ERROR {fuente['nombre']}: {ex}")

    limite = AHORA - timedelta(days=cfg["dias_conservar"])
    lista = [n for n in anteriores.values()
             if datetime.fromisoformat(n["fecha"].replace("Z", "+00:00")) >= limite]
    lista.sort(key=lambda n: n["fecha"], reverse=True)
    lista = lista[: cfg["max_noticias"]]

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        "actualizado": AHORA.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "noticias": lista,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Total guardadas: {len(lista)} | Fuentes con error: {errores}")

    # Ayudas y plazos abiertos (BDNS + avisos manuales)
    try:
        import plazos
        plazos.actualizar()
    except Exception as ex:
        print(f"ERROR plazos: {ex}")

    # Solo falla si TODAS las fuentes fallan (para que GitHub avise)
    if errores == len(cfg["fuentes"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
