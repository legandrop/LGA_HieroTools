# Columnas del Media Spreadsheet

El prototipo local `+Building_Blocks/LGA_NKS_MediaSpreadsheetColumns.py`
permite ordenar, dimensionar y ocultar o mostrar columnas del Media
Spreadsheet abierto en Hiero/Nuke Studio. Permanece en Building Blocks hasta
decidir si se integra en un panel; no se distribuye en el pack. Existe
porque el orden predeterminado deja `Clip` lejos de `Status`, aunque son los
dos datos que se necesitan juntos al revisar media.

## Uso desde el Script Editor

```python
from pathlib import Path
import sys
from LGA_NKS_Shared import LGA_QtAdapter_HieroTools as qt_adapter
sys.path.insert(0, str(Path(qt_adapter.__file__).resolve().parents[1] / "+Building_Blocks"))
import LGA_NKS_MediaSpreadsheetColumns as spreadsheet_columns
spreadsheet_columns.apply()
```

Ese ejemplo deja `Status`, `Clip` y `Clip Media` como las primeras tres columnas
visibles. `Status` mide 51 px y `Clip Media` 150 px: son los anchos medidos
después del ajuste manual en Nuke Studio. `Clip` se ajusta a su contenido con
`resizeColumnToContents`, la misma
operación que el doble click en el borde del header. En la sesión medida,
con 38 filas, pasó de 240 a 330 px y entran los nombres de las 38 filas.
La cadena más ancha de esas 38 filas midió 318 px; el header dejó margen.
El script oculta `Event`, `Action`, `Num Versions` y `Link Status` cuando están
presentes, y lleva el scroll horizontal al inicio. Las demás columnas conservan
su orden relativo y su visibilidad. Para elegir otros anchos y ocultar además
`Color` en la versión medida:

```python
spreadsheet_columns.apply(
    order=("Status", "Clip", "Clip Media", "Shot Name"),
    widths={"Status": 51, "Clip": "auto", "Clip Media": 150, "Shot Name": 180},
    hide=("Event", "Action", "Num Versions", "Link Status", "Color"),
)
```

Para volver a mostrar las cuatro columnas ocultas, usar
`spreadsheet_columns.apply(widths={}, hide=(), show=("Event", "Action", "Num Versions", "Link Status"))`.
`hide=None` usa las cuatro columnas predeterminadas solo si existen; `hide=()`
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

El ajuste se aplica a los Spreadsheet Views visibles en ese momento. Si el
host reconstruye el panel, puede volver al orden predeterminado; en ese caso
se corre `apply()` otra vez. No se instaló un hook automático de restauración
porque todavía no se midió cuándo recrea el host esta vista.
