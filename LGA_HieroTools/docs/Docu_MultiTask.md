> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Soporte Multi-Task en las herramientas de Hiero / Nuke Studio

Este documento describe el **objetivo** del soporte multi-task del pipeline, la **convención de nombres** que lo hace posible, y el **estado actual** de cada herramienta respecto de las tasks vigentes: **comp**, **roto**, **cleanup** (studio) y **cg** (client, ver más abajo).

Complementa a [Docu_Logica_Nombres_Tracks.md](Docu_Logica_Nombres_Tracks.md), que define la convención de nombres. Este documento se enfoca en **qué scripts ya soportan multi-task y cuáles todavía no**.

## 1. Objetivo

Históricamente las herramientas trabajaban únicamente con la task **comp** (un único track EXR `_comp_` y un único track de review). El pipeline hoy necesita operar con varias tasks en paralelo, cada una con su propio track de EXR y su propio track de review.

El objetivo es que **toda herramienta que toque tracks de task**:

1. Sepa recorrer todos los tracks de task disponibles (no solo comp).
2. Detecte a qué task pertenece cada clip por su nombre de track y/o su filename.
3. Actualice o consulte la task correcta en Flow/SG.
4. Nunca hardcodee el string `_comp_` como si fuera sinónimo de "cualquier task".

## 2. Convención de nombres (resumen)

Regla única:

- **EXR** de una task → `_{task}_` (ej: `_comp_`, `_roto_`, `_cleanup_`)
- **Review MOV/MXF** de una task → `_{task}Rev_` (ej: `_compRev_`, `_rotoRev_`, `_cleanupRev_`)

El track Rev puede contener `.mov` o `.mxf` según el proyecto; el nombre del track es siempre `_{task}Rev_`.

Todo está centralizado en [LGA_NKS_Shared/LGA_NKS_GetClip.py](../LGA_NKS_Shared/LGA_NKS_GetClip.py):

```python
TRACK_comp_EXR    = "_comp_"
TRACK_roto_EXR    = "_roto_"
TRACK_cleanup_EXR = "_cleanup_"
TRACK_cg_EXR      = "_cg_"        # solo contexto client

TRACK_comp_REV    = "_compRev_"
TRACK_roto_REV    = "_rotoRev_"
TRACK_cleanup_REV = "_cleanupRev_"
TRACK_cg_REV      = "_cgRev_"     # solo contexto client

TASK_EXR_TRACKS = [TRACK_comp_EXR, TRACK_roto_EXR, TRACK_cleanup_EXR, TRACK_cg_EXR]
TASK_REV_TRACKS = [TRACK_comp_REV, TRACK_roto_REV, TRACK_cleanup_REV, TRACK_cg_REV]
```

Los scripts deben importar estas variables o las listas y no hardcodear los strings.

### El concepto de "stream" en CG

CG es distinta de comp/roto/cleanup en un punto clave: **el filename no lleva
el token de task**. En comp, un archivo se llama `..._comp_v003`; en CG, un
archivo se llama `PROJA_1013_0800_layout_v003` — `layout` es la
**disciplina** (a la que en este pipeline se llama **stream**: layout,
lighting, anim, fx, etc.), no un token de task reconocible por nombre. Por
eso puede haber varios tracks `_cg_` en el mismo timeline (uno por stream) y
los helpers de `GetClip.py` que buscan por nombre de track recorren todos los
que coincidan, en vez de asumir uno solo. El emparejamiento de versión más
alta por stream se resuelve en la DB de PipeSync vía la columna
`version_code`, no por nombre de track (ver sección 5.2, Flow Pull/Push).

## 3. Scope de tasks por contexto: `LGA_NKS_TaskScope.py`

La sección 2 define los **nombres** de los tracks de cada task. Una pregunta
distinta es **qué tasks existen en cada contexto** (studio vs. client) — el
*scope*. Esa pregunta la resuelve un módulo aparte:
[LGA_NKS_Shared/LGA_NKS_TaskScope.py](../LGA_NKS_Shared/LGA_NKS_TaskScope.py).

### División de responsabilidades con GetClip

