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
   Click en una fila de resultados navega al shot; con el checkbox **Shot Info** prendido abre
   además el Shot Info de esa fila arriba de la ventana, sin sacarle el foco. Ver
   [LGA_NKS_Flow_Shot_Info.md](LGA_NKS_Flow_Shot_Info.md#apertura-automatica-desde-viewertl-y-flow-pull).

   El header de la ventana de resultados trae **Only in review**, a la izquierda de
   **Keep on top**. Arranca prendido la primera vez y oculta las
   filas cuyo New Status no contiene "review" en el nombre visible (Review Lega,
   Review Hold, Pending Review...). Por qué: después de un Pull lo que se va a
   mirar son los shots en review; el resto de los cambios ya quedó aplicado en el
   timeline. Es solo vista, el Pull colorea y sube versiones igual. Se compara
   contra el nombre y no contra códigos para que un estado de review nuevo entre
   sin tocar una lista. Las filas se ocultan con `setRowHidden`, no se borran:
   la navegación y la actualización tras un Push van por índice de fila. Una fila
   que un Push saca de review sigue visible hasta volver a tocar el checkbox.

   A su derecha, **Only for me** (apagado la primera vez) deja solo las
   filas cuyo New Status es el review del usuario. Acá sí se compara el código de
   Flow de la fila (`revleg`, `rev_su`...) contra los del usuario, porque el dato
   es de quién es el review y no si la palabra aparece. Si el usuario no es un
   reviewer conocido, el checkbox queda deshabilitado.

   **Shot Info** (apagado por default) decide si el click en una fila abre el
   Shot Info. Antes lo decidía una lista de reviewers en el código y sólo para
   las filas del review propio; ahora cada uno lo elige.

   El texto de **Keep on top** se acortó (antes «Keep this window on top») para
   que el header entre con el botón y los cuatro checkboxes.

   **Los cuatro checkboxes del header persisten igual.** Only in review, Only
   for me, Shot Info y Keep on top se guardan al tocarlos en
   `%APPDATA%/LGA/HieroTools/FlowPull.ini`, sección `[FlowPullWindow]`, claves
   `only_in_review`, `only_for_me`, `shot_info` y `keep_on_top`; la ventana abre
   como quedó.
   Los defaults (`_FLOWPULL_DEFAULTS`) valen solo hasta el primer toque. Por qué:
   cada reviewer mira el Pull siempre igual, y volver a tildar lo mismo en cada
   Pull era el paso que sobraba. Dos cosas que no se deducen del código:
   - Se guarda **solo la clave que el usuario tocó**, y el valor se carga antes
     de conectar la señal, así abrir la ventana no escribe el INI.
   - Si el usuario no se resuelve como reviewer, Only for me se muestra apagado
     y deshabilitado **sin guardar ese apagado**: lo elegido sigue en el INI para
     cuando el perfil de PipeSync vuelva a resolverse.

   Test: `tests/test_flow_pull_window_settings.py`.

   **De dónde sale el usuario:** de `get_normal_login()` (perfil PipeSync normal),
   igual que los botones Prev/Next Rev del ViewerTL. No del contexto activo: en
   modo client ese perfil es el de la editora, y con ese login el Pull no
   reconocía los reviews de quien está en la máquina, ni para este filtro ni para
   las filas de review propio ni para el Shot Info automático.

   Si los filtros no dejan ninguna fila, un mensaje reemplaza a la tabla y dice
   qué destildar. El número que muestra son las filas que realmente van a
   aparecer: con los dos filtros prendidos y reviews de otros, cuenta solo esos.

   Dos trampas de Qt en esa ventana, las dos por tamaños mínimos: un
   `QStackedWidget` toma el mínimo de su página más grande aunque esté oculta
   (por eso el alto mínimo del mensaje se pone solo mientras se ve), y una tabla
   sin mínimo propio usa el `minimumSizeHint` del scroll area, más alto que una
   fila (por eso lleva `setMinimumHeight(1)`).

   **Download Clip**, a la izquierda de los checkboxes, baja de Wasabi la última
   versión del clip de la fila seleccionada. Por qué: el Pull sube los clips a la
   versión de Flow, que muchas veces todavía no está en disco y queda offline;
   antes había que buscar ese clip en el timeline, seleccionarlo e ir al panel
   Flow S3. Hace lo mismo que el click en **Download Clip** de ese panel
   (`--download-latest` / `--download-latest-file` con `--notify-completion`, y
   el watcher lo reconecta al terminar): reusa
   `LGA_NKS_FileManagerS3_DownloadClip.main(download_latest=True, clips=[clip])`,
   que acepta clips explícitos en vez de leer la selección del timeline. El clip
   se vuelve a buscar en la secuencia con `_find_clip_for_navigation`, como al
   navegar, porque la fila se armó antes de que el Pull lo cambiara de versión.
   Está deshabilitado mientras no haya una fila visible seleccionada (una fila
   que un filtro ocultó no cuenta).
2. **Shot Info** — muestra datos del shot y comentarios/versiones de la task; shortcut `Shift+T`.
3. **Review Pic** — captura el viewer con número de frame y la abre en FrameRev para anotarla; Save en FrameRev deja la anotación en ese mismo JPG, que Flow Push sube con la nota (ver `Docu_FrameRev.md`).

## Botones de estado

Se construyen desde `LGA_NKS_Flow_Status_Config.PUSH_BUTTONS` y conservan el
orden real de `sg_status_list`. No se mantiene una segunda lista en el panel.

- **Studio y Client:** cada contexto expone únicamente sus estados válidos de
  review y entrega, en el orden definido por Flow. La lista vigente se obtiene
  desde la configuración compartida; no se duplican nombres personales aquí.

**Rev Dir, Ctrl+Alt+Click** (solo studio, un clip): escribe la Submission Note del
slate de entrega. Abre el diálogo de notas con los selectores Submitting For y
Media Color, precargados con lo que ya tiene la Version exacta del clip, y guarda
los tres campos en esa Version en vez de crear una Note (los artistas no la
reciben). Si la task ya está en la cola de entrega ofrece guardar solo la nota.
Detalle: [Docu_Slate_MXF.md](Docu_Slate_MXF.md).

**Gestos de los botones de estado** (el tooltip de cada botón los nombra en una línea
corta cada uno; el detalle es este):

- **Click:** pasa la task a ese estado en Flow y pinta el clip (selección o clip
  del playhead). Si el estado pide nota (`is_note_capable()`), la nota va a la
  Version de Flow del clip. Rev Dir y Corrections además borran los tags del clip.
- **Shift+Click** (solo estados con nota, un clip): igual, pero abre un selector
  para elegir a qué Version de Flow va la nota. En los estados sin nota hace lo
  mismo que el Click y el tooltip no lo anuncia.
- **Ctrl+Alt+Click** (solo Rev Dir, solo studio): la Submission Note de arriba.
  El tooltip lo muestra solo en studio, que es donde funciona.

Los textos salen de `PUSH_TOOLTIPS` y `status_button_tooltip()` en
`LGA_NKS_Flow_Panel.py` (la línea de Ctrl+Alt+Click, de `TOOLTIPS` en
`LGA_NKS_Slate_Config.py`), aparte de los widgets para la futura versión bilingüe.
`tests/test_flow_panel_tooltips.py` verifica que cada botón de los dos contextos
anuncie sus gestos.

El cambio de contexto reconstruye la lista en caliente. Los colores visibles son
los colores de estado de Flow con un techo de luminancia para conservar el texto
legible; el color aplicado al clip sigue siendo el valor real sin esa corrección.

## Responsabilidades

- **Flow Pull** lee Flow/PipeSync y actualiza el timeline.
- **Shot Info** es observación: consulta y presenta historial, notas y versiones.
- **Review Pic** crea material auxiliar para comunicar feedback.
- **Botones de estado** realizan Flow Push; el Shift+Click elige la Version de
  Flow de la nota (ver "Gestos de los botones de estado").

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
  - `main()` captura el viewer, guarda el JPG en `ReviewPic_Cache` y lo abre en FrameRev.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_FrameRev.py`
  - `find_framerev()` ubica FrameRev por el registro de apps LGA; `edit_image()` lo lanza con `--edit-image`.
