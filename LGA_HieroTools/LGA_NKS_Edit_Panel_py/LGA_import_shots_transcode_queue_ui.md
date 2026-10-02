> **Regla de documentacion**: este archivo describe la UI prevista para `LGA_import_shots_transcode_queue_ui.py`. No es un historial de cambios.
> **Estado general**: implementado, pendiente de test en Hiero.

# UI - Import Shots - Transcode Queue

Ventana flotante no modal para visualizar la cola global de transcode de `Import Shot`.

Modulo previsto:

```text
LGA_NKS_Edit_Panel_py/LGA_import_shots_transcode_queue_ui.py
```

Clase principal prevista:

```python
TranscodeQueueWindow
```

Funcion publica prevista:

```python
show_queue_window(manager, parent=None, focus_window_callback=None)
```

El boton `Open Queue` en `LGA_import_shots.py` debe llamar a esta funcion. La UI recibe el
manager global existente; no crea otro manager ni decide el orden de la cola.

---

## Proposito

Mostrar al usuario que conversion esta corriendo ahora, que plates siguen en fila y que
jobs terminaron mientras la ventana estuvo abierta.

La unica accion sobre la cola es `Skip Current`, que saltea el plate en curso. Fuera de
eso:

- No reordena jobs.
- No quita jobs pendientes.
- No pausa la cola.
- No toca archivos ni ejecuta transcodes (el skip lo resuelven el manager y el worker).

---

## Layout

Estructura general:

```text
Import Shots - Transcode Queue
────────────────────────────────────────────────────────
Shot          Plate                  Duration      Status
TEST_014_010  TEST_014_010_aPlate... 184f - 7.7s  [barra progreso]
TEST_014_010  TEST_014_010_bPlate... 184f - 7.7s  Queued #1
TEST_014_020  TEST_014_020_aPlate... 78f - 3.3s   Queued #2
TEST_014_020  TEST_014_020_bPlate... 484f - 20.2s DONE (18.6s)
────────────────────────────────────────────────────────
[Show All Import Windows] [Clear Completed] [Skip Current] CPU [High (6/6)]   ☐ Keep this window on top
```

La tabla debe usar una estetica similar a la tabla de la seccion Convert:

- Fondo oscuro `#272727`.
- Headers sobrios.
- Sin grid visible.
- Bordes y separadores compatibles con `Import Shot`.
- Tipografia y tamanos similares a la tabla de transcode.

---

## Columnas

| Columna | Contenido |
|---------|-----------|
| Shot | Nombre del shot como boton plano clickeable |
| Plate | Nombre de secuencia |
| Duration | Frames y segundos, por ejemplo `484f - 20.2s` |
| Status | Barra de progreso, `Skipping…`, `Queued #N`, `DONE (Xs)`, `Error`, `Skipped` o `Cancelled` |

No se agrega columna `Pos`: la posicion global se comunica dentro de `Status` con
`Queued #N`. El job activo se identifica por la barra de progreso.

---

## Columna Shot

El texto de `Shot` funciona como boton plano:

- Sin fondo.
- Sin borde.
- Color principal `SHOTNAME_COLOR`.
- Hover con mas brillo, sin subrayado.
- Click trae al frente la ventana de `Import Shot` si todavia existe.
- Si la ventana fue cerrada, no hace nada visible y registra el evento en log.

Se agrega una segunda constante para esta UI:

```python
SHOTNAME_COLOR_ALT = "..."
```

La tabla alterna entre `SHOTNAME_COLOR` y `SHOTNAME_COLOR_ALT` cuando cambia el shot en la
lista ordenada global:

```text
TEST_014_010  SHOTNAME_COLOR
TEST_014_010  SHOTNAME_COLOR
TEST_014_020  SHOTNAME_COLOR_ALT
TEST_014_020  SHOTNAME_COLOR_ALT
TEST_014_030  SHOTNAME_COLOR
```

La alternancia es por bloque de shot consecutivo, no por fila.

---

## Columna Plate

Muestra el nombre de la secuencia usando el mismo criterio visual que la columna `Nombre`
de la tabla Convert:

- Si el plate comienza con `shot_name`, ese prefijo puede colorearse con el color del shot
  usado en la fila.
- El resto del nombre mantiene el color base `#cccccc`.

---

## Columna Duration

Formato:

```text
484f - 20.2s
```

Debe usar el mismo color de frames/segundos que en la tabla Convert.

La duracion se calcula con:

- `frame_count` del job si existe.
- FPS del item si existe.
- Si no hay FPS confiable, mostrar solo frames.

---

## Columna Status

Estados:

