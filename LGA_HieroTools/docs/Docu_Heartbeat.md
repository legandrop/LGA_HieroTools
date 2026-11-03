> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Heartbeat: el archivo de latido de Hiero / NKS

## Por que existe

Con dos proyectos abiertos (algo normal en Nuke Studio) ni el titulo de la ventana ni la pantalla dicen cual tiene el
artista adelante, y adivinarlo mirando pixeles es lento y falla justo cuando importa. Otra app de la maquina necesita
saber que proyecto y que timeline estan al frente sin pedirle nada a NKS.

`LGA_NKS_Heartbeat` lo deja anotado en un archivo chico, un **archivo de latido**, y quien quiera lo lee. NKS no abre
ningun puerto ni expone ningun comando: solo escribe.

## Contrato del archivo

- **Donde:** `%APPDATA%\LGA\Heartbeat\<app>-<pid>.json` (macOS: `~/Library/Application Support/LGA/Heartbeat/`; la raiz
  sale igual que en `LGA_NKS_BurnIn_Config._user_config_root()`). Un archivo por proceso: dos NKS abiertos son dos
  archivos. `<app>` es `nukestudio` si `nuke.env["studio"]`, si no `hiero`.
- **La carpeta la crea quien lee, nunca este modulo.** Si no existe, no escribe nada: donde nadie lee no hace nada, y el
  orden de instalacion de las apps da igual. Si aparece despues, el chequeo siguiente (5 s) ya escribe.
- **Formato v1**, una linea de JSON con salto de linea final, solo ASCII (los acentos viajan como `\uXXXX`):

```json
{"v":1,"app":"nukestudio","host":"17.0v4","pid":35404,"updatedAt":"2026-11-03T14:52:10Z","basis":"timeline",
 "project":{"name":"PROJA_SUP_v004","key":"PROJA","path":"T:/VFX-PROJA/101_SUP/PROJA_SUP_v004.hrox"},
 "sequence":"101","open":[{"name":"PROJA_SUP_v004","key":"PROJA"},{"name":"PROJB_SUP_v012","key":"PROJB"}]}
```

  | Campo | Que es |
  |---|---|
  | `v` | Version del formato: `1`. |
  | `app` | `nukestudio` o `hiero`. |
  | `host` | Version del host (`nuke.NUKE_VERSION_STRING`, por ejemplo `17.0v4`); `null` si no se pudo leer. |
  | `pid` | Pid del proceso que escribe; es el mismo que lleva el nombre del archivo. |
  | `updatedAt` | UTC, `AAAA-MM-DDThh:mm:ssZ`, de la ultima escritura. |
  | `basis` | De donde sale `project`: `timeline`, `only-open` o `none`. |
  | `project` | `{name, key, path}` del proyecto al frente, o `null` si `basis` es `none`. |
  | `sequence` | Nombre del timeline activo; `null` si `basis` no es `timeline`. |
  | `open` | Todos los proyectos abiertos (`hiero.core.projects()`), cada uno `{name, key}`. |

- **`basis`**, la misma cadena que ya usa el BurnIn para el nombre del proyecto:
  - `timeline`: `project` es el del timeline activo (`hiero.ui.activeSequence().project()`).
  - `only-open`: no hay timeline activo y hay un solo proyecto abierto: ese.
  - `none`: no hay timeline activo y hay cero o varios proyectos: no se sabe, y no se inventa.
- **`key`** es la carpeta `VFX-<X>` de la ruta del proyecto, sin el prefijo (`extract_project_name_from_path()`). Un
  proyecto sin guardar tiene `path` vacio y `key` `null`.

## Cuando se escribe

- **La garantia es un `QTimer` de 5 s en el hilo principal.** Llama a `publish()`, que lee el estado de Hiero
  (`snapshot()`) y escribe solo si **cambio** o si pasaron **60 s** desde la ultima escritura (el pulso). El primer latido
  se escribe al arrancar.
