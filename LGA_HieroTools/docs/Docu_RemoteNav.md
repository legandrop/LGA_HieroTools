> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Remote Nav: saltar a un shot desde PipeSync

## Por que existe

Desde PipeSync (tab PROD, click derecho sobre una fila > `Show shot in NukeStudio`) se
puede pedirle al Hiero/NKS abierto que lleve su timeline a ese shot: secuencia correcta,
clip seleccionado, In/Out marcados, playhead en el shot y Zoom to Fit. Antes habia que
buscar el shot a mano en el timeline.

Hace falta algo adentro de NKS que reciba el pedido. `LGA_NKS_RemoteNav` es ese "buzon":
un server local que arranca solo con HieroTools. La busqueda y la navegacion viven en
`LGA_NKS_ShotNavigation`, sin nada de red, asi que se pueden llamar desde cualquier tool.

## Contrato del protocolo

- TCP en `127.0.0.1:54327`. Solo localhost.
- Una linea JSON por mensaje, UTF-8, terminada en `\n`. El server lee hasta el primer
  `\n` (juntando todos los fragmentos que lleguen) e ignora lo que venga despues.
- El cliente manda UN pedido. El server contesta cero o mas lineas intermedias y UNA
  final, y cierra la conexion.
- Comandos (lista fija, nunca `exec`):
  - `{"cmd": "ping"}` -> `{"status": "ok", "server": "LGA_NKS_RemoteNav", "version": "...", "protocol": 1, "pid": ..., "busy": false}`
  - `{"cmd": "goto_shot", "project": "PROJA", "shot": "PROJA_010_0100", "sequence": "010", "task": "comp"}`.
    `project` y `shot` son obligatorios; `sequence` y `task` solo orientan la busqueda.
- Estados de la respuesta a `goto_shot`:

  | status | Tipo | Significado |
  |---|---|---|
  | `opening` | intermedio | El proyecto no estaba abierto y se va a abrir. `detail` = nombre del `.hrox`. |
  | `ok` | final | Navego. Trae `sequence`, `track`, `clip`, `in_frame`, `out_frame`, `clips_of_shot`, `opened_project`. |
  | `not_found` | final | El proyecto esta abierto pero ningun clip es de ese shot. |
  | `no_project` | final | No hay `.hrox` para ese proyecto en el root del contexto. |
  | `busy` | final | Hay otro pedido en curso. |
  | `error` | final | Cualquier otra falla; `detail` trae el traceback o el motivo. |

- `detail` es texto crudo en castellano: el cliente lo muestra en su boton "Details", no
  en el mensaje principal.
- Limites: linea de hasta 64 KB, campos de hasta 256 caracteres, 5 s para que llegue la
  linea completa, y 170 s de tope por pedido (watchdog que libera el `busy`).

## Como se busca el shot

`LGA_NKS_ShotNavigation.goto_shot()`:

1. **Proyectos candidatos:** los proyectos abiertos cuyo `.hrox` cuelga de la carpeta
   `VFX-<project>` (misma clave que usa el Projects Panel, `obtener_clave_proyecto()`),
   sin distinguir mayusculas. No se filtra por contexto Studio/Client: se busca en lo que
   este abierto.
