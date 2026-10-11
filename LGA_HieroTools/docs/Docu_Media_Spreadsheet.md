# Columnas del Media Spreadsheet

El módulo compartido `LGA_NKS_Shared/LGA_NKS_MediaSpreadsheetColumns.py`
permite ordenar, dimensionar y ocultar o mostrar columnas del Media
Spreadsheet abierto en Hiero/Nuke Studio. Lo llaman `TL | Refresh` del ViewerTL
y el switch de secuencias del Projects Panel. Existe
porque el orden predeterminado deja los datos de estado y media separados,
y obliga a reorganizar la vista cada vez que se revisan clips.

## Uso desde el Script Editor

```python
from LGA_NKS_Shared import LGA_NKS_MediaSpreadsheetColumns as spreadsheet_columns
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

## Un solo tab al refrescar o cambiar de timeline

El problema era que ambos flujos reconstruían el timeline y su viewer pero
dejaban los spreadsheets anteriores. La sonda encontró cinco tabs al inicio;
un switch de ida y vuelta añadió uno en cada apertura.

Antes de reconstruir el timeline, ambos flujos llaman a `close_for_refresh()`:
cierra únicamente los tabs nativos de Spreadsheet y procesa sus
`DeferredDelete`. Sin procesar esa destrucción, el tab sigue registrado y
Foundry puede devolverlo de nuevo. No se cierran proyectos ni se borran clips.

Al final, después de las restauraciones y los cierres del timeline, llaman a
`refresh()`. Si Hiero no creó el spreadsheet nuevo, se abre con
`openInSpreadsheet(sequence)`; después `apply()` impone las reglas. Esto es
necesario en TL Refresh: en la prueba, abrir el timeline nuevo antes de
destruir el viejo no volvió a crear automáticamente el spreadsheet cerrado.
El resultado es una única pestaña de media para el timeline activo. El widget
nativo se reconstruye; no se retargetea el objeto anterior, porque la API
pública `SpreadsheetView` no ofrece `setSequence`.

El switch que encuentra su destino ya activo conserva la optimización de
reuso y aplica las columnas. Si detecta varios spreadsheets, reconstruye
también en ese caso para eliminar los tabs acumulados. El ajuste incluye tabs
ocultos detrás de otros y docks flotantes; no depende de `isVisible()`.

Las referencias al panel padre y a su tabla deben conservarse juntas durante
todo el ajuste: se midió que soltar el wrapper del padre invalida los wrappers
PySide de sus hijos, aun cuando el panel sigue existiendo en la UI. Buscar la
tabla y devolver solo el hijo causaba `Internal C++ object already deleted`
antes de leer el header. No usar `sourceModel()` ni el slot interno
`refreshTimeline()` para retargetear: no forman parte de la API pública de
Spreadsheet y no hacen falta para este flujo.

Se verificaron dos idas y vueltas entre secuencias (9 y 38 filas), el click en
la secuencia ya activa y dos TL Refresh consecutivos: siempre un tab,
columnas y anchos correctos, seis columnas ocultas y textos de Clip ordenados.
También se generaron dos tabs antes de pulsar la secuencia ya activa: el
switch los redujo a uno. Una prueba con el spreadsheet oculto corrigió Status
de 100 a 51 px sin hacerlo visible.
Las sondas quedan en `+Building_Blocks/explore_spreadsheet_tabs.py`; el módulo
runtime ya no vive en Building Blocks.

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

En dos ejecuciones completas de `apply()` v1.05 sobre la vista de 38 filas se
midieron 33,629 ms y 25,998 ms, incluidos la búsqueda de tabs ocultos/flotantes
y los logs, sin contar el viaje del
dev-link. La duración se registra en cada corrida. El costo del autoajuste
crece con la cantidad de filas; estos tiempos corresponden a la sesión
medida, no a proyectos de cualquier tamaño.

El ajuste manual se aplica a los Spreadsheet Views abiertos en ese momento.
Los dos flujos integrados lo repiten al final de cada refresh/switch. Si otra
acción nativa reconstruye el panel, se puede correr `apply()` otra vez: no hay
un hook global para intervenir en todas las acciones del host.