- **`LGA_NKS_GetClip.py`** define los **nombres** de track (`TRACK_comp_EXR`,
  `TRACK_cg_EXR`, `TASK_EXR_TRACKS`, ...) y vive del lado de Hiero: importa
  `hiero` y solo carga dentro de NKS.
- **`LGA_NKS_TaskScope.py`** define **qué tasks existen en cada contexto**
  y deliberadamente NO importa `hiero`, para que lo puedan usar también los
  tests y los módulos compartidos que corren fuera de NKS — por ejemplo
  `LGA_NKS_Flow_NamingUtils.py`, que resuelve la familia CG en contexto
  client (ver [Docu_TaskName_Aliases.md](Docu_TaskName_Aliases.md)) y
  necesita funcionar sin la cadena de imports de Hiero.
- Antes de existir TaskScope, el scope por contexto vivía como constante
  local de `LGA_NKS_CreateV000` (`ALL_TASKS` / `CLIENT_TASKS`, resueltas por
  una función `_resolve_active_tasks()` que ya no existe) y ninguna otra
  herramienta podía consultarlo: cada una mantenía su propia lista de tasks
  por contexto en paralelo, con riesgo de que derivaran entre sí.

### Qué expone

- `TRACK_TASKS`: tabla `(task, carpeta, contextos)` — la fuente única de qué
  tasks tienen track propio y en qué contexto(s) existen.
- `CG_TASK_NAME`: nombre de la task CG (`"cg"`).
- `resolve_mode(mode=None)`: normaliza o lee el contexto activo (cae a
  `studio` ante cualquier falla en la cadena de imports de contexto).
- `all_track_task_names()`: todas las tasks con track, sin filtrar por
  contexto.
- `active_track_tasks(mode=None)`: tasks con track activas en el contexto
  (`("comp", "roto", "cleanup")` en studio; `("comp", "cg")` en client), en
  el orden del stack de tracks.
- `is_track_task_active(task_name, mode=None)`: si esa task existe en el
  contexto.
- `task_folder_name(task_name, default=...)`: carpeta en disco de la task
  (`"cg" -> "CG"`).
- `exr_track_for_task()` / `rev_track_for_task()` / `task_for_track()`:
  derivan el nombre de track EXR/Rev de una task, o la task de un track.

### Cómo se verifica que no derive de GetClip

[LGA_NKS_Shared/tests/test_task_scope.py](../LGA_NKS_Shared/tests/test_task_scope.py)
lee `LGA_NKS_GetClip.py` como TEXTO (no lo puede importar: ese módulo importa
`hiero`) y compara, vía regex, las constantes `TRACK_*_EXR` / `TRACK_*_REV` y
las listas `TASK_EXR_TRACKS` / `TASK_REV_TRACKS` contra `TaskScope.TRACK_TASKS`.
También verifica que `get_available_tasks()` de `LGA_NKS_Flow_Task_Config`
filtre por el mismo scope, y que la familia CG de `normalize_task_name()`
(ver [Docu_TaskName_Aliases.md](Docu_TaskName_Aliases.md)) se aplique sin
`hiero` disponible. Corre sin Hiero, sin PipeSync y sin red.

### Consumidores

| Módulo | Qué consulta de TaskScope |
|---|---|
| `LGA_NKS_Flow_Task_Config.get_available_tasks()` | `BOTH` / `STUDIO_ONLY` / `CLIENT_ONLY`, `resolve_mode()` |
| `LGA_NKS_Flow_NamingUtils._apply_cg_family()` | `all_track_task_names()`, `CG_TASK_NAME` |
| `LGA_NKS_CreateV000._active_tasks()` / `_task_folder_map()` | `active_track_tasks()`, `all_track_task_names()`, `task_folder_name()` |
| `LGA_NKS_Review_Panel._segunda_task()` | `active_track_tasks()` |
| `LGA_NKS_Clip_DisableCG.py` | `exr_track_for_task("cg")` |
| `LGA_NKS_Flow_ShowInFlow._nombres_preferidos()` | `is_track_task_active("cg")` |
| `LGA_NKS_Flow_CheckTimelineShots._tracks_de_tasks_activas()` | `exr_track_for_task()`, `is_track_task_active()` |
| `LGA_import_shots._task_folders_for_context()` | `is_track_task_active()`, `task_folder_name()` |
| `LGA_import_shots_preview.classify_track_type()` | `exr_track_for_task(CG_TASK_NAME)` |

