> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Triple Check (Flow | S3 Panel)

Botón verde del panel **Flow | S3**, al lado de Check Shots Exist. Compara, para cada shot y task del
timeline activo, la **última versión publicada (EXR)** en tres lugares:

| Fuente | Qué se lee | Cómo |
|---|---|---|
| **Flow** | Versions de la task que nombran al shot | API de Flow en vivo: 3 consultas por proyecto (Shots, Tasks, Versions) |
| **Wasabi** | Carpetas de versión del `*_publish` de la task | `list_objects_v2` con `Delimiter="/"`, 12 hilos |
| **Local** | Carpetas de versión del `*_publish` de la task | `os.scandir` sobre la raíz del contexto |

Además cruza los shots del timeline con los de Flow en las dos direcciones: hace lo mismo que Check
Shots Exist y le suma los shots de Flow que faltan en el timeline.

## Por qué existe

El EXR publicado de un shot tiene que estar en los tres lugares con el mismo número, y lo mueven
varias personas:

- **Studio:** el artista renderiza el `vNNN` a `4_publish`, lo sube a Wasabi y crea la Version en Flow.
  Cualquiera de los tres pasos se puede olvidar.
- **Client:** el vendor sube su entrega a Flow y a la plataforma de entregas del cliente, que no tiene
  acceso por API. El editor de VFX la baja a mano a la carpeta del shot y la sube a Wasabi. Si la bajó y
  no la subió, si la bajó a otra carpeta o si subió la de otro shot, los números dejan de coincidir.
- El supervisor y el editor trabajan en máquinas distintas: lo que uno subió el otro lo tiene que bajar.

Revisarlo card por card en PipeSync con 150 shots no es viable. El botón lo hace de una pasada y deja
un **Download** o un **Upload** en cada fila que lo necesita, como la columna de descarga del Flow Pull.

## Alcance

- **Tasks:** las del contexto que tienen track propio (`active_track_tasks()`): studio `comp`, `roto`,
  `cleanup`; client `comp`, `cg`.
- **Solo Publish (EXR).** Ni el `.nk` ni el MOV de review.
- **Shots del timeline:** los clips de los tracks de task (`_comp_`, `_roto_`, `_cleanup_`, `_cg_`),
  prendidos o apagados. Un shot con varios clips en el mismo track cuenta una vez.
- **Shots de Flow que faltan en el timeline:** solo los de las secuencias de Flow que ya aparecen en el
  timeline (un timeline de un episodio no reporta los shots de los otros), sin los omitidos (`omt`, `na`).

## Cómo se decide cada número

- **Regla de versión de una carpeta: la de PipeSync** (`VersionRules::parseVersionedEntry` +
  `TaskNameMapper`). `_v` más dígitos **al final** del nombre, y el nombre base tiene que terminar en un
  alias de la task (`comp`, `cmp`, `compo`). Así `SHOT_comp_v052_fix/` no es versión y una
  `SHOT_roto_v060/` dentro de `comp/4_publish` no se ofrece como comp. Si la regla fuera otra, el Triple
  Check y las cards de PipeSync mostrarían números distintos.
- **`v000` vale 0.** Es el placeholder de frames negros que crea `Create v000`. Se muestra, pero no es
  una entrega.
- **Una carpeta de versión sin archivos no cuenta** (mismo criterio que `LocalVersionContent` de
  PipeSync): una descarga cancelada deja la carpeta creada. Se baja a la versión anterior.
- **Flow:** solo cuentan las Versions cuyo `code` empieza con el nombre del shot o con su núcleo
  `PROY_SEQ_SHOT` (hay vendors que no ponen su código). La task Comp de un shot trae también Versions de
  minicuts (`PROJA_1005_MINICUT_v08`), y sin el filtro una de esas le ganaría a la versión real. Las
  Versions colgadas del shot **sin task** se asignan por el token de task del código (`_comp_v003`).
- **Carpeta de la task y del publish, sin distinguir mayúsculas.** Conviven `comp/` y `Comp/`. Se elige
  como en PipeSync: nombre canónico sin distinguir mayúsculas; si hay dos, gana el canónico y si no el
  primero alfabético. Dentro, la primera subcarpeta que contiene `_publish`.
- **Secuencia:** la de Flow (`sg_sequence`), como PipeSync. La de la ruta del clip queda de respaldo
  para los shots que Flow no tiene.
- **Raíz local: la del contexto** (`get_alt_work_root()`: `T:` studio, `N:` client o la `AltTPath`),
  igual que FileManagerS3. **No** la de la ruta del clip: un timeline de client abierto en contexto
  studio compararía el Wasabi de studio contra el disco de client y ofrecería subidas que no
  corresponden. Si la media del timeline está bajo otra raíz, la ventana lo avisa arriba. La
  `AltTPath` puede venir como `N:` sin barra, y `N:` + `VFX-X` es una ruta relativa a la carpeta actual
  de la unidad: `_project_folder()` le agrega la barra.
