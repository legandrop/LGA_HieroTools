# LGA_HieroTools - Contexto Studio/Client (integración con PipeSync)

## Referencia principal

Este documento complementa a:

- `C:/Portable/LGA_PipeSync_2/Docs/Doc_Studio_Client_Context.md`

PipeSync define la arquitectura de contexto. Este MD documenta cómo se aplica en
HieroTools, qué scripts quedaron adaptados y cuáles requieren revisión adicional.

## Estado actual

- Control de contexto por INI: `LGA_HieroTools_context.ini` (`mode=studio|client`).
- Resolución de `config.secure/.key` por contexto activo.
- Resolución de cache/DB por contexto activo (con fallback portable histórico).
- Preflight bloqueante en Pull/Push con mensajes UI cuando faltan prerequisitos.
- Projects Panel con switch Studio/Client visible solo para `lega@wanka.tv`
  (leyendo PipeSync normal).
- Para los demás usuarios, el Projects Panel no crea ni conecta los botones del
  switch; el panel inicia normalmente y usa el contexto configurado.

## Reglas operativas

- Si falta `config.secure` o `pipesync.db`, Pull y Push muestran error claro.
- Push además valida `Flow.Url`, `Flow.Login`, `Flow.Password`.
- En client no se debe caer en DB studio como fallback funcional.
- El switch Studio/Client actualiza INI, fuerza recarga del Projects Panel y
  avisa por el bus a los paneles suscriptos.
- Scope de tasks por contexto:
  - `studio`: tasks `comp`, `roto`, `cleanup` (no existe `cg`).
  - `client`: tasks `comp` y `cg` (no se consideran `roto`/`cleanup`).
  - La fuente de este scope es
    [LGA_NKS_Shared/LGA_NKS_TaskScope.py](../LGA_NKS_Shared/LGA_NKS_TaskScope.py)
    (`TRACK_TASKS`, `active_track_tasks(mode)`, `is_track_task_active()`):
    NO importa hiero, así que lo consultan tanto scripts que corren dentro de
    NKS como tests y módulos compartidos que no pueden cargar `hiero`. Todo
    catálogo o UI que decida qué tasks ofrecer o revisar por contexto tiene
    que resolverlo desde ahí y no mantener su propia lista en paralelo.
  - La task `cg` agrupa todas las disciplinas/streams del shot (layout,
    lighting, anim, fx, ...); el filename de cada versión lleva el stream,
    nunca el token "cg". Ver
    [Docu_Logica_Nombres_Tracks.md](Docu_Logica_Nombres_Tracks.md) y
    [Docu_MultiTask.md](Docu_MultiTask.md) para la convención de tracks y el
    concepto de stream.
  - `normalize_task_name()` (en `LGA_NKS_Flow_NamingUtils.py`) aplica en
    client la **familia CG por exclusión**: toda task que no esté en
    `all_track_task_names()` de `LGA_NKS_TaskScope` (`comp`, `roto`,
    `cleanup`, `cg`) normaliza a `cg`. No hay una lista de streams que
    mantener. En studio esta regla no se activa. Detalle en
    [Docu_TaskName_Aliases.md](Docu_TaskName_Aliases.md).

## Paneles dinamicos por contexto

El switch existe para **un solo usuario**. El resto tiene contexto FIJO, definido
por el zip que instalo (ver Packaging), y nunca lo cambia en caliente. Por eso
toda la maquinaria dinamica esta detras de un gate:

- `LGA_NKS_Shared/LGA_NKS_ContextSwitch.py` resuelve `has_context_switch()`
  comparando el `Flow.Login` del perfil PipeSync **normal** contra
  `SWITCH_USER_LOGIN`. El resultado no cambia durante la sesion, asi que se
  memoiza: resolverlo implica leer y desencriptar `config.secure`, y antes lo
  hacian por separado el Projects Panel (dos veces), el UIManager y el ViewerTL.
- Si el gate da **False**, `subscribe()` y `notify()` no hacen nada: no se
  instancia el QObject del bus, no se conecta ninguna senal y no queda ningun
  callback vivo. El panel lee `get_context_mode()` una vez en `__init__` — una
  lectura de INI que ya ocurria — arma su UI y ahi termina.