## 4. Tasks y su estado en Flow / SG

Las tasks de studio (**comp**, **roto**, **cleanup**) tienen en Flow/SG **sus propios status, versiones y assignee**. Es decir: un shot puede tener simultáneamente una task `comp` con status "Review Lega" y una task `roto` con status "In Progress", cada una con su propia historia de versiones.

**CG (client) es distinta:** una sola task `cg` en Flow agrupa las versiones de **todos los streams** (layout, lighting, anim, fx, ...) de un shot. Como el número de versión se repite entre streams (cada stream tiene su propio `v001`, `v002`, ...), la task sola no alcanza para identificar una versión: hace falta además el `version_code` (el nombre completo, ej. `PROJA_1013_0800_layout_v003`) guardado en la DB de PipeSync. Ver sección 5.2 para cómo Pull/Push resuelven esto por stream.

## 5. Estado actual por herramienta

Leyenda:

- ✅ Soporta la task completamente
- 🟡 Soporta de forma parcial (ver nota)
- ❌ No soporta (hardcodeado a comp, o no existe)
- — No aplica

### 5.1. Módulo central — `LGA_NKS_Shared/LGA_NKS_GetClip.py`

| Dominio | comp | roto | cleanup | cg (client) |
|---|---|---|---|---|
| Variables `TRACK_*_EXR` | ✅ | ✅ | ✅ | ✅ |
| Variables `TRACK_*_REV` | ✅ | ✅ | ✅ | ✅ |
| Lista `TASK_EXR_TRACKS` | ✅ | ✅ | ✅ | ✅ |
| Lista `TASK_REV_TRACKS` | ✅ | ✅ | ✅ | ✅ |
| `find_clip_at_playhead_in_track()` / `get_selected_clips_in_track()` | ✅ | ✅ | ✅ | ✅ (múltiples tracks `_cg_`, uno por stream) |

Nada pendiente.

### 5.2. Flow Panel

| Script | comp EXR | roto EXR | cleanup EXR | cg EXR (client) | comp Rev | roto Rev | cleanup Rev |
|---|---|---|---|---|---|---|---|
| [LGA_NKS_Flow_Pull.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py) | ✅ | ✅ | ✅ | ✅ | — | — | — |
| [LGA_NKS_Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py) | ✅ | ✅ | 🟡 | ✅ | — | — | — |
| [LGA_NKS_Flow_Shot_info.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py) | ✅ | ✅ | ✅ | ❓ | — | — | — |
| [LGA_NKS_ReviewPic.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py) | ✅ | ❓ | ❓ | ❓ | — | — | — |

**Flow Pull — notas:**
- Multi-task completo (v3.41). El filtro de filename acepta cualquier task de `TASK_EXR_TRACKS` (`_comp_`, `_roto_`, `_cleanup_`, `_cg_`); antes hardcodeaba `_comp_` y descartaba roto/cleanup.
- Comparación de versión SG vs NKS por task: `find_highest_version_for_task(shot, task, task_name)` ([Flow_Pull.py:312](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py:312)) recorre solo `task["versions"]` de la task detectada y devuelve el string como `_{task}_v{n}`. Antes mezclaba todas las tasks del shot y rotulaba como `_comp_`, lo que producía falsos mismatches (ej: comp v9 en NKS comparado contra roto v33 en SG).
- Tabla de cambios incluye columna `Task` (la detectada del filename), para distinguir a qué task corresponden la versión y el status mostrados.
- v3.58: los clips que viven en un track `_cg_` se procesan aunque el filename no traiga un token de task conocido (ahi el filename lleva el stream y no "cg"); los demas tracks conservan el filtro historico por filename. Para CG, `find_highest_version_for_task()` recibe además `stream_token` (helper `_stream_token_from_code()`) y compara la versión más alta **por stream**, usando la columna `version_code` de la DB de PipeSync — no alcanza con el número de versión porque cada stream tiene su propia numeración. Al terminar el pull, si la DB tiene streams de CG sin clip en ningún track `_cg_` del timeline, se muestra un aviso listando shot/stream/código.