- **Los eventos solo adelantan el chequeo.** `kAfterNewProjectCreated`, `kAfterProjectLoad`, `kAfterProjectSave`,
  `kAfterProjectClose`, `kCurrentViewerChanged` y `kContextChanged` reprograman un `QTimer` de un disparo a 400 ms que
  llama a `publish()`. Ningun evento trae el dato: sale siempre de `snapshot()`. Por eso un evento que no llega (o que
  llega de otro hilo y no puede reprogramar el timer) cuesta como mucho 5 s y nunca un dato falso; con eventos como unica
  fuente, uno perdido dejaria un dato viejo en silencio. Los 400 ms cubren que `kAfterProjectLoad` llega sin timeline
  nuevo y Hiero lo abre ~0,16 s despues (medido, ver `LGA_NKS_Projects_Panel.md`).
- **Escritura atomica:** se escribe `<app>-<pid>.json.tmp` en la misma carpeta y se reemplaza con `os.replace`, asi quien
  lee ve el archivo viejo o el nuevo, nunca uno a medias. En Windows `os.replace` falla si el lector tiene el archivo
  abierto: el error se anota una vez en el log, no queda ningun temporal y el chequeo siguiente reintenta (el estado no
  se da por escrito hasta que se escribe).
- **`kShutdown` borra solo el archivo propio** (`<app>-<pid>.json`). Nunca barre la carpeta. Si NKS se cae sin pasar por
  ahi queda un huerfano de unos 300 bytes, inofensivo por la regla de vigencia de abajo.
- **Solo sesiones con ventana.** Igual que `LGA_NKS_RemoteNav`: espera hasta 20 x 500 ms a que exista
  `hiero.ui.mainWindow()`; un Nuke `-t` o un worker del frame server no escribe nada.

## Para quien lo lee: cuando un latido vale

Se abre solo el archivo del pid de la ventana que esta al frente (no se recorre la carpeta) y vale si:

1. `v` es `1` y el `pid` del contenido es el del nombre del archivo;
2. la hora de modificacion no es anterior al inicio de ese proceso (un NKS muerto cuyo pid se reutilizo dejo su archivo);
3. la hora de modificacion es de hace menos de 5 minutos: el modulo late cada 60 s, y si dejo de latir no se confia
   aunque el proceso siga vivo.

**No usar `os.kill(pid, 0)` para saber si el proceso vive:** en Windows termina el proceso. Si el archivo falta, esta
roto o no vale, no hay dato y quien lee sigue como si NKS no latiera.

## Decisiones y lo que costo descubrir

- **Un archivo y no un comando en el server de `LGA_NKS_RemoteNav`.** Ese server solo lo atiende el primer NKS que abre el
  puerto, y agregarle un comando de estado amplia la superficie de red. Un archivo por proceso sirve a varios NKS a la vez
  y trae su vencimiento gratis (la hora del archivo).
- **Timer como garantia, eventos como aceleradores:** ver arriba. Los eventos de un build de Nuke que no tengan alguno de
  esos tipos se saltean y quedan anotados en el log.
- **`kShutdown` no desregistra los handlers.** `hiero.core.events.unregisterInterest()` reemplaza el contenido de la
  lista de callbacks que el despacho esta recorriendo en ese momento: sacar un handler adentro de `kShutdown` hace que
  Hiero se saltee al siguiente de la lista (se ve en `events.py`: `unregisterInterest()` y `_callCallbacks()`). Los
  handlers solo se sacan al reemplazar un latido por otro tras un reimport del modulo.
- **Un reimport reemplaza al latido anterior.** El latido vivo se guarda en `hiero.core._lga_heartbeat` (como el server de
  RemoteNav): al recargar el modulo se cortan los timers y se sacan los handlers del anterior, asi no se acumulan.
- **El proyecto es el del timeline activo aunque se mire el bin de otro proyecto.** Es un limite aceptado; si molesta,
  `kSelectionChanged` permitiria afinarlo.
- **La escritura corre en el hilo principal** (unos 300 bytes en la carpeta local de AppData, solo al cambiar o cada 60 s):
  Hiero solo se puede leer desde ese hilo y escribir es mas barato que pasarle el dato a un worker. Si `%APPDATA%`
  alguna vez fuera de red, la escritura tendria que pasar a un worker; el costo real lo mide la sonda.