- Si da **True**, recien ahi se crea el bus. `ProjectsPanel.set_context_mode()`
  emite **despues** de escribir el INI, porque los suscriptos releen el contexto
  y tienen que ver el valor nuevo.

Paneles suscriptos: Flow Panel (`on_context_changed` -> `build_buttons`) y
Assignee Panel (`on_context_changed` -> `build_buttons`).

### Estados de Flow por contexto

Los dos sitios de Flow no tienen la misma lista de `sg_status_list`, asi que los
botones del Flow Panel y los dropdowns de Create Shot se filtran por contexto.
Detalle completo en [Docu_Flow_Estados_Colores.md](Docu_Flow_Estados_Colores.md).

### Assignee Panel en client

En client el panel queda **deshabilitado**, con el motivo a la vista. No es una
decision de UI: es que ahi no hay assignees que mostrar.

- El envelope `HumanUser.sg_pipesync_user_json` es un custom field que solo
  existe en el sitio de studio. En client todos los usuarios llegan con
  `assignable = 0`.
- La `pipesync_stats.db` de client tampoco tiene las columnas `panel_order` y
  `skip_wasabi_policy`, asi que la query de `load_flow_users()` levantaba
  `OperationalError` y devolvia lista vacia.
- Las policies de Wasabi por shot no aplican: en client el acceso se resuelve con
  Vendor Groups y permission rules de Flow.

Antes de este cambio el panel se dibujaba igual, con los dos botones fijos y
ningun usuario — indistinguible de "PipeSync todavia no sincronizo", que es un
problema distinto y con arreglo.

## Impacto en herramientas de Edit

- `Create v000` ([LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py)):
  - Las tasks activas salen de `_active_tasks()`, que resuelve
    `LGA_NKS_TaskScope.active_track_tasks()` **en cada llamada** (no hay
    constante `CLIENT_TASKS`/`ALL_TASKS` ni función `_resolve_active_tasks()`:
    ese diseño se reemplazó porque una constante de módulo quedaba fijada al
    valor del arranque y no reflejaba un switch de contexto en caliente). En
    `client` esto resuelve a `("comp", "cg")`, y la UI muestra los botones
    `comp` y `cg`.
  - `TASK_FOLDER` sale de `_task_folder_map()` (deriva de
    `LGA_NKS_TaskScope.task_folder_name()`) y resuelve `"cg" -> "CG"`. No
    existe un dict `TASK_COLORS` local: el color de cada task sale de
    `get_task_color()` del catálogo compartido
    ([LGA_NKS_Flow_Task_Config.py](../LGA_NKS_Shared/LGA_NKS_Flow_Task_Config.py)),
    y el de `cg` es `#CA7A3B` (naranja de la familia 3D), no cyan.
  - Orden de tracks en el timeline de client: `BurnIn` > `_comp_` > `_cg_` >
    plates.
  - El chequeo de solape/versions en timeline para elegibilidad de shot
    considera ambas tasks de client.
- `Import Shot` ([LGA_NKS_Edit_Panel_py/LGA_import_shots.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots.py)
  y [LGA_import_shots_preview.py](../LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py)):
  - En `client`, CG es una task de primera clase del import: tiene su color
    (`_CLR_CG`, vía `get_task_color(CG_TASK_NAME)`), su lugar en el orden de
    tracks (`_cg_` justo debajo de `_comp_`) y su carpeta de publish
    (`_task_folders_for_context()` suma `CG` a `TASK_FOLDERS` solo si
    `is_track_task_active(CG_TASK_NAME)`; en studio esa función devuelve
    `TASK_FOLDERS` sin cambios). La detección es siempre por carpeta de
    publish y por nombre de track, nunca por filename.
  - Dentro de la carpeta `CG`, la versión "más alta" se calcula **por
    stream** (`_stream_token()`), porque una sola carpeta CG agrupa
    disciplinas (layout, lighting, anim, ...) con numeración independiente
    cada una; un máximo global dejaría a todas menos una sin marcar como
    última.
  - En `client`, el flujo post-import `Create v000` hereda el scope de tasks
    del contexto (`comp` y `cg`).