**Flow Push — notas:**
- v3.97 implementó multi-task correctamente: itera `TASK_EXR_TRACKS`, detecta la task del filename y, cuando hay clips de varias tasks seleccionadas, muestra un diálogo para elegir a cuál aplicar el status (`_show_task_selection_dialog`, [Flow_Push.py:2325](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py:2325)).
- Para cleanup: apenas se agregue a `TASK_EXR_TRACKS` (ya hecho), Push lo detecta automáticamente. Pendiente validar con timeline real.
- v4.07: mismo bypass de filtro que Pull, limitado al track `_cg_` (procesa clips de CG aunque el filename no tenga token de task; los demas tracks conservan el filtro historico). `find_version_by_number`, `find_latest_version` y `update_version_status` del DBManager aceptan `stream_token` y discriminan por `version_code` entre versiones que comparten número dentro de la task CG.
- [Flow_Push.py:839](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py:839) tiene `get_comp_assignee()` que busca siempre la task "comp" del shot para decidir el assignee. → **Pendiente revisar:** definir si el assignee del shot debe venir siempre de comp o depender de la task activa.

**Flow Shot_info — notas:**
- v1.86 resolvió el hardcode a `comp`. Antes llamaba siempre a `find_task(shot, "comp")`.
- Ahora resuelve la task vía el helper compartido [LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py): si el playhead atraviesa clips de varias tasks de `TASK_EXR_TRACKS`, abre un popover con un botón por task.

**Flow ReviewPic:** no auditado en detalle. Posibles hardcodes a revisar; pendiente integrar el mismo helper.

### 5.3. Review Panel

| Script | comp | roto (studio) | cleanup (studio) | cg (client) | Notas |
|---|---|---|---|---|---|
| [LGA_NKS_Clip_DisableEXR.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py) | ✅ | ✅ | ✅ | ✅ | Parametrizado con `track_name=TRACK_*_EXR`; el wrapper de CG le pasa `exr_track_for_task("cg")` |
| [LGA_NKS_Clip_DisableRoto.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableRoto.py) | — | ✅ | — | — | Wrapper de DisableEXR con `TRACK_roto_EXR` |
| [LGA_NKS_Clip_DisableCG.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableCG.py) | — | — | — | ✅ | Wrapper de DisableEXR con `exr_track_for_task("cg")` y `enable_rev_fallback=False`; existe solo para el contexto client |
| **Wrapper cleanup** | — | — | ❌ | — | **Pendiente crear** `LGA_NKS_Clip_DisableCleanup.py` |
| [LGA_NKS_EXRTrack_Difference.py](../LGA_NKS_Review_Panel_py/LGA_NKS_EXRTrack_Difference.py) | ✅ | ❌ | ❌ | ❌ | Hardcodeado a `TRACK_comp_EXR` |
| [LGA_NKS_Compare_Versions.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions.py) | ✅ | ❌ | ❌ | ❌ | Hardcodeado a `TRACK_comp_EXR` |
| [LGA_NKS_Compare_Versions_OFF.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions_OFF.py) | ✅ | ❌ | ❌ | ❌ | Hardcodeado a `TRACK_comp_EXR` |
| [LGA_NKS_ON_Clips_OFF_v00-Clips.py](../LGA_NKS_Review_Panel_py/LGA_NKS_ON_Clips_OFF_v00-Clips.py) | ✅ | ✅ | ✅ | ✅ | v1.30: identifica por track (`TASK_EXR_TRACKS`/`TASK_REV_TRACKS`, que ya incluyen `_cg_`/`_cgRev_`). EXR: v00/v000 OFF, resto ON. Rev: siempre OFF. Tracks no-task: ON |

