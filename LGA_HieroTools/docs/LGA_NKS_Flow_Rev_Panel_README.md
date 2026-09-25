> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios.

# Flow Review Panel (`LGA_NKS_Flow_Panel`)

## Por qué existe

Flow Review reúne el recorrido de review sobre material ya sincronizado: traer el
estado actual desde Flow, inspeccionar un shot y sus comentarios, generar una
imagen para notas y empujar el siguiente estado de revisión. El nombre anterior,
`Flow`, era demasiado amplio y se confundía con las operaciones de creación,
consulta y acceso que viven en Flow | S3.

Solo cambia la identidad visible y la carpeta privada. El módulo
`LGA_NKS_Flow_Panel.py`, la clase `ColorChangeWidget` y el `objectName`
`com.lega.FPTPanel` se conservan para no invalidar imports ni layouts de docks
guardados por Nuke Studio.

## Carpeta privada

Los scripts auxiliares viven en `LGA_NKS_Flow_Rev_Panel_py/`. La ruta anterior
`LGA_NKS_Flow_Panel_py/` ya no existe y no debe usarse en código o documentación
nueva.

## Botones fijos

1. **Flow Pull** — click procesa todos los shots del timeline; Shift+click solo el seleccionado.
   Click en una fila de resultados navega al shot; si la fila está en el review del usuario y
   ese reviewer está habilitado (hoy Lega), abre además el Shot Info arriba de la ventana. Ver
   [LGA_NKS_Flow_Shot_Info.md](LGA_NKS_Flow_Shot_Info.md#apertura-automatica-al-llegar-a-un-shot-en-review).
2. **Shot Info** — muestra datos del shot y comentarios/versiones de la task; shortcut `Shift+T`.
3. **Review Pic** — captura el viewer con número de frame para acompañar notas de review.

## Botones de estado

Se construyen desde `LGA_NKS_Flow_Status_Config.PUSH_BUTTONS` y conservan el
orden real de `sg_status_list`. No se mantiene una segunda lista en el panel.

- **Studio y Client:** cada contexto expone únicamente sus estados válidos de
  review y entrega, en el orden definido por Flow. La lista vigente se obtiene
  desde la configuración compartida; no se duplican nombres personales aquí.

El cambio de contexto reconstruye la lista en caliente. Los colores visibles son
los colores de estado de Flow con un techo de luminancia para conservar el texto
legible; el color aplicado al clip sigue siendo el valor real sin esa corrección.

## Responsabilidades

- **Flow Pull** lee Flow/PipeSync y actualiza el timeline.
- **Shot Info** es observación: consulta y presenta historial, notas y versiones.
- **Review Pic** crea material auxiliar para comunicar feedback.
- **Botones de estado** realizan Flow Push; el click normal y Shift+click pueden
  seleccionar distintos alcances/versiones según el botón y el flujo de Push.

El panel no crea shots, no administra vendor groups y no lanza operaciones S3.
Esas responsabilidades pertenecen a Flow | S3 y Assignee.

## Referencias técnicas

- `LGA_HieroTools/LGA_NKS_Flow_Panel.py`
  - `ColorChangeWidget.__init__()` fija `Flow Review` como título visible sin cambiar el `objectName`.
  - `build_buttons(mode)` arma los tres botones fijos y agrega los estados del contexto.
  - `on_context_changed(mode)` reconstruye el panel al alternar Studio/Client.
  - `run_FPT_pull_with_deselect()` y `run_FPT_pull()` ejecutan los dos alcances de Pull.
  - `handle_color_button_click()` y `handle_color_button_shift_click()` enrutan Flow Push.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`
  - `PUSH_BUTTONS` y `get_push_buttons(mode)` son la fuente única de labels, códigos, colores y orden.
- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Pull.py`
  - `FPT_Hiero()` y `ShotGridManager` resuelven consulta, comparación y aplicación al timeline.
- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Push.py`
  - `push_from_selected_clips()` coordina selección, diálogo de nota y conector.
- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Shot_info.py`
  - `main()` resuelve el clip y abre `GUIWindow`; `ShotGridManager` consulta la información.
- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_ReviewPic.py`
  - `main()` captura el viewer y abre el flujo de edición/guardado de la imagen.