- `Create NK v000` ([LGA_NKS_Edit_Panel_py/LGA_NKS_CreateNKScript.py](../LGA_NKS_Edit_Panel_py/LGA_NKS_CreateNKScript.py))
  es **solo de la task comp, a propósito y por decisión cerrada**: las
  entregas de CG llegan renderizadas del vendor y no se componen en Nuke, así
  que esa task no necesita script `.nk`. No es una limitación pendiente de
  resolver; si alguna vez cambia el flujo, hay que reabrir la decisión antes
  de tocar el código.

## Nombre de las carpetas de task en disco

La carpeta de cada task dentro del shot va **capitalizada**: `Comp`, `Roto`,
`Cleanup`, `CG`, `DMP`. Ese es el nombre canónico y sale de
`LGA_NKS_TaskScope.task_folder_name()`.

Los shots creados antes de unificar esto las tienen en minúscula, porque
`Create Shot Folders` era la única herramienta que las escribía así mientras
todos los lectores armaban la ruta capitalizada. En Windows la diferencia no
se nota porque el filesystem no distingue mayúsculas; **en macOS `comp/` y
`Comp/` son dos carpetas distintas** y el lector no encuentra nada.

Por eso nada arma el nombre de la carpeta con un literal:

- Para **leer**, `LGA_NKS_TaskScope.resolve_task_folder(shot_root, task)`
  devuelve el caso real que hay en disco, y el canónico si la carpeta todavía
  no existe.
- Para **crear**, `LGA_NKS_Flow_CreateShot_Folders.resolve_existing_case()`
  respeta el caso de los segmentos que ya existan, así un shot histórico no
  queda partido en dos carpetas.

## Impacto en Coordination Panel

- `Create Shot` ([LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py)):
  el diálogo de creación genera una sección por task con
  `get_available_tasks()` de `LGA_NKS_Flow_Task_Config` en vez de iterar
  `AVAILABLE_TASKS` completo. En `client` eso ofrece únicamente `Comp` y
  `CG`; en `studio`, todo el catálogo salvo `CG`.
  ([LGA_NKS_Flow_CreateShot_Folders.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py)
  suma la estructura de carpetas de `CG` — una sola carpeta para todas las
  disciplinas, sin subdividir por stream.)
- `Show in Flow` ([LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py)):
  la task a abrir sale de `_task_preferida()` / `_nombres_preferidos()`. En
  `studio` el orden de preferencia sigue siendo únicamente `("Comp",)`,
  idéntico al comportamiento histórico. En `client` es `("Comp", "CG")`: si
  el shot no tiene task Comp, cae a CG en vez de abrir la URL del shot
  pelado.
- `Check Shots` ([LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py](../LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py)):
  en `studio` sigue revisando solo el track `_comp_`. En `client` suma
  `_cg_` (`_tracks_de_tasks_activas()`) y recorre TODOS los tracks que
  coincidan con cada nombre, no solo el primero, porque puede haber varios
  `_cg_` en el mismo timeline (uno por stream).

## Impacto en Review Panel

- El segundo botón ON/OFF ya no es siempre `_roto_`: `_segunda_task()`
  ([LGA_NKS_Review_Panel.py](../LGA_NKS_Review_Panel.py)) resuelve la
  segunda task activa desde `LGA_NKS_TaskScope.active_track_tasks()`. En
  `studio` sigue siendo `roto` (`LGA_NKS_Clip_DisableRoto.py`); en `client`
  es `cg`, con el wrapper nuevo
  [LGA_NKS_Clip_DisableCG.py](../LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableCG.py)
  (mismo patrón que `DisableRoto`: envuelve `LGA_NKS_Clip_DisableEXR` con
  `track_name=exr_track_for_task("cg")` y `enable_rev_fallback=False`). El
  atajo de teclado (`Ctrl+Shift+D`) es el mismo en los dos contextos.

## Archivos adaptados (confirmados)

### Núcleo de contexto