**El segundo botón ON/OFF (`Ctrl+Shift+D`) sigue el contexto.** En
[LGA_NKS_Review_Panel.py](../LGA_NKS_Review_Panel.py), `_segunda_task()`
resuelve la segunda task de `active_track_tasks()` (TaskScope) y
`execute_DisableSecondTask()` elige el wrapper correspondiente de
`_SEGUNDA_TASK_SCRIPTS` (`"roto"` en studio, `"cg"` en client). Antes el
botón era literal `"ON OFF _roto_"` y en client no servía para nada porque
roto no existe ahí.

**Pendiente en Review Panel:**
- Agregar botón y wrapper `ON OFF _cleanup_` análogo a los de comp y roto
  (`_SEGUNDA_TASK_SCRIPTS` no incluye `cleanup` a propósito: mapearlo
  apuntaría a un wrapper inexistente y el botón fallaría en silencio).
- Decidir si las herramientas de diferencia/comparación deben operar por task o solo sobre comp.
- Reemplazar regex hardcodeados por patrón que use `TASK_EXR_TRACKS`.

### 5.4. Edit Panel

| Script | comp EXR | roto EXR | cleanup EXR | comp Rev | roto Rev | cleanup Rev |
|---|---|---|---|---|---|---|
| [LGA_NKS_MatchVerToEXR.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py) | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| [LGA_NKS_CompareVerToEditref.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py) | — | — | — | ✅ | ❌ | ❌ |
| [LGA_NKS_CompareEXR_to_aPlate.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py) | ✅ | ❌ | ❌ | — | — | — |

**Pendiente en Edit Panel:**
- MatchVerToEXR: hoy matchea la versión de `_comp_` con `_compRev_`. Cuando roto/cleanup tengan review, extender para operar por task iterando las listas.
- CompareVerToEditref: hoy compara rangos solo del track `_compRev_` contra EditRef. Evaluar si debe operar también sobre `_rotoRev_` y `_cleanupRev_`.

**Create v000 e Import Shots — soporte de tasks por contexto (scope, no review de track):**

| Script | comp | roto (studio) | cleanup (studio) | cg (client) | Notas |
|---|---|---|---|---|---|
| [LGA_NKS_CreateV000.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py) | ✅ | ✅ | ✅ | ✅ | Tasks activas y carpetas resueltas desde `LGA_NKS_TaskScope` **en cada llamada** (`_active_tasks()`, `_task_folder_map()`); antes una constante de módulo fijada al importar quedaba desactualizada tras un switch de contexto en caliente |
| [LGA_import_shots.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots.py) | ✅ | ✅ | ✅ | ✅ | CG es task de primera clase en el import: color (`_CLR_CG`), orden de track (`_cg_` bajo `_comp_`), carpeta de publish (`_task_folders_for_context()`) y "última versión" calculada **por stream** (`_stream_token()`), porque una sola carpeta CG agrupa disciplinas con numeración independiente |
| [LGA_import_shots_preview.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py) | ✅ | ✅ | ✅ | ✅ | `classify_track_type()` reconoce `_cg_` vía `exr_track_for_task(CG_TASK_NAME)`; devuelve el tipo `"cg"` |

### 5.5. Coordination Panel

| Script | comp | roto (studio) | cleanup (studio) | cg (client) | Notas |
|---|---|---|---|---|---|
| [LGA_NKS_Flow_CreateShot.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py) | ✅ | ✅ | ✅ | ✅ | El diálogo genera una sección por task con `get_available_tasks()` (filtra `AVAILABLE_TASKS` por contexto); antes iteraba `AVAILABLE_TASKS` completo y ofrecía Roto/Cleanup/DMP/3D también en client, sitio de Flow donde esas tasks no existen |
| [LGA_NKS_Flow_CreateShot_Folders.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py) | ✅ | ✅ | ✅ | ✅ | Suma `TASK_FOLDER_STRUCTURE["CG"]`: una sola carpeta (`cg/0_assets` … `cg/4_publish`) para todas las disciplinas, sin subdividir por stream |
| [LGA_NKS_Flow_ShowInFlow.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py) | ✅ | — | — | ✅ (fallback) | `_task_preferida()` / `_nombres_preferidos()`: en studio abre solo la task Comp (`("Comp",)`, igual que antes); en client intenta Comp y, si el shot no la tiene, cae a CG. Antes el literal `"Comp"` estaba repetido en cuatro lugares y un shot solo-CG abría la URL del shot pelado |
| [LGA_NKS_Flow_CheckTimelineShots.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py) | ✅ | — | — | ✅ | `_tracks_de_tasks_activas()`: en studio revisa solo `_comp_` (igual que antes); en client suma `_cg_` y `_collect_shots_from_track()` recorre TODOS los tracks que coincidan con cada nombre — antes tomaba solo el primer track `_comp_` |

