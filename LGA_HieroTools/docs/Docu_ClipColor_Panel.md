# ClipColor Panel

## Por que existe

ClipColor permite marcar visualmente clips seleccionados durante la edicion sin
esperar un Pull ni cambiar una Task en Flow. Es una accion local: cambia el
color del `BinItem` en Hiero y queda dentro de un unico Undo.

Los cuatro botones de review existen para que un clip que se etiqueta de forma
manual conserve el mismo lenguaje de color que Flow Review. No son botones de
Push: no escriben estados, notas ni datos remotos.

## Colores

Los primeros ocho botones son colores locales de trabajo (`v_00`, Plate,
EditRef, Reference, Error, Violet, Magenta y Cyan). Sus valores pertenecen al
panel porque no representan un estado de Flow.

Los cuatro botones de review resuelven su color desde
`LGA_NKS_Flow_Status_Config.get_status_color()`:

| Boton ClipColor | Codigo de estado | Origen del color |
|---|---|---|
| Corrections | `corr` | Catalogo compartido de Flow Review |
| Review Lega | `revleg` | Catalogo compartido de Flow Review |
| Review Dir | `rev_di` | Catalogo compartido de Flow Review |
| Approved | `apr` | Estado final de aprobacion del catalogo |

`Approved` conserva la etiqueta corta historica del panel, pero toma el color
del estado final `apr`. De ese modo no duplica un hex ni puede quedar distinto
del panel Flow Review cuando el catalogo se ajuste.

## Comportamiento y limites

- Trabaja sobre la seleccion del Timeline Editor de la secuencia activa.
- Omite Effects, media no presente, items sin `BinItem` y items sin version
  activa; un item problematico no corta el resto de la seleccion.
- Si no hay secuencia, proyecto de la secuencia o seleccion, no modifica nada.
- El Undo pertenece al proyecto de la secuencia activa, nunca al primer proyecto
  abierto; esto conserva Undo correcto cuando hay mas de un proyecto en NKS.
- Siempre cierra el Undo aunque falle un item durante el recorrido.
- Cada click deja su resultado en
  `LGA_HieroTools/logs/DebugPy_LGA_NKS_ClipColor_Panel.log`. La consola queda
  apagada salvo que `DEBUG` se active para diagnostico.

## UI

Los fondos de los botones son datos semanticos, por eso no usan
`Style.BTN_SECONDARY`: reemplazar el color borraria la informacion que el boton
representa. Si el color es muy claro, se oscurece solo el fondo del boton para
que el texto se lea; el `QColor` que llega al clip sigue siendo el original.

ClipColor usa la misma estructura compacta de Edit y Flow Review: `QScrollArea`
sin marco, grilla con 6 px horizontales y 3 px verticales, botones de 20 px,
radio 3 y texto regular. La caja comun, hover, pressed y foco salen de
`create_data_button_stylesheet()` en `LGA_NKS_StyleUtils`; asi el panel no
define QSS propio ni vuelve a verse como una ventana de formulario. El layout
mide el ancho real de los botones y solo se reconstruye cuando cambia el numero
de columnas.

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_ClipColor_Panel.py`
  - `ColorChangeWidget._build_buttons()` arma los colores locales y resuelve
    los cuatro estados de review.
  - `ColorChangeWidget.adjust_columns_on_resize()` calcula columnas desde el
    ancho medido.
  - `ColorChangeWidget.change_clip_color()` aplica el color local dentro de
    Undo y aísla errores por clip.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`
  - `get_status_color()` es la fuente unica de los colores de Flow Review.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
  - `create_data_button_stylesheet()` concentra el estilo de botones que
    expresan colores de datos.