- `LGA_HieroTools_context.ini`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextSwitch.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`
- `LGA_HieroTools/LGA_NKS_Shared/SecureConfig_Reader.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_BucketResolver.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPreflight.py`
- `LGA_HieroTools/docs/Docu_Context_Profile.md`

### Flow Pull / Push

- `LGA_HieroTools/LGA_NKS_Flow_Panel.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`

### Projects

- `LGA_HieroTools/LGA_NKS_Projects_Panel.py`
- `LGA_HieroTools/LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
- `LGA_HieroTools/LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`

### Edit / CreateV000

- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_NKS_CreateV000.py`
- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_import_shots.py` (flujo post-import hacia CreateV000; reconoce la task/track CG)
- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_import_shots_preview.py` (clasifica tracks `_cg_` en el preview)

### Scope de tasks por contexto (TaskScope)

- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_TaskScope.py` (módulo nuevo; no importa hiero)
- `LGA_HieroTools/LGA_NKS_Shared/tests/test_task_scope.py` (verifica consistencia contra `LGA_NKS_GetClip.py` leyéndolo como texto)
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Task_Config.py` (`contexts` por task, `get_available_tasks()`)
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py` (familia CG lee `all_track_task_names()` de TaskScope)

### Coordination Panel (Create Shot / Show in Flow / Check Shots)

- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`

### Review Panel

- `LGA_HieroTools/LGA_NKS_Review_Panel.py` (segundo botón ON/OFF por contexto)
- `LGA_HieroTools/LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableCG.py` (wrapper nuevo)

## Archivos revisados que siguen parciales o con deuda

- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py`
  - usa rutas hardcodeadas de instalación (no completamente context-aware).
- `LGA_HieroTools/LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`
  - requiere confirmar matriz Studio/Client en entorno deploy.
- `LGA_HieroTools/+Building_Blocks/PipeSync_Usuario_Actual.md`
  - documentación desactualizada respecto a estructura actual shared/contexto.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull_README.md`
  - referencias históricas y ejemplos con paths legacy.

## Packaging (release generator)

- El `_LGA_ReleaseGen-HieroTools.bat` genera dos zips y cada uno viaja con un
  `LGA_HieroTools_context.ini` fijado por el packaging, independiente del
  INI activo de Lega al momento de releasar:
  - Zip público `*_gh.zip`: `mode = client` (fuente:
    `Python/Startup/LGA_HieroTools_context_gh.ini`).
  - Zip interno `*.zip`: `mode = studio` (fuente:
    `Python/Startup/LGA_HieroTools_context_studio.ini`).
- Los INI fuente son fijos, versionados y verificados por preflight
  (existencia + valor de `mode`) antes de empaquetar.
- El INI se agrega al zip con 7z desde un directorio temporal renombrado a
  `Startup/LGA_HieroTools_context.ini`, así el installer lo deposita en el
  path esperado.
- El `i_win_engine.ps1` copia el `LGA_HieroTools_context.ini` a
  `%USERPROFILE%/.nuke/python/startup/` siempre pisando el previo. No se
  respeta el INI del usuario final: la política es que el modo lo define el
  zip que se instala (client para gh, studio para interno).
- Consecuencia: la editora del cliente siempre arranca en modo client sin
  intervención manual, y los demás reviewers de estudio siempre arrancan en
  studio (sin ver el switch, porque su `Flow.Login` de PipeSync normal no
  es `lega@wanka.tv`).

## Decisiones de diseño implementadas

- Switch en Projects Panel:
  - persistencia en `LGA_HieroTools_context.ini`;
  - override de sesión vía `LGA_HIEROTOOLS_CONTEXT_INI` y `PIPESYNC_CONTEXT`;
  - recarga de panel/proyectos sin reinicio obligatorio.
- Visibilidad del switch:
  - solo si `Flow.Login` de `%APPDATA%/LGA/PipeSync/config.secure` es
    `lega@wanka.tv`.
- Preflight:
  - validación común para Pull/Push con mensajes de error accionables.

## Gaps detectados (seguimiento)

- Unificar paths de runtime/ejecutable de PipeSync en módulos de Coordination.
- Revisar documentación auxiliar para eliminar ejemplos studio-only.
- Validar en QA que todos los paneles abiertos en sesión refrescan contexto sin
  reinicio en escenarios edge.