**Assignee Panel, ViewerTL:** siguen sin auditar para este documento. El assignee por task ya funciona en parte porque Flow/SG devuelve assignees por task, pero hay lugares (ej. el `get_comp_assignee()` del Push) donde la task está hardcodeada a comp. Revisar caso por caso.

### 5.6. Selección de task en herramientas single-task

Algunas herramientas (Shot_info, en el futuro Push y ReviewPic) actúan sobre **una sola task por ejecución**. Para esas herramientas, el helper compartido [LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py) resuelve qué task usar:

- Si el playhead no toca ningún track de task → devuelve `None` (la herramienta cae al fallback histórico, normalmente comp).
- Si el playhead toca **una sola** task → la devuelve sin mostrar UI.
- Si el playhead toca **varias** tasks → abre un popover modal "Select task" con un botón por task disponible. Cada botón muestra a la izquierda un cuadradito con un número de atajo (1, 2, 3…); la task se elige con el mouse o presionando esa tecla.

API:

- `get_tasks_at_playhead(seq) -> list[str]`
- `track_for_task(task_name) -> str | None`
- `prompt_task_selection(task_names, title) -> str | None`
- `resolve_task_at_playhead(seq, title) -> str | None`

El mapa interno `_TASK_TO_TRACK` (y su inverso `_TRACK_TO_TASK`) ya no se
hardcodea: se deriva de `TASK_EXR_TRACKS` (`{t.strip("_").lower(): t for t in
TASK_EXR_TRACKS}`). Sumar una task nueva en `GetClip.py` la registra sola acá
— así entró `cg` sin tocar este módulo. El chequeo de mismatch
(`get_valid_tasks_at_playhead_with_check`) normaliza la task del filename con
`normalize_task_name()`, así un clip de stream (layout, lighting, ...) en el
track `_cg_` no se reporta como mismatch.

Estado de adopción:

| Herramienta | Usa el helper |
|---|---|
| [Flow_Shot_info.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py) | ✅ |
| [Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py) | ❌ (tiene su propio `_show_task_selection_dialog`; pendiente migrar) |
| [ReviewPic.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py) | ❌ (pendiente) |

## 6. Advertencia de Task / Track Mismatch

Cuando la **task detectada en el filename** de un clip no coincide con el **nombre del track** donde el clip está ubicado, las herramientas muestran una ventana informativa al finalizar la operación.

Ejemplo: un clip llamado `SHOW_SEQ_SHOT_comp_v003.exr` ubicado en el track `_roto_`.

### Política

- **Solo informa**, no bloquea ni modifica el procesamiento.
- El procesamiento real sigue usando la task **del filename** (comportamiento histórico): en el ejemplo anterior, se actualiza la task `comp` en SG.
- El usuario decide si renombra el clip, lo mueve de track, o ignora el aviso.

### Dónde aplica

| Herramienta | Cuándo aparece la ventana |
|---|---|
| Flow Pull | Al finalizar, después de procesar todos los clips |
| Flow Push | Al iniciar, antes del diálogo de selección de task |

### Formato

Una fila por clip con tres columnas: **Clip**, **Task (filename)**, **Track**.

### Implementación

- Helper compartido: [LGA_NKS_Shared/LGA_NKS_TaskMismatchDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskMismatchDialog.py)
  - `collect_task_mismatches(...)`: arma la lista de mismatches.
  - `show_task_mismatch_warning(...)`: muestra la ventana modal.
- Usado por [Flow_Pull.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py) y [Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py).

## 7. Roadmap resumido

Lista de pendientes concretos, en orden sugerido:

