# Columnas del Media Spreadsheet

El prototipo local `+Building_Blocks/LGA_NKS_MediaSpreadsheetColumns.py`
permite ordenar, dimensionar y ocultar o mostrar columnas del Media
Spreadsheet abierto en Hiero/Nuke Studio. Permanece en Building Blocks hasta
decidir si se integra en un panel; no se distribuye en el pack. Existe
porque el orden predeterminado deja los datos de estado y media separados,
y obliga a reorganizar la vista cada vez que se revisan clips.

## Uso desde el Script Editor

```python
from pathlib import Path
import sys
from LGA_NKS_Shared import LGA_QtAdapter_HieroTools as qt_adapter
sys.path.insert(0, str(Path(qt_adapter.__file__).resolve().parents[1] / "+Building_Blocks"))
import LGA_NKS_MediaSpreadsheetColumns as spreadsheet_columns
spreadsheet_columns.apply()
```

Ese ejemplo deja estas cinco columnas visibles al principio:

| Posición | Columna | Ancho |
| --- | --- | --- |
| 1 | Status | 51 px, medidos después del ajuste manual |
| 2 | Clip Media | 99 px, medidos después del último ajuste manual |
| 3 | Clip | Automático por contenido; 330 px en la sesión medida |
| 4 | Color | 33 px, medidos después del ajuste manual |
| 5 | Shot Name | Automático por contenido; 299 px en la sesión medida |

`Clip` y `Shot Name` usan `resizeColumnToContents`, como el autoajuste del
header. Se miden todas las filas mediante la precisión temporal `-1` de Qt,
para no omitir nombres largos fuera de pantalla o más allá del muestreo
predeterminado. Después se restaura la precisión original del host.
Referencia: [QHeaderView.setResizeContentsPrecision](https://doc.qt.io/qt-6/qheaderview.html#setResizeContentsPrecision).
En la sesión de 38 filas, los textos más anchos midieron 318 px en `Clip` y
287 px en `Shot Name`; ambos quedaron con margen.
El script oculta `Event`, `Action`, `Num Versions`, `Link Status`, `Reel` y
`Version` cuando están presentes, y lleva el scroll horizontal al inicio.
Las filas se ordenan siempre por `Clip` ascendente mediante `sortByColumn`,
como al pulsar su cabecera. Se conserva el criterio nativo del host, que en
la sesión medida distingue mayúsculas y minúsculas. La prueba verificó el
orden de los textos de las 38 filas, además del indicador del header.
Referencia: [Sorting and Custom Columns de Foundry](https://learn.foundry.com/nuke/17.1/content/timeline_environment/conforming/about_spreadsheet.html).
Las demás columnas conservan
su orden relativo y su visibilidad. Para elegir un ancho manual de `Shot Name`
conservando el orden y el ocultamiento predeterminados:

```python
spreadsheet_columns.apply(
    widths={"Status": 51, "Clip": "auto", "Clip Media": 99,
            "Color": 33, "Shot Name": 180},
)
```

Para volver a mostrar las seis columnas ocultas, usar
`spreadsheet_columns.apply(widths={}, hide=(), show=("Event", "Action", "Num Versions", "Link Status", "Reel", "Version"))`.
`hide=None` usa las seis columnas predeterminadas solo si existen; `hide=()`
no oculta ninguna. Una lista `hide` explícita exige que sus nombres existan.
`show` y `hide` modifican solo los nombres indicados; los demás quedan como
estaban. Un nombre desconocido o un ancho inválido cancela la operación antes
de modificar la vista. Un ancho numérico fija píxeles; `"auto"` mide el
contenido como el doble click. No se toca la media ni la secuencia.

Los nombres disponibles en la versión de Nuke Studio medida son: `Event`,
`Status`, `Shot Name`, `Color`, `Reel`, `Track`, `Action`, `Version`,
`Num Versions`, `Link Status`, `Speed`, `Src In`, `Src Out`, `Src Duration`,
`Dst In`, `Dst Out`, `Dst Duration`, `Clip` y `Clip Media`.

## Por qué se usa el header Qt

La clase pública `hiero.ui.SpreadsheetView` no expone métodos de columnas.
En la sesión medida, el panel contiene un `SpreadsheetTreeView` con un
`QHeaderView` Qt, `sectionsMovable=True` y tamaño interactivo. La sonda
`+Building_Blocks/explore_media_spreadsheet.py` confirmó que `moveSection`,
`resizeSection` y `setColumnHidden` funcionan en vivo y que `saveState` /
`restoreState` revierten la prueba. Una prueba posterior confirmó el ancho
automático de `Clip` mediante `resizeColumnToContents`. El prototipo busca la
tabla por clase y cabeceras para no alterar otras tablas de Nuke Studio.

## Rapidez y repintado

Los nombres de columna se resuelven una vez en un diccionario por vista. Se
omiten movimientos, cambios de visibilidad y anchos fijos que ya estén bien.
Solo las dos columnas automáticas vuelven a medir contenido, mediante Qt,
sin recorrer textos desde Python en la herramienta.

Los cambios se agrupan con el repintado suspendido temporalmente. No se
bloquean señales del header: el host puede necesitarlas para actualizar su
estado interno. Un `finally` restaura la precisión y el estado de repintado
previos, también si falla una operación; el estado del header se revierte
ante un error.

En dos ejecuciones completas de `apply()` v1.04 sobre la vista de 38 filas se
midieron 5,341 ms y 9,628 ms, incluidos los logs, sin contar el viaje del
dev-link. La duración se registra en cada corrida. El costo del autoajuste
crece con la cantidad de filas; estos tiempos corresponden a la sesión
medida, no a proyectos de cualquier tamaño.

El ajuste se aplica a los Spreadsheet Views visibles en ese momento. Si el
host reconstruye el panel, puede volver al orden predeterminado; en ese caso
se corre `apply()` otra vez. No se instaló un hook automático de restauración
porque todavía no se midió cuándo recrea el host esta vista.
