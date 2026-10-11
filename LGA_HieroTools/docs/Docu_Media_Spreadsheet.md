# Columnas del Media Spreadsheet

`LGA_NKS_MediaSpreadsheetColumns.py` permite ordenar, dimensionar y ocultar o
mostrar columnas del Media Spreadsheet abierto en Hiero/Nuke Studio. Existe
porque el orden predeterminado deja `Clip` lejos de `Status`, aunque son los
dos datos que se necesitan juntos al revisar media.

## Uso desde el Script Editor

```python
import LGA_NKS_MediaSpreadsheetColumns as spreadsheet_columns
spreadsheet_columns.apply()
```

Ese ejemplo deja `Status` primera y `Clip` segunda, con anchos de 90 y 240 px.
Las demás columnas conservan su orden relativo y su visibilidad. Para elegir
otros anchos y ocultar columnas:

```python
spreadsheet_columns.apply(
    order=("Status", "Clip", "Shot Name"),
    widths={"Status": 90, "Clip": 320, "Shot Name": 180},
    hide=("Event", "Color"),
)
```

Para volver a mostrar esas dos columnas sin pedir anchos nuevos, usar
`spreadsheet_columns.apply(widths={}, show=("Event", "Color", "Status", "Clip"))`.
`show` y `hide` modifican solo los nombres indicados; los demás quedan como
estaban. Un nombre desconocido o un ancho inválido cancela la operación antes
de modificar la vista. No se toca la media ni la secuencia.

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
`restoreState` revierten la prueba. La herramienta busca la tabla por clase y
cabeceras para no alterar otras tablas de Nuke Studio.

El ajuste se aplica a los Spreadsheet Views visibles en ese momento. Si el
host reconstruye el panel, puede volver al orden predeterminado; en ese caso
se corre `apply()` otra vez. No se instaló un hook automático de restauración
porque todavía no se midió cuándo recrea el host esta vista.
