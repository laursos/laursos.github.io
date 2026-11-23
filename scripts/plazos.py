"""
Ayudas y plazos abiertos -> data/plazos.json

Fuentes:
1. Base de Datos Nacional de Subvenciones (BDNS / infosubvenciones.es), API pública JSON.
   Convocatorias de "Agricultura, Pesca y Alimentación" de la Comunitat Valenciana,
   la Región de Murcia y el Estado, más las de caza.
2. data/plazos-manuales.json: avisos que añade Laura a mano (con fecha de fin).

Una convocatoria se muestra mientras su plazo siga abierto:
- con fecha de fin conocida: hasta ese día (incluido);
- sin fecha de fin estructurada (plazo en texto, p. ej. "un mes desde la publicación"):
  se muestra con el texto del plazo durante DIAS_SIN_FECHA desde su publicación.
"""
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "plazos.json"
MANUALES = RAIZ / "data" / "plazos-manuales.json"
API = "https://www.infosubvenciones.es/bdnstrans/api"
FICHA = "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (aviso de ayudas agrarias; GitHub Actions)", "Accept": "application/json"}

FINALIDAD_AGRICULTURA = 12
REGIONES = {54: "Comunitat Valenciana", 72: "Región de Murcia"}
DIAS_BUSQUEDA = 150      # convocatorias publicadas en los últimos N días
DIAS_SIN_FECHA = 45      # cuánto se muestra una convocatoria con plazo solo en texto
MAX_DETALLES = 120       # consultas de detalle por ejecución (para no saturar la API)

# Debe aparecer al menos una de estas palabras (agricultura de la zona, maquinaria, caza...)
RELEVANTE = re.compile(
    r"agr[ií]col|agrari|agricult|explotaci|cultivo|c[ií]tric|hort[ií]col|hortaliza|frutal|"
    r"granad|olivar|olivo|almendr|regad|riego|regante|maquinaria|tractor|modernizaci|"
    r"joven(es)? agricultor|incorporaci[oó]n|relevo generacional|seguro agrario|ecol[oó]gic|"
    r"sanidad vegetal|plaga|fitosanit|fertiliz|caza|cineg|coto|fauna|da[ñn]os|dana|inundaci|siniestr|"
    r"cat[aá]strof|granizo|pedrisco|helada|temporal|incendi|lluvias",
    re.I)
# Se descartan (pesca, acuicultura, ganadería exclusiva, actos o premios)
DESCARTE = re.compile(
    r"pesca|pesquer|acuicultur|marisqu|buque|cofrad[ií]a|apicultur|apícol|ganado|porcino|bovino|"
    r"ovino|caprino|av[ií]cola|premio|certamen|feria|congreso|jornada|festival|"
    r"animales|ganader|reposici[oó]n de (los )?animales|comedor|escolar|alimentos? para|banco de alimentos|consumo de fruta",
    re.I)
BENEFICIARIO_UTIL = "PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA"

# Siniestros: búsquedas extra sin filtro de finalidad (se exige además un término agrario)
SINIESTROS = ("DANA", "inundaciones", "daños agrícolas", "granizo", "temporal", "catástrofe")
AGRARIO = re.compile(r"agr[ai]|explotaci|cultiv|regad|rural|campo|cosecha", re.I)
# Orden de prioridad en la portada (primero lo que más interesa a la clientela)
PRIORIDAD = ["Daños y siniestros", "Jóvenes agricultores", "Modernización", "Maquinaria", "Riego y agua"]

CATEGORIAS = [
    ("Daños y siniestros", r"\bdanas?\b|inundaci|siniestr|cat[aá]strof|granizo|pedrisco|helada|temporal|incendi|lluvias|riada|damnificad|da[ñn]os por"),
    ("Caza", r"caza|cineg|coto"),
    ("Maquinaria", r"maquinaria|tractor|pulverizad|atomizad|renove"),
    ("Jóvenes agricultores", r"joven(es)? agricultor|incorporaci[oó]n|relevo generacional"),
    ("Riego y agua", r"riego|regad|regante|h[ií]dric|agua"),
    ("Modernización", r"modernizaci|inversi|mejora de (las )?explotaci"),
    ("Seguros agrarios", r"seguro"),
    ("Agricultura ecológica", r"ecol[oó]gic"),
    ("Sanidad vegetal", r"sanidad vegetal|plaga|fitosanit"),
]


