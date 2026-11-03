# Tooltip propio de los packs (`LGA_UI_CustomTooltip_HieroTools`)

## Por qué existe

El tooltip nativo de Qt dentro de NKS sale con el tema del host (o con el
`QToolTip` de la hoja de la ventana, si tiene uno), pegado al cursor, sin flecha
y distinto en cada ventana. Las apps de escritorio LGA (PipeSync, FileManagerS3,
Mighty Tools) usan todas el mismo globo propio. Este módulo es ese globo en
Python, para que una ventana de los packs no se vea distinta de las apps.

**Regla dura (2026-11-03): ningún tooltip usa el nativo.** Ni `setToolTip(texto)`,
ni `QToolTip.showText`, ni un `QToolTip { }` en una hoja como reemplazo. El linter
de `lga-nuke-ui` lo marca como error (UI007). Al tocar una ventana, sus tooltips
nativos pasan a este en la misma pasada.

## Uso

```python
from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import (
    set_custom_tooltip, tooltip_label,
)

set_custom_tooltip(boton, "Primera oración.<br>Segunda oración.")
set_custom_tooltip(boton, tooltip_label("Click:") + " Una cosa<sbr/>"
                          + tooltip_label("Shift+Click:") + " Otra")
set_custom_tooltip(boton, "")  # lo saca
```

- `refresh_custom_tooltip(widget, texto)`: cambia el texto y, si el globo de ese
  widget está a la vista, lo repinta (contadores, progreso).
- `CustomTooltip.instance().debug_show(widget, texto)`: lo muestra ya, sin mouse
  ni delay, y devuelve el globo. Es para el harness de capturas (ver el fixture
  `h3_flow_pull.py`).

## Redacción

La fuente de verdad es la de las apps: `C:\Portable\LGA_Base_QT_C_Py\docs\Doc_CustomTooltip.md`.
En corto:

- Castellano. El texto va en un diccionario fuera del widget (los tooltips van a
  pasar a ser bilingües).
- No repetir lo que el control ya dice. Un control obvio no lleva tooltip.
- `Click:` / `Shift+Click:` solo cuando hay dos o más interacciones; con una
  sola acción, sin rótulo ni verbo.
- Una oración por renglón: `<br>` entre oraciones, también para partir una muy
  ancha. `<sbr/>` (4 px) y `<sBR/>` (10 px) separan bloques.
- Rótulos con `tooltip_label()`: `#E8E8E8` en negrita. Nunca blanco.

## Qué copia de `CustomTooltip.cpp` y qué no

Copia tal cual: medidas (flecha 16×11, radio 6, sombra de 4 capas), colores
(`#242424` fondo, `#3a3a3a` borde, `#B2B2B2` texto), medición con
`QTextDocument` y `setDocumentMargin(0)` (con `QFontMetrics` el alto sale corto),
borde trazado a mano sin la base de la flecha, volteo arriba/abajo cuando no
entra, delay de 600 ms que no se reinicia con Enter repetidos, y `Leave`
ignorado si el cursor sigue dentro (entró a un hijo).

Cambia, a propósito:

- **Sin event filter en toda la QApplication.** En C++ es gratis; en Python haría
  pasar por el intérprete cada evento de NKS. El ocultado robusto (Qt no siempre
  manda `Leave` al mover rápido) lo hace el watchdog de 120 ms, que corre solo
  mientras hay un globo visible.
- **Límites de pantalla, no de ventana activa.** Las ventanas de los packs son
  chicas y flotan sobre NKS sin estar activas.
- **No consume Enter/Leave.** El C++ los consume y por eso en las apps los
  checkbox necesitan reconstruir el hover a mano; acá el `:hover` de las hojas
  del pack sigue andando en el control que tiene el tooltip.
- **Se oculta al hacer click** en el control.
- **Sin master switches** de settings: los packs no tienen esa pantalla.

## Los otros packs

Hoy el módulo vive solo en HieroTools. ToolPack, ToolPack-B y Layout no lo
tienen: un pack que necesite un tooltip lo copia de acá (por copia, como el
módulo de estilo), cambiando solo los imports del adapter y del módulo de estilo
al nombre de ese pack.
