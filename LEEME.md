# Agregador de noticias – instalación en GitHub

## Archivos
```
.github/workflows/noticias.yml   → tarea automática (cada 6 h)
scripts/actualizar_noticias.py   → lee los RSS y genera data/noticias.json
scripts/config.json              → FUENTES y PALABRAS CLAVE (lo único que editarás)
scripts/requirements.txt         → librerías de Python
```

## Puesta en marcha (una sola vez)
1. Crea un repositorio **público** en GitHub (GitHub Pages es gratis en repos públicos).
2. Sube **todo el contenido de la carpeta `REPOSITORIO-LISTO-PARA-SUBIR`** a la raíz del repositorio
   (ya incluye la web, `data/`, `.github`, `scripts` y `.nojekyll`). `index.html` debe quedar en la raíz,
   porque el script escribe en `data/noticias.json` y la web lo lee desde `./data/noticias.json`.
   - Ojo: la carpeta `.github` empieza por punto y puede estar oculta en tu ordenador.
3. **Settings → Actions → General → Workflow permissions** → marca *Read and write permissions* → Save.
4. **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main` / `(root)` → Save.
5. **Actions → Actualizar noticias → Run workflow** para lanzarlo la primera vez.
6. Revisa el registro: verás `OK` o `ERROR` por cada fuente.

La web queda en `https://TU-USUARIO.github.io/NOMBRE-REPO/`.

## Mantenimiento
- **Añadir/quitar una fuente:** edita `fuentes` en `scripts/config.json`.
- **Cambiar categorías:** edita `categorias`. `naranja*` = empieza por; `pac` = palabra exacta.
  Cada noticia recibe todas las categorías que coincidan; si ninguna, 'General'.
- Las noticias de ejemplo (fuente "Ejemplo") se borran solas en la primera ejecución.
- Si una fuente falla, se conservan sus noticias anteriores; el resto sigue funcionando.
- GitHub desactiva las tareas programadas tras 60 días sin actividad en el repo:
  si pasa, entra en Actions y pulsa *Enable workflow*.

## Fuentes configuradas
Alicante Plaza · Convega (Vega Baja) · MAPA (solo cítricos, hortalizas, frutales, siniestros, jóvenes, maquinaria, fitosanitarios y fertilización; sin agenda ministerial ni otras comunidades) · CARM - Agricultura (solo noticias de la zona) · Valencia Fruits · Agroinformación · Phytoma · Revista Mercados · Agroauténtico ·
Federación de Caza Comunidad Valenciana · Real Federación Española de Caza (solo noticias que citan la Comunitat Valenciana o Alicante).
Se descartan siempre las noticias de política de partidos.
Los medios generalistas llevan `descartar_general: true` (solo entran noticias de algún tema).
Las federaciones de caza llevan siempre la categoría 'Caza' y como máximo 8 noticias por actualización.

## Portada: 6 destacadas con cupos
Hasta 2 ayudas con plazo abierto + agricultura (prioridad cítricos y hortalizas, luego frutales,
PAC, maquinaria...) + 1 de caza. Se configura al principio de `js/carrusel-noticias.js` (`PRIO`).

## Ayudas y plazos abiertos (`data/plazos.json`)
- Automático: `scripts/plazos.py` consulta la Base de Datos Nacional de Subvenciones (BDNS).
  Zona: Generalitat Valenciana (sin las limitadas a Valencia/Castellón), provincia de Alicante
  (Diputación y ayuntamientos de Vega Baja, Elche y Crevillent), Murcia solo si cita la zona limítrofe
  y Estado (siniestros solo si citan la zona). Las convocatorias del DOGV y del BORM se registran en la BDNS,
  que envía el extracto al boletín, así que aparecen aquí el mismo día o antes.
  Cada convocatoria se muestra hasta su fecha de fin de solicitud.
- Manual: añade avisos en `data/plazos-manuales.json` (hay un ejemplo dentro).
  Se muestran primero y desaparecen solos al pasar su `fecha_fin`.