1. **Review Panel** — crear wrapper y botón para `ON OFF _cleanup_` (el de `_cg_` ya existe: `LGA_NKS_Clip_DisableCG.py`).
2. **Flow Push** — migrar `_show_task_selection_dialog` interno al helper compartido `LGA_NKS_TaskSelectionDialog`.
3. **Flow Push** — decidir política del assignee del shot (`get_comp_assignee`) y ajustar si corresponde.
4. **Flow ReviewPic** — auditar hardcodes a comp e integrar `LGA_NKS_TaskSelectionDialog`.
5. **Edit Panel** — extender MatchVerToEXR y CompareVerToEditref a operar por task iterando `TASK_EXR_TRACKS` / `TASK_REV_TRACKS`.
6. **Review Panel** — evaluar si EXRTrack_Difference y Compare_Versions deben trabajar por task o seguir siendo comp-only.
7. **Scripts no auditados** — pasar el filtro de hardcodes por Assignee, ViewerTL. (Coordination Panel — Create Shot, Show in Flow, Check Shots — ya se auditó para el scope de CG, ver sección 5.5.)

## 8. Tests manuales sugeridos

Con un timeline que tenga un shot con clips en `_comp_`, `_roto_`, `_cleanup_`, `_compRev_`, `_rotoRev_`, `_cleanupRev_`:

- Flow Pull (Shift+Click = solo shot seleccionado):
  - El clip `_comp_` debe recibir color del status de la task comp.
  - El clip `_roto_` debe recibir color del status de la task roto.
  - El clip `_cleanup_` debe recibir color del status de la task cleanup.
  - La tabla de cambios debe mostrar la columna `Task` con `comp`/`roto`/`cleanup` según el filename del clip.
- Flow Push con un status:
  - Seleccionar clips de varias tasks → debe mostrar el diálogo preguntando a cuál aplicar.
  - Aplicar a una sola task → el status debe escribirse únicamente en esa task en SG.
- Review Panel:
  - `ON OFF _comp_` (Shift+D) alterna el clip de `_comp_`.
  - `ON OFF _roto_` (Ctrl+Shift+D) alterna el clip de `_roto_`.
  - `ON OFF _cleanup_` todavía no existe (pendiente).

### Contexto client — task CG

Con el contexto activo en `client` y un timeline con un shot con clip en
`_comp_` y uno o más tracks `_cg_` (uno por stream — por ejemplo un `_cg_`
con `PROJA_1013_0800_layout_v003` y otro `_cg_` con
`PROJA_1013_0800_lighting_v002`):

- **Create Shot:** el diálogo debe ofrecer únicamente las tasks `Comp` y `CG`, sin Roto/Cleanup/DMP/3D.
- **Create v000:** los botones de task deben ser `comp` y `cg` únicamente; crear una v000 de `cg` debe publicar en la carpeta `CG`.
- **Review Panel:** el segundo botón ON/OFF (`Ctrl+Shift+D`) debe leer "ON OFF _cg_" y alternar el clip de un track `_cg_` bajo el playhead, no de `_roto_`.
- **Show in Flow:** un shot sin task Comp pero con task CG debe abrir la URL de la task CG, no la del shot pelado.
- **Check Shots:** debe reportar como existentes los shots que solo tienen clip en `_cg_`; si hay varios tracks `_cg_`, tiene que revisarlos todos, no solo el primero.
- **Import Shots:** una carpeta de publish `CG` con streams `layout` y `lighting` numerados de forma independiente (`..._layout_v001`, `..._layout_v002`, `..._lighting_v001`) tiene que marcar `is_latest=True` en la versión más alta de CADA stream, no solo en el máximo global de la carpeta.
- **Cambiar el contexto a `studio`** y repetir Create Shot / Create v000 / Review Panel: ninguno debe ofrecer ni mostrar `cg`.

## 9. Referencias técnicas