def _get(ruta, params=None):
    for intento in range(3):
        try:
            r = requests.get(f"{API}/{ruta}", params=params, headers=HEADERS, timeout=40)
            r.raise_for_status()
            return r.json()
        except Exception:
            if intento == 2:
                raise
            time.sleep(3)


def _buscar(**params):
    desde = (date.today() - timedelta(days=DIAS_BUSQUEDA)).strftime("%d/%m/%Y")
    base = {"page": 0, "pageSize": 100, "fechaDesde": desde,
            "order": "fechaRecepcion", "direccion": "desc"}
    base.update(params)
    resultados = []
    for pagina in range(5):
        base["page"] = pagina
        d = _get("convocatorias/busqueda", base)
        resultados += d.get("content", [])
        if d.get("last", True):
            break
    return resultados


def _fecha(txt):
    if not txt:
        return None
    try:
        return date.fromisoformat(str(txt)[:10])
    except ValueError:
        return None


def _categorias(texto):
    cats = [n for n, p in CATEGORIAS if re.search(p, texto, re.I)]
    return cats or ["Ayudas agrarias"]


def candidatas():
    """Convocatorias publicadas recientemente que pueden interesar."""
    vistas = {}
    for region, nombre in REGIONES.items():
        for c in _buscar(finalidad=FINALIDAD_AGRICULTURA, regiones=region):
            c["_ambito"] = nombre
            vistas.setdefault(c["numeroConvocatoria"], c)
        for palabra in ("caza", "cinegética"):
            for c in _buscar(descripcion=palabra, regiones=region):
                c["_ambito"] = nombre
                vistas.setdefault(c["numeroConvocatoria"], c)
        for palabra in SINIESTROS:
            for c in _buscar(descripcion=palabra, regiones=region):
                if AGRARIO.search(c.get("descripcion") or ""):
                    c["_ambito"] = nombre
                    vistas.setdefault(c["numeroConvocatoria"], c)
    for palabra in SINIESTROS:
        for c in _buscar(descripcion=palabra):
            if c.get("nivel1") == "ESTATAL" and AGRARIO.search(c.get("descripcion") or ""):
                c["_ambito"] = "Estatal"
                vistas.setdefault(c["numeroConvocatoria"], c)
    for c in _buscar(finalidad=FINALIDAD_AGRICULTURA):
        if c.get("nivel1") == "ESTATAL":
            c["_ambito"] = "Estatal"
            vistas.setdefault(c["numeroConvocatoria"], c)

    filtradas = []
    for c in vistas.values():
        txt = c.get("descripcion") or ""
        if c.get("nivel1") == "LOCAL":          # ayuntamientos: fuera
            continue
        if not RELEVANTE.search(txt) or DESCARTE.search(txt):
            continue
        filtradas.append(c)
    return filtradas


def estado(det, recepcion, hoy):
    """Devuelve (abierta, fecha_fin, texto_fin)."""
    fin = _fecha(det.get("fechaFinSolicitud"))
    ini = _fecha(det.get("fechaInicioSolicitud"))
    texto = (det.get("textFin") or "").strip()
    if fin:
        return (fin >= hoy and (ini is None or ini <= hoy + timedelta(days=30))), fin, texto
    if det.get("abierto"):
        return True, None, texto
    if texto and recepcion and (hoy - recepcion).days <= DIAS_SIN_FECHA:
        return True, None, texto
    return False, None, texto