- **Nada de pulso en el log:** el log anota los cambios, no cada minuto. Un log con una linea por pulso son cientos de
  lineas por dia sin informacion nueva.

## Lo que falta medir en NKS

Todo lo de arriba sale de leer el codigo de Hiero y de lo ya medido en otras tools; lo siguiente se mide con
`+Building_Blocks/explore_heartbeat_events.py` (no se versiona), en una sesion de prueba de NKS 16 y otra de NKS 17:

- que devuelven `hiero.core.projects()` y `hiero.ui.activeSequence()` con NKS recien abierto, sin proyecto, y en el grafo
  de nodos;
- cual de los seis eventos dispara de verdad al cambiar de timeline, abrir un segundo proyecto y cerrarlo, en que hilo y
  cuanto antes de que el estado sea visible;
- que `kShutdown` borre el archivo (el orden de los handlers decide si el de la sonda ve el archivo ya borrado);
- el costo de `snapshot()` y de la escritura atomica.

Una sesion de NKS abierta antes de instalar el modulo no late hasta que se la reinicia: `LGA_HieroTools_Startup.py` solo
carga los modulos al arrancar.

## Logs

- Consola apagada (`DEBUG = False`).
- `LGA_HieroTools/logs/DebugPy_Heartbeat.log`: se pisa al arrancar NKS. Anota el arranque (app, host, pid), la carpeta de
  latidos cuando aparece o desaparece, cada cambio de estado (basis, proyecto, timeline y proyectos abiertos), `kShutdown`
  y los errores (uno por mensaje distinto).

## Pruebas

`LGA_HieroTools/tests/test_heartbeat.py`, sin host (`hiero`, `nuke` y el adapter de Qt falsos), con el runtime embebido:

    LGA_NKS_Shared\OIIO_Win\bin\python\python.exe -B LGA_HieroTools\tests\test_heartbeat.py

Cubre los tres `basis`, el formato v1, que no escribe si no cambio y pasaron menos de 60 s, que si escribe a los 60 s,
que no escribe ni crea la carpeta si no existe, la escritura atomica y su reintento, los eventos como aceleradores,
el arranque sin ventana, el reimport y que `kShutdown` borra solo el archivo propio. Cada caso falla si se rompe el
codigo que protege.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Heartbeat.py`: `Heartbeat` (`start()`, `publish()`, `_publish()`, `_on_event()`, `_on_shutdown()`, `stop()`, `shutdown()`, `unregister()`), `snapshot()`, `write_atomic()`, `heartbeat_dir()`, `start_heartbeat()`, `_start_deferred()`, `_has_gui()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_NKS_Flow_NamingUtils.py`: `extract_project_name_from_path()` (la `key` del proyecto).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_BurnIn_py\LGA_NKS_BurnIn_Logic.py`: `_project_name()` (la cadena timeline / unico proyecto abierto).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_BurnIn_py\LGA_NKS_BurnIn_Config.py`: `_user_config_root()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_RemoteNav.py`: el patron del arranque (`_has_gui()`, `_start_deferred()`, handle en `hiero.core`).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\LGA_QtAdapter_HieroTools.py`: `QtCore`, `QtWidgets`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools_Startup.py`: `MODULES` (carga `LGA_NKS_Heartbeat` despues de `LGA_NKS_RemoteNav`).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\tests\test_heartbeat.py`: los tests.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\+Building_Blocks\explore_heartbeat_events.py`: la sonda (no se versiona).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\LGA_NKS_Projects_Panel.md`: lo medido sobre `kAfterProjectLoad` y el timeline que Hiero abre despues.
- `C:\Program Files\Nuke17.0v4\pythonextensions\site-packages\hiero\core\events.py`: `registerInterest()`, `unregisterInterest()`, `_callCallbacks()` y los tipos de evento (`kShutdown`, `kAfterProjectLoad`, `kCurrentViewerChanged`...).