- **Convención de nombres:** [Docu_Logica_Nombres_Tracks.md](Docu_Logica_Nombres_Tracks.md)
- **Selección de clips:** [Docu_Metodos_Seleccion_Clip.md](Docu_Metodos_Seleccion_Clip.md)
- **Módulo central:** [LGA_NKS_Shared/LGA_NKS_GetClip.py](../LGA_NKS_Shared/LGA_NKS_GetClip.py)
  - Variables: `TRACK_comp_EXR`, `TRACK_roto_EXR`, `TRACK_cleanup_EXR`, `TRACK_cg_EXR`, `TRACK_comp_REV`, `TRACK_roto_REV`, `TRACK_cleanup_REV`, `TRACK_cg_REV`, `TASK_EXR_TRACKS`, `TASK_REV_TRACKS`, `CG_TASK_NAME`, `registered_task_names()`
- **Scope de tasks por contexto:** [LGA_NKS_Shared/LGA_NKS_TaskScope.py](../LGA_NKS_Shared/LGA_NKS_TaskScope.py) (no importa `hiero`)
  - Datos: `TRACK_TASKS`, `CG_TASK_NAME`, `BOTH`/`STUDIO_ONLY`/`CLIENT_ONLY`
  - Funciones: `resolve_mode()`, `all_track_task_names()`, `active_track_tasks()`, `is_track_task_active()`, `task_folder_name()`, `exr_track_for_task()`, `rev_track_for_task()`, `task_for_track()`
  - Test de consistencia: [LGA_NKS_Shared/tests/test_task_scope.py](../LGA_NKS_Shared/tests/test_task_scope.py)
- **Catálogo de tasks (Flow):** [LGA_NKS_Shared/LGA_NKS_Flow_Task_Config.py](../LGA_NKS_Shared/LGA_NKS_Flow_Task_Config.py)
  - Datos: `AVAILABLE_TASKS` (cada entrada declara `contexts`)
  - Funciones: `get_available_tasks()`, `get_available_task_names()`, `get_task_color()`
- **Flow Pull:** [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py)
  - Métodos: `HieroOperations.process_selected_clips()`, `HieroOperations.enable_or_disable_clips()`, `SGManager.find_highest_version_for_task()`
- **Flow Push:** [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py)
  - Funciones: `push_from_selected_clips()`, `_show_task_selection_dialog()`, `get_comp_assignee()`
- **Review Panel (panel):** [LGA_NKS_Review_Panel.py](../LGA_NKS_Review_Panel.py)
  - Métodos: `execute_DisableEXR()`, `execute_DisableRoto()`, `_segunda_task()`, `_second_task_button()`, `execute_DisableSecondTask()`
- **Review Panel (wrappers):** [LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py), [LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableRoto.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableRoto.py), [LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableCG.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableCG.py)
- **Edit Panel:** [LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py), [LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py)
- **Create v000:** [LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py)
  - Funciones: `_active_tasks()`, `_task_folder_map()`, `_tasks_human_list()`
  - Clase: `CreateV000Dialog` (`_build_task_box()`, `_selected_tasks()`, `available_task_count()`)
- **Import Shots:** [LGA_NKS_Edit_Panel_py/LGA_import_shots.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots.py)
  - Funciones: `_task_folders_for_context()`, `_stream_token()`, `_scan_publish_folders()`
- **Import Shots (preview):** [LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py)
  - Función: `classify_track_type()`
- **Create Shot:** [LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py)
  - Clase: `ShotConfigDialog` (genera secciones desde `get_available_tasks()`)
  - Carpetas: [LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py) (`TASK_FOLDER_STRUCTURE`)
- **Show in Flow:** [LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py)
  - Funciones: `_nombres_preferidos()`, `_task_preferida()`
- **Check Shots:** [LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py)
  - Funciones: `_tracks_de_tasks_activas()`, `_collect_shots_from_track()`
- **Advertencia Task/Track Mismatch:** [LGA_NKS_Shared/LGA_NKS_TaskMismatchDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskMismatchDialog.py)
  - Funciones: `collect_task_mismatches()`, `show_task_mismatch_warning()`
- **Selección de task en playhead:** [LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py](../LGA_NKS_Shared/LGA_NKS_TaskSelectionDialog.py)
  - Funciones: `get_tasks_at_playhead()`, `track_for_task()`, `prompt_task_selection()`, `resolve_task_at_playhead()`
- **Flow Shot_info:** [LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py](../LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py)
  - Métodos: `HieroOperations.process_selected_clips()`