| Estado logico | UI |
|---------------|----|
| running / starting | Barra de progreso identica a la tabla Convert |
| queued | `Queued #N`, mismo estilo que la tabla Convert |
| done | `DONE (Xs)`, verde como estado listo. El tiempo sale de `elapsed_seconds` emitido por el worker |
| running con skip pedido | `Skipping…`, ambar: el convert se esta cortando y los originales vuelven a su lugar |
| error | `Error`, rojo. Tooltip con el motivo del fallo (`error` del resultado) |
| skipped | `Skipped`, ambar (`Color.WARNING`): salteado a pedido, no es un error del transcode |
| cancelled | `Cancelled`, rojo |

La barra de progreso debe reutilizar la logica visual de la tabla Convert todo lo posible.

---

## Historial Visual

El manager global provee activo y pendientes. Para mostrar `DONE`, `Error`, `Skipped` y
`Cancelled`, la primera version puede mantener un historial visual dentro de la ventana UI.

Reglas:

- Los jobs activos y pendientes siempre vienen del snapshot del manager.
- Los completados se agregan al historial de la UI cuando llegan senales del manager.
- Cuando un job pasa a `DONE`, `Error`, `Skipped` o `Cancelled`, queda en la misma posicion visual
  en la que estaba; la tabla no mueve completados al final.
- `Clear Completed` borra solo ese historial visual.
- `Clear Completed` no modifica el manager ni la cola real.

---

## Botones Inferiores

```text
[Show All Import Windows] [Clear Completed] [Skip Current] CPU [High (6/6)]   ☐ Keep this window on top
```

El ancho minimo de la ventana sale del layout de esta fila (medido despues de
`apply_ui_font`): con un minimo fijo de 720 px el checkbox de la derecha quedaba cortado.

`Show All Import Windows`:

- Busca todas las ventanas abiertas de `Import Shot` por `objectName() == "LGA_ImportShotDialog"`.
- Las trae de vuelta a pantalla con `show()`.
- Si alguna esta minimizada, llama `showNormal()`.
- Luego llama `raise_()` y `activateWindow()`.

`Clear Completed`:

- Borra filas con estado `DONE`, `Error`, `Skipped` o `Cancelled`.
- No borra jobs activos ni pendientes.

`Skip Current`:

- Saltea el plate que se esta convirtiendo: llama a `manager.skip_active_job()`. El
  convert se corta con todos sus procesos hijos, los originales vuelven a su lugar y la
  cola sigue con el siguiente. Detalle en `LGA_import_shots_transcode_queue.md`,
  "Saltear el plate en curso".
- Habilitado solo si hay un job corriendo que todavia no se pidio saltear.
- Sin confirmacion: es reversible (el plate se puede volver a encolar).
- Tooltip en castellano, desde el diccionario `_TOOLTIPS` del modulo.

`CPU`:

- Dropdown global para bajar/subir consumo de CPU de los proximos plates.
- Opciones visibles: `High (6/6)`, `Medium (4/4)`, `Low (2/2)`, `Minimal (1/1)`.
- El primer numero es `workers` del manifest: cantidad de frames paralelos.
- El segundo numero es `exrmetrics_threads`: threads por proceso de `exrmetrics`.
- El valor es persistente entre sesiones.
- Si se cambia mientras un plate esta convirtiendo, no interrumpe ese proceso; aplica desde el proximo plate que arranque.
- Si hay jobs pendientes, el manager sobreescribe `workers` y `exrmetrics_threads` justo antes de lanzar cada worker, por lo que esos pendientes usan el preset nuevo cuando les llega el turno.

`Keep this window on top`:

- Persistente entre sesiones.
- Usa `QtCore.Qt.WindowStaysOnTopHint`.
- No debe volver modal la ventana.
- Texto visible: `Keep this window on top`.

Persistencia propuesta en `ImportShots.ini`:

```ini
[TranscodeQueueWindow]
keep_on_top = true
cpu_preset = High
```

---

## Recarga de Desarrollo

`LGA_import_shots.py` puede recargar este modulo durante desarrollo solo si no hay ventanas
vivas:

- No hay ventanas `Import Shot` visibles.
- No hay ventana `Import Shots - Transcode Queue` visible.

Si alguna existe, debe reutilizar el modulo ya cargado para evitar widgets creados por una
clase vieja, senales duplicadas o una ventana desconectada del manager actual.

---

## Referencias Tecnicas

| Archivo | Funciones / clases clave |
|---------|--------------------------|
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots.py` | `_make_footer_pair()`, `_focus_import_shot_window()`, boton `Open Queue` |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_transcode_queue.py` | `TranscodeQueueManager`, `snapshot()`, `skip_active_job()`, `queue_changed`, `sequence_started`, `sequence_done`, `job_cancelled` |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_transcode_queue.md` | Especificacion funcional de la cola global |
| `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_import_shots_transcode_queue_PLAN.md` | Plan de implementacion por etapas |