- **Bucket:** `resolve_bucket_for_project()`, con los overrides del contexto (un proyecto puede tener un
  bucket con otro nombre en client).

### CG (solo client)

CG junta entregas de varias disciplinas, cada una con su contador (`lighting_v016`, `animation_v005`),
así que el número no ordena. La última de Flow es la **última subida, por fecha**
(`LGA_NKS_CG_Versions.ultima_version_cg`), y en Wasabi y en local no se busca la más alta sino **si está
esa entrega** (`misma_entrega`: disciplina + número, ignora sufijos como `_SeqRef`). Las columnas
Wasabi y Local dicen `Yes` / `No`.

## Estados de una fila

Una fila es un (shot, task). `F`, `W`, `L` son los números de Flow, Wasabi y Local (0 = ninguna).

| Estado (texto en la UI) | Condición | Botón |
|---|---|---|
| `Error` | No se pudo leer Wasabi o el disco (policy, disco sin montar, publish plano) | — |
| `Not in Flow` | El shot no existe en Flow (lo de Check Shots Exist) | Upload, con pregunta |
| `Task not in Flow` | El shot existe pero no tiene esa task | Upload, con pregunta |
| `Not in timeline` | Shot y task en Flow, sin clip en el track | Download si `W > L` (no entra en Download all) |
| `Missing in Wasabi` | `F > W` y `F > L`: Flow tiene una versión que no está en ningún disco | — |
| `Incomplete` | `W = L` pero una tiene menos archivos (descarga o subida cortada) | Download o Upload |
| `Size differs` | `W = L`, misma cantidad de archivos y distinto peso total | — |
| `Wrong folder` | La carpeta tope lleva el nombre de **otro shot** (material en el lugar equivocado) | — |
| `Upload` | `L > W` | Upload |
| `Download` | `W > L` | Download |
| `No Flow version` | `max(W, L) > F`: hay un publish sin Version en Flow | — |
| `OK` | `F = W = L > 0` | — |
| `No versions` | `F = W = L = 0` | — |

Los estados no se excluyen: `F=10, W=8, L=5` es `Missing in Wasabi` (falta la v010) y además `Download`
(la v008 está en Wasabi y no en local). La columna **Sync** muestra el más importante en el orden de la
tabla y **Detail** explica todos en una oración cada uno. `Only issues` (prendido al abrir) oculta `OK` y
`No versions`.

**`Not in timeline` sin nada publicado no se oculta.** Un shot de Flow con su task y ninguna versión en
ningún lado es un shot creado y asignado que todavía no se empezó: lo que falta es armarlo en el
timeline (el plate y la v000). Detail lo dice así. Por eso esas filas cuentan como problema y quedan
visibles con `Only issues`.

## Columnas, orden y filtro

`Shot | Task | Task Status | Flow | Wasabi | Local | Sync | (botón) | Detail`.

- **Task Status:** el estado de la task en Flow (`sg_status_list`, leído en la misma consulta de Tasks),
  con el nombre y el color del catálogo `LGA_NKS_Flow_Status_Config`, los mismos de PipeSync y del Flow
  Pull. El texto va claro u oscuro según la luminancia del fondo. Un código que el catálogo no conoce
  sale crudo y sin color; sin task en Flow, `-`. La columna del chequeo se llama **Sync** y no Status
  para que no se confunda con esta.
- **Orden:** click en una cabecera ordena por esa columna; otro click, al revés; el tercero vuelve al
  orden de entrada (filas del timeline primero, por importancia del estado; después las de Flow que
  faltan en el timeline). Las versiones ordenan como número (`-` y `?` antes que `v000`) y Task Status
  en el **orden del flujo de trabajo** del catálogo (Not ready → In progress → reviews → entregas), no
  alfabético. Desempate siempre por shot. El orden es propio y no el de `QTableWidget`: la fila de la
  tabla sigue siendo el índice en `self.rows` (lo usan la navegación, el filtro y los botones masivos),
  y la tabla se rearma en cada orden.
- **Filtro por estado:** el combo al lado de `Only issues` lista los estados presentes con su cantidad
  (`Review Lega (12)`) y `No task in Flow`. Se suma a `Only issues`: con los dos se ve qué shots en
  Review Lega tienen algo desparejo; con `Only issues` apagado, todos los de ese estado. Download all y
  Upload all trabajan sobre lo que queda visible.