2. **Si no hay ninguno, se abre:** `find_project_hrox()` busca en el root del contexto
   (`get_base_scan_path()`: AltTPath de PipeSync, o `T:\` / `N:\`) la carpeta
   `VFX-<project>`, y adentro de sus `*_SUP` la version mas alta de cada proyecto. Si hay
   mas de uno (por ejemplo `PROJA_SUP` y `PROJA_Breakdown`), gana aquel cuya clave de grupo
   (`obtener_clave_proyecto_archivo()`, sin version ni sufijos como `_Mac`) se muestra igual
   que el nombre del proyecto. Son dos listados de carpeta en el hilo principal, no el
   escaneo entero del root que el panel hace en un worker. Se abre con los mismos pasos que un click en el Projects
   Panel (`begin_project_open()`, `openProject()`, `start_scan()`,
   `after_project_open(..., on_done=...)`) y la navegacion corre en el `on_done`, cuando la
   post-apertura termino. Antes de abrir se contesta `opening` (el server hace `flush()` al
   escribirla, asi que sale antes de que `openProject()` bloquee el hilo principal).
3. **Orden de las secuencias:** la activa (si es de esos proyectos), las que se llaman
   como `sequence`, y el resto. Gana la primera secuencia que tenga el shot.
4. **Un clip es del shot** si alguna carpeta de la ruta de su media se llama como el shot
   (segmento entero), o si `extract_shot_code(clean_base_name(filename))` da el shot. Es el
   mismo criterio que el Flow Pull. Si la ruta tiene `VFX-<otro>`, el clip se descarta.
   Se ignoran los `EffectTrackItem`.
5. **Que clip se elige** dentro de la secuencia: el del track de la task pedida (o uno
   cuyo filename sea de esa task), despues `_comp_`, despues el resto de `TASK_EXR_TRACKS`,
   despues `EditRef`, despues cualquier otro track. Empate: el `timelineIn` mas chico.
6. **Navegacion:** `switch_to_sequence_hybrid()` del Projects Panel (el mismo switch que
   un click en una secuencia). Despues, **esperando `MEMORY_RESTORE_RETRY_MS` + 100 ms**, se
   vuelve a buscar el clip en la secuencia ya activa (el switch reabre el timeline), se
   selecciona, In/Out del clip de `EditRef` que lo cubre (si no hay, del propio clip),
   playhead al In, NKS al frente, foco al timeline y Zoom to Fit.

## Decisiones y lo que costo descubrir

- **El foco al clip espera al reintento de la memoria de vista.** El switch restaura la
  vista guardada de la secuencia (zoom, scroll y playhead, `LGA_NKS_TimelineMemory`) y deja
  programado un segundo intento a `MEMORY_RESTORE_RETRY_MS` (150 ms). Si el playhead y el
  Zoom to Fit se aplican antes, ese reintento los pisa y queda la vista vieja con el clip
  seleccionado. Vale tambien despues de abrir un proyecto, porque la post-apertura usa el
  mismo switch.
- **Zoom to Fit necesita el foco en el timeline:** antes de dispararlo se activa la ventana
  del timeline, igual que el Flow Pull.
- **Un pedido vencido no navega:** si el watchdog ya libero el pedido (por ejemplo, la
  apertura tardo mas de 170 s), `goto_shot()` recibe `is_current()` en `False` y no mueve el
  timeline, para no pisar un pedido que haya entrado despues.

- **El server es un `QTcpServer` en el hilo principal**, no un socket de Python con hilos
  como el de OpenInNukeX. Los slots ya corren en el main, asi que no hace falta
  `executeInMainThreadWithResult`. El despacho igual se difiere con
  `QTimer.singleShot(0)`: el switch de secuencia procesa eventos, y hacerlo adentro del
  slot de `readyRead` lo reentraria.
- **Puerto exclusivo.** En Windows `QTcpServer.listen()` usa `SO_EXCLUSIVEADDRUSE`: un
  segundo NKS no puede escuchar el mismo puerto y lo deja en su log. Con `SO_REUSEADDR`
  (el socket de Python de OpenInNukeX y el dev-link) dos procesos quedan escuchando a la
  vez: se vio en vivo con el puerto 54321, abierto al mismo tiempo por NKS y por un worker
  del frame server.
- **Varios NKS abiertos:** contesta el primero que abrio el puerto. Es un limite aceptado
  para esta version; la alternativa (rango de puertos) esta en `ROADMAP.md`.
- **Solo en sesiones con ventana:** el arranque espera a que exista `hiero.ui.mainWindow()`
  (20 reintentos de 500 ms). Un Nuke `-t` o un worker del frame server no arranca nada.
- **Nunca carteles en NKS:** todo resultado vuelve al cliente, que avisa en PipeSync. Un
  modal en NKS quedaria escondido detras de PipeSync.
- **Traer NKS al frente:** en Windows un proceso de fondo no puede tomar el foco solo.
  PipeSync llama a `AllowSetForegroundWindow` antes de mandar el pedido, y
  `_bring_main_window_to_front()` usa `SetForegroundWindow` con ese permiso.
- **`QtNetwork` es opcional en el adapter:** si un build de Nuke no lo trajera, el import
  no puede romper el adapter y con el todas las tools. Sin `QtNetwork` solo no arranca el
  server (y lo dice el log).
- **Seguridad:** cualquier proceso local puede pedir una navegacion o que se abra un
  proyecto del root del contexto. No ejecuta codigo ni toca archivos. Aceptable en una
  maquina de trabajo; si hiciera falta, el paso siguiente seria un token compartido.

## Logs

- Consola del host, al arrancar (mismo estilo que OpenInNukeX): `LGA_NKS_RemoteNav active on
  port 54327`, o `LGA_NKS_RemoteNav inactive: port 54327 already in use (...)` si otro Hiero /
  NukeStudio ya lo tiene. Deja claro cual sesion atiende a PipeSync. Solo sale en Hiero y
  NukeStudio: son los unicos que cargan `Python/Startup`.
- `LGA_HieroTools/logs/DebugPy_RemoteNav.log`: sesion del server (arranque y una linea por
  pedido con su resultado). Se pisa al arrancar NKS.
- `LGA_HieroTools/logs/DebugPy_ShotNavigation.log`: detalle del ultimo pedido (proyectos,
  secuencia elegida, track, EditRef). Se pisa en cada pedido.
- El switch escribe su traza en `DebugPy_ProjectsPanel.log`, como siempre.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_RemoteNav.py`: `RemoteNavServer` (`start()`, `dispatch()`, `_goto_shot()`, `_finish_request()`, `_on_watchdog()`), `_Connection` (`_on_ready_read()`, `send()`), `start_server()`, `_start_deferred()`, `_has_gui()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_NKS_ShotNavigation.py`: `goto_shot()`, `open_projects_for()`, `find_shot()`, `_clip_matches_shot()`, `_clip_rank()`, `_ordered_sequences()`, `find_project_hrox()`, `_open_then_navigate()`, `_focus_clip()`, `_bring_main_window_to_front()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel.py`: `ProjectsPanel.after_project_open()` (parametro `on_done`), `_call_post_open_done()`, `begin_project_open()`, `end_project_open()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_Projects_Panel_SwitchSequence.py`: `switch_to_sequence_hybrid()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_Projects_Panel_ScanProjects.py`: `get_base_scan_path()`, `obtener_clave_proyecto()`, `obtener_nombre_display_proyecto()`, `_agrupar_hrox_por_proyecto()`, `_elegir_version_mas_alta()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_NKS_Flow_NamingUtils.py`: `extract_shot_code()`, `clean_base_name()`, `extract_project_name_from_path()`, `extract_task_name()`, `normalize_task_name()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_QtAdapter_HieroTools.py`: `QtNetwork` (opcional).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools_Startup.py`: `MODULES` (carga `LGA_NKS_RemoteNav` despues del Projects Panel).
- Cliente: `C:\Portable\LGA_PipeSync_2\src\services\NukeStudioNavigator.cpp` (repo de PipeSync), doc `C:\Portable\LGA_PipeSync_2\Docs\Doc_Saltar_Shot_NukeStudio.md`.
