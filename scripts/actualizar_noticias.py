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


def fecha_iso(entrada):
    for campo in ("published_parsed", "updated_parsed"):
        t = entrada.get(campo)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return AHORA


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


def leer_fuente(fuente, categorias, cfg):
    resp = requests.get(fuente["url"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        raise ValueError("el feed no contiene noticias (¿no es RSS?)")

    filtros = fuente.get("solo_si_contiene", [])
    noticias = []
    for e in feed.entries:
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

        noticias.append({
            "id": hashlib.sha1(url.encode()).hexdigest()[:16],
            "titulo": titulo,
            "extracto": recortar(resumen, cfg["longitud_extracto"]),
            "fecha": fecha_iso(e).isoformat().replace("+00:00", "Z"),
            "fuente": fuente["nombre"],
            "url": url,
            "imagen": extraer_imagen(e),
            "categorias": categorizar(f"{titulo} {resumen}", categorias,
                                      fuente.get("categoria_por_defecto", "General"),
                                      fuente.get("categoria_siempre")),
        })
    return noticias


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    categorias = compilar_categorias(cfg["categorias"])

    # Noticias anteriores (para acumular)
    anteriores = {}
    if SALIDA.exists():
        try:
            for n in json.loads(SALIDA.read_text(encoding="utf-8")).get("noticias", []):
                if n.get("fuente") != "Ejemplo":  # descarta los datos de prueba
                    anteriores[n["id"]] = n
        except (json.JSONDecodeError, KeyError):
            print("Aviso: noticias.json anterior no válido; se regenera.")

    errores = 0
    for fuente in cfg["fuentes"]:
        try:
            nuevas = leer_fuente(fuente, categorias, cfg)
            for n in nuevas:
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

    # Solo falla si TODAS las fuentes fallan (para que GitHub avise)
    if errores == len(cfg["fuentes"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
