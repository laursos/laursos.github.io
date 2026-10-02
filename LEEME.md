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
ASAJA Alicante · ASAJA Murcia · CARM - Agricultura · MAPA · Federación de Caza Región de Murcia ·
Federación de Caza Comunidad Valenciana (`federacioncazacv.com/feed/?post_type=prensa`) ·
Real Federación Española de Caza (`fecaza.com/feed/`).
Las tres federaciones llevan siempre la categoría 'Caza' (`categoria_siempre`).