**`Incomplete`** compara cantidad de archivos y bytes de la versión tope, solo cuando Wasabi y local
tienen la misma. Un listado completo de esa carpeta en Wasabi y un `os.walk` local por fila.

## Acciones y sus protecciones

- **Download** baja la carpeta de la versión con FileManagerS3 (`--download <carpeta local>`). La ruta
  se arma con las mayúsculas de **Wasabi** en todos los tramos (secuencia, shot, task, publish), porque
  FileManagerS3 traduce la ruta local a la key de S3 tal cual. `--download` acepta una carpeta que todavía
  no existe.
- **Upload** sube la carpeta local de la versión (`--upload <carpeta>`), también con las mayúsculas de
  Wasabi. Un tramo que todavía no existe en Wasabi va con el nombre canónico (`comp`), como lo crea
  PipeSync: con `Comp/` en Wasabi y `comp/` en la ruta se crearía una carpeta paralela. En Windows la
  ruta resuelve igual porque el disco no distingue mayúsculas; si con ese caso no existe (macOS), se usa
  la ruta local real.
- **Upload bloqueado** (sin botón, con el motivo en Detail):
  - la carpeta local lleva el nombre de otro shot (subirla replicaría el error);
  - el publish local y el de Wasabi tienen nombres distintos (`3_publish` contra `4_publish`): quedarían
    dos carpetas de publish.
- **Download bloqueado** si la carpeta de Wasabi es de otro shot: bajarla copiaría el error al disco.
- **Upload con pregunta** cuando la local es más nueva que la última Version de Flow o el shot no tiene
  la task en Flow: en client suele ser una carpeta mal nombrada o un timeline de otro contexto. Esas filas
  no entran en Upload all.
- **Download all** baja todas las filas visibles del timeline en una sola llamada al CLI (acepta varias
  rutas). No incluye las de `Not in timeline`: en client bajaría las entregas de toda la secuencia.
- **Upload all**: `--upload` acepta una carpeta por llamada, y cada llamada extra le pasa el comando a
  la instancia abierta de FileManagerS3 por un canal que espera 500 ms y no reintenta. Con la app
  cerrada, la primera llamada todavía está arrancando y las demás se perderían con un cartel. Por eso la
  primera sale enseguida y las siguientes a los 9 s, de a una cada 2,5 s (`UPLOAD_FIRST_DELAY_MS`,
  `UPLOAD_STEP_MS`).
- Download all y Upload all preguntan antes, con la cantidad.
- Ninguna acción re-chequea sola: FileManagerS3 encola y transfiere en segundo plano. **Recheck** vuelve
  a correr todo.
- **Click en una fila del timeline** lleva el timeline a ese shot (`goto_shot`).

## Red, tiempos y errores

- **3 reintentos cada 5 s** en cada pedido a Flow y a Wasabi (regla de GateBouncer). El primer pedido de
  un programa nuevo lo frena el firewall (`WinError 10013`) hasta que se autoriza. Los reintentos quedan
  en el log: `Reintento 1 de conexion a Flow: [WinError 10013] ...`.
- Un `AccessDenied` de Wasabi (la policy no cubre ese shot) no se reintenta: es un error de la fila.
- Si Wasabi agota los reintentos por un error de **red**, el lister queda caído y los pedidos siguientes
  fallan al instante. Si no, ~600 listados con 15 s de reintentos cada uno serían minutos.
- Medido en un proyecto real en client: 162 clips, 227 filas, 30 s con la red ya autorizada.
- Todo corre fuera del hilo principal (`QThreadPool`); la recolección del timeline, que usa la API de
  Hiero, corre antes en el hilo principal.
- El core se recarga en cada click (`importlib.reload`): el panel carga el script de cero, pero el core
  queda en `sys.modules`, y una actualización con NKS abierto mezclaría la ventana nueva con la lógica
  vieja. Si el core salió de `sys.modules`, el paquete `LGA_NKS_Shared` conserva el atributo viejo y
  `reload` falla con `ImportError`: en ese caso se importa de cero (`importlib.import_module`).
- Log siempre a `LGA_HieroTools/logs/DebugPy_FlowTripleCheck.log`, pisado en cada corrida: fuentes,
  raíz, bucket, una línea por fila con lo que leyó de cada lado, reintentos y las rutas que se mandan a
  FileManagerS3.

## Cómo se prueba

- `tests/test_triple_check_core.py`: regla de versión, escaneo sobre un árbol falso, Versions de Flow
  (minicuts, sin task), todos los estados, rutas de Download/Upload, el `WasabiLister` con un cliente
  falso (paginación, AccessDenied sin reintento, red caída) y el orden de los estados de task.