def desde_bdns(anteriores, hoy):
    plazos, consultas = [], 0
    for c in candidatas():
        num = c["numeroConvocatoria"]
        previa = anteriores.get(f"bdns-{num}")
        # Si ya la teníamos con fecha de fin, no hace falta volver a consultar
        if previa and previa.get("fecha_fin"):
            if date.fromisoformat(previa["fecha_fin"]) >= hoy:
                plazos.append(previa)
            continue
        if consultas >= MAX_DETALLES:
            continue
        consultas += 1
        try:
            det = _get("convocatorias", {"numConv": num})
        except Exception as ex:
            print(f"  aviso: detalle {num} no disponible ({ex})")
            continue
        tipos = " ".join(t.get("descripcion", "") for t in det.get("tiposBeneficiarios") or [])
        if tipos and BENEFICIARIO_UTIL not in tipos.upper():
            continue
        abierta, fin, texto_fin = estado(det, _fecha(c.get("fechaRecepcion")), hoy)
        if not abierta:
            continue
        titulo = re.sub(r"\s+", " ", det.get("descripcion") or c.get("descripcion") or "").strip()
        organo = det.get("organo") or {}
        plazos.append({
            "id": f"bdns-{num}",
            "titulo": titulo,
            "organismo": (organo.get("nivel3") or "").strip().capitalize(),
            "ambito": c["_ambito"],
            "publicada": c.get("fechaRecepcion"),
            "fecha_inicio": (det.get("fechaInicioSolicitud") or "")[:10] or None,
            "fecha_fin": fin.isoformat() if fin else None,
            "texto_fin": None if fin else (texto_fin[:160] or None),
            "url": FICHA.format(num),
            "categorias": _categorias(titulo),
            "origen": "BDNS",
        })
        time.sleep(0.3)
    return plazos


def desde_manuales(hoy):
    if not MANUALES.exists():
        return []
    datos = json.loads(MANUALES.read_text(encoding="utf-8"))
    salida = []
    for i, p in enumerate(datos.get("avisos", [])):
        fin = _fecha(p.get("fecha_fin"))
        if not p.get("titulo") or not fin or fin < hoy:
            continue
        salida.append({
            "id": p.get("id") or f"manual-{i}",
            "titulo": p["titulo"],
            "organismo": p.get("organismo", ""),
            "ambito": p.get("ambito", ""),
            "publicada": p.get("publicada"),
            "fecha_inicio": p.get("fecha_inicio"),
            "fecha_fin": fin.isoformat(),
            "texto_fin": None,
            "url": p.get("url", ""),
            "categorias": p.get("categorias") or _categorias(p["titulo"]),
            "origen": "manual",
            "destacado": True,
        })
    return salida


def actualizar():
    hoy = datetime.now(timezone.utc).date()
    anteriores = {}
    if SALIDA.exists():
        try:
            anteriores = {p["id"]: p for p in json.loads(SALIDA.read_text(encoding="utf-8")).get("plazos", [])}
        except (json.JSONDecodeError, KeyError):
            pass

    manuales = desde_manuales(hoy)
    try:
        bdns = desde_bdns(anteriores, hoy)
        print(f"OK    BDNS (infosubvenciones): {len(bdns)} convocatorias abiertas")
    except Exception as ex:
        print(f"ERROR BDNS: {ex} -> se conservan las anteriores que sigan abiertas")
        bdns = [p for p in anteriores.values() if p.get("origen") == "BDNS"
                and (not p.get("fecha_fin") or date.fromisoformat(p["fecha_fin"]) >= hoy)]
    print(f"OK    Avisos manuales: {len(manuales)}")

    ids = {p["id"] for p in manuales}
    lista = manuales + [p for p in bdns if p["id"] not in ids]
    # Primero las destacadas (manuales), luego por fecha de cierre más próxima; sin fecha al final
    def prio(p):
        rangos = [PRIORIDAD.index(c) for c in p.get("categorias", []) if c in PRIORIDAD]
        return min(rangos) if rangos else len(PRIORIDAD)
    lista.sort(key=lambda p: (not p.get("destacado"), prio(p), p.get("fecha_fin") or "9999-12-31"))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        "actualizado": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "plazos": lista,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Plazos abiertos guardados: {len(lista)}")


if __name__ == "__main__":
    actualizar()