- Ventana: harness de UI con `+Building_Blocks/UI_Capture/fixtures/h3_flow_triplecheck.py` (una fila
  por estado, datos ficticios); capturas en `_LGA_Release/UI_Captures/FlowTripleCheck_*.png`, entre
  ellas una ordenada por Task Status y otra filtrada por Review Lega.
- En vivo: con el dev-link se corre `collect_timeline()` y el worker sin abrir la ventana. Para probar
  otro contexto sin tocar el INI de la máquina, el worker se puede correr fuera de NKS con
  `LGA_HIEROTOOLS_CONTEXT_INI` apuntando a un INI propio, el Python de Nuke y los módulos de UI
  stubeados. **No** levantar Qt `offscreen` con ese Python sin `QT_PLUGIN_PATH`: Windows abre un cartel
  «no Qt platform plugin» en la pantalla del usuario.

## Referencias técnicas

- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_TripleCheck.py`
  - `main()`: recolecta el timeline, lanza el worker y abre la ventana.
  - `collect_timeline()`: clips de los tracks de task → `{project, shot, seq, task, clip, path, root}`.
  - `TripleCheckWorker._run()`, `_rows_for_project()`, `_new_row()`, `_scan_rows()`: Flow, raíz local,
    bucket, filas y escaneo en paralelo.
  - `_flow_connection()`, `_wasabi_client()` (boto3 vendorizado en `LGA_NKS_Assignee_Panel_py`),
    `_project_folder()`, `_with_net_retries()`.
  - `TripleCheckDialog`: tabla (`_fill_table()`, `_fill_row()`, `_task_status_item()`),
    `_set_action_cell()`, orden (`_on_header_clicked()`, `_sort_key()`), filtro
    (`_fill_status_filter()`, `_apply_filter()`), `_download_all()`, `_upload_all()`,
    `_upload_row()` (pregunta), `_on_cell_clicked()` (navegación).
  - `download_rows()`, `upload_rows()`, `bulk_download_rows()`, `bulk_upload_rows()`,
    `_launch_filemanagers3()`.
  - `version_text()`, `version_color()`, `detail_text()`: presentación de una fila.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_TripleCheck_Core.py`
  (sin hiero ni Qt)
  - `parse_versioned_folder()`, `versioned_entries()`, `TASK_FOLDER_ALIASES`, `version_number()`,
    `pick_folder()`, `pick_publish_folder()`.
  - `LocalLister`, `WasabiLister` (`list_dir`, `has_files`, `content_stats`, `dead`), `ListError`,
    `_with_retries()`, `on_retry`.
  - `scan_task()`, `resolve_shot_parts()`, `compare_content()`, `cg_folder_for()`.
  - `fetch_flow_project()`, `flow_highest()`, `flow_latest_cg()`, `version_belongs_to_shot()`,
    `shot_prefixes()`.
  - `classify()`, `is_issue()`, `has_no_versions()`, `STATUS_PRIORITY`, `download_target()`,
    `upload_source()`.
  - `task_status_info()`: nombre, color y orden del estado de la task.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Flow_S3_Panel.py`
  - `FlowProdPanel.triple_check_versions()`: carga el script y llama a `main()`.
  - `panel_tooltip_html()`: tooltips del panel en el globo propio.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`:
  `get_task_status_dict()` (catálogo de estados de task: nombre, color, orden del flujo).
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_CG_Versions.py`:
  `ultima_version_cg()`, `misma_entrega()`, `clave_de_version()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_TaskScope.py`:
  `active_track_tasks()`, `exr_track_for_task()`, `task_folder_name()`, `task_display_name()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`:
  `extract_shot_code_from_path()`, `extract_project_name_from_path()`, `extract_sequence_name_from_path()`,
  `normalize_task_name()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_BucketResolver.py`:
  `resolve_bucket_for_project()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`:
  `get_alt_work_root()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/SecureConfig_Reader.py`:
  `get_flow_credentials()`, `get_s3_credentials()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_FileManagerS3Launcher.py`:
  `build_filemanagers3_command()`, `resolve_context_mode()`.
- `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ShotNavigation.py`:
  `goto_shot()`.
- Reglas que se copian de PipeSync y FileManagerS3 (otros repos):
  `C:/Portable/LGA_FileManagerS3/src/utils/VersionRules.cpp` (`parseVersionedEntry`),
  `C:/Portable/LGA_PipeSync_2/src/utils/PathService.cpp` (`getHighestVersionNumber`),
  `C:/Portable/LGA_PipeSync_2/src/utils/TaskNameMapper.cpp`,
  `C:/Portable/LGA_FileManagerS3/src/main.cpp` (`startCliUpload`, parseo de `--download`/`--upload`).
- Check Shots Exist, que el Triple Check amplía:
  `C:/Users/leg4-pc/.nuke/Python/Startup/LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`.
