> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

## Tab Transcode Plates

Conversion de EXR sequences. Muestra **todos** los plates de `_input/` (todas las versiones),
**independientemente** de lo marcado en el tab Import.

- Todos los EXR aparecen chequeados por defecto al abrir el tab.
- MOVs aparecen en la tabla con checkbox deshabilitado (`No soportado`).
- Solo opera sobre `exr_seq` con checkbox activo.
- Durante transcode activo (esta ventana): tabs Rename e Import quedan deshabilitados.
- Al terminar el transcode: tabs Rename e Import se marcan para refresh (`_needs_refresh`).

### Layout

```
┌─ EXR CONVERT ─────────────────────────────────────────┐
│  [⚠ avisos por MOVs excluidos]                        │
├───────────────────────────────────────────────────────┤
│  TABLA DE EXRs A CONVERTIR                            │
├───────────────────────────────────────────────────────┤
│  Codec / Calidad     │  Resolucion                    │
│  (col izquierda)     │  (col derecha)                 │
├───────────────────────────────────────────────────────┤
│  Manejo de originales                                 │
├───────────────────────────────────────────────────────┤
│  RESUMEN  (totales en disco)                          │
├───────────────────────────────────────────────────────┤
│  LOG (3 lineas, expandible ▲/▼)                       │
├───────────────────────────────────────────────────────┤
│  [Open Queue] [Shot Rename and Transcode tabs] [estado global]  [Start Transcode] │
└───────────────────────────────────────────────────────┘
```

### Tabla de EXRs a convertir

En la columna Nombre de esta tabla aplica el mismo coloreado de shotname que en la tabla
principal: si el nombre comienza con `shot_name` (case-sensitive), el prefijo se colorea
con `SHOTNAME_COLOR`. La celda pasa de `QTableWidgetItem` plano a `setCellWidget(_cell_html_label(...))`.

| Col | Contenido | Formato / color |
|-----|-----------|-----------------|
| (barra) | Color `#42616d` (plates) | 4 px, sin header |
| Nombre | Nombre de la secuencia | Prefijo = shotname → `SHOTNAME_COLOR`. Resto → `#cccccc` |
| Origen | `WxH (AR) (PAR) · bitdepth · Nch · compresion · #f - Xs` | AR dorado `#a89060`, PAR rosa `#c4787a` entre paréntesis, comp coloreada, count+secs ámbar `#b09040`. Ancho: 400 px |
| → | Flecha separadora | centrada, `#666` |
| Destino | `WxH (AR) (PAR) · bitdepth · Nch · compresion` | mismo coloring; PAR destino = `(1)` si desanamorfizar activo, sino mismo PAR fuente; `—` gris oscuro si checkbox off |
| Tamaño | Tamaño actual en disco | escaneado al abrir la pagina (`_folder_size_bytes`) |
| Estado | `Pendiente` / `Queued #N` / `⚠ Upscale` / `—` / barra de progreso / `DONE (Xs)` / `✗ Error` | ancho fijo 130px. Ver detalle abajo. |

**Estados de la columna Estado:**

| Estado | Descripción | Color/widget |
|--------|-------------|--------------|
| `Pendiente` | EXR chequeado, listo para convertir | cian `#5a9ab5` |
| `Queued #N` | Job pendiente en la cola global | cian `#5a9ab5` |
| `⚠ Upscale` | Resize bloqueado por "no upscale" | rojo `#a06060` |
| `—` | Checkbox desactivado (fila no se convertirá) | gris oscuro `#444444` |
| Barra de progreso | Convirtiendo — polling QTimer cada 300ms de archivos en dst | fondo vacío `#393959`, relleno `#443a91`, texto `#cccccc`, bordes redondeados |
| `DONE (Xs)` | Conversión completada exitosamente con segundos reales | verde `#6a9960` |
| `✗ Error` | Conversión fallida | rojo `#a06060` |

La columna Destino y la columna Estado se recalculan en vivo cuando cambian:
DWAA on/off, channels, preset de resolucion, custom W×H, preserve AR, match_dim,
desanamorfizado, forzar pares, **checkbox de la fila**.

**Interacción con la tabla:**
- **Click simple** en cualquier columna (excepto col 0/1): activa/desactiva el checkbox de la fila.
- **Shift+click** en una fila o checkbox: deja checked solo esa fila y deselecciona las demas filas habilitadas.
- **Doble click**: restaura el checkbox a su estado previo (cancela el toggle del primer click) y abre la carpeta del plate en el explorador del sistema (Windows: `os.startfile`; macOS: `open`).

**Upscale bloqueado:** la tool nunca permite upscale. Cuando el preset elegido
resultaría en una resolución mayor que el origen, se mantiene la resolución original,
la fila muestra `⚠ Upscale` en rojo y la columna Destino se grísea.

El bit depth y channels se leen via `oiiotool --info -v` parseando la linea
`"WxH, N channel, half openexr"` y se guardan en cada item como `bitdepth` y
`channels` (int) en `_scan_input_folder()` y `_scan_publish_folders()`.

### Opciones — Codec / Calidad (columna izquierda)

| Control | Default | Notas |
|---------|---------|-------|
| ☑ Convertir a DWAA + `compression 45` | on | Si off, mantiene compresion original. Si on, siempre usa DWAA con compression fija `45`. |
| Channels (`QComboBox`) | `Mantener` | `Mantener` o `Reducir a RGB` (elimina canal alpha; pasa `channels: "rgb"` al manifest) |

> Los valores editables de Codec / Calidad son **persistentes**: se guardan en el INI al cambiar
> y se restauran en la próxima apertura de la herramienta.

### Opciones — Resolucion (columna derecha)

| Control | Default | Notas |
|---------|---------|-------|
| Destino (`QComboBox`) | `Original` | Presets cargados desde INI. Secciones `[AR]` en dorado. Ícono 🗑 a la derecha solo en presets borrables (excluye siempre `Original`, `Timeline ...` y `Custom...`, incluso cuando `Original` muestra AR). Click en ícono borra el preset del INI. Presets por defecto: `Original`, `Timeline  WxH  [AR]` (resolución del timeline activo), `2K — 2048×1152 [16:9]`, `UHD — 3840×2160 [16:9]`, `4K — 4096×2304 [16:9]`, `Custom...`. Con source disponible: muestra `→ WxH [AR_real]` calculado según PAR y match_dim |
| Custom W × H + `[Save preset]` | `2048 × 1152` | Solo visible si preset = `Custom...`. Spinboxes de 88 px de ancho (suficiente para mostrar 4 dígitos completos). El botón "Save preset" usa estilo `_BTN_SMALL` (igual que los botones de selección rápida). Abre un diálogo para nombrar y guardar el preset al INI. |
| ☑ Preserve aspect ratio | on | Comparte fila con **Dimensión que manda**. Si el usuario re-activa este checkbox estando en `Custom...` con W/H arbitrarios, se corrige automáticamente la dimensión derivada según match_dim. |
| Dimensión que manda | `Match target width` | Visible cuando Preserve AR está activo (también en `Custom...`). Define qué eje se conserva y cuál se recalcula para mantener AR. |
| ☑ Desanamorfizar (Pixel Aspect Ratio) + PAR fuente | off + `2.0` | El combo `PAR fuente` (`1.3`, `1.5`, `1.8`, `2.0`) aparece inline, a la derecha del checkbox. Si está activo: ancho destino = `target_w × PAR`, `PixelAspectRatio` de salida se fuerza a `1.0` en el manifest y la columna Destino muestra PAR `(1)`. |
| ☑ Forzar dimensiones pares (recomendado) | on | Si el resultado final tiene ancho/alto impar, resta 1 px en esa dimensión (ej: `4139×1280` → `4138×1280`). Se aplica en preview y en el cálculo final de transcode. |
| Filtro resampling | `lanczos3` | `cubic`, `box` (solo aplica si hay resize) |
> **HDR-safe resize automático:** cuando hay resize activo, `LGA_EXR_Convert.py` aplica
> automáticamente `--rangecompress → --resize:highlightcomp=1 → --rangeexpand` (Opción A,
> probada 2026-05-08). Esto evita pixeles negativos en zonas de alto contraste (ringing
> de filtro en material HDR lineal). No requiere configuración — se activa solo.
> Detalle completo: `LGA_NKS_Shared/LGA_EXR_Convert_HDR_Resize.md`

> Todos los valores de Resolución son **persistentes**: se guardan en el INI al cambiar
> y se restauran en la próxima apertura.

#### Presets de resolución — formato INI

Los presets se almacenan en secciones `[ResPreset_N]` del mismo INI (`ImportShots.ini`):

```ini
[ResPreset_0]
name = Original
special = original

[ResPreset_1]
name = 2K — 2048×1152
w = 2048
h = 1152

[ResPreset_4]
name = Custom...
special = custom
```

- `special = original` → mantiene resolución fuente  
- `special = custom` → muestra spinboxes  
- `w` + `h` → preset fijo (permite trash icon y borrado)  
- Los presets `original` y `custom` son invariables (sin trash icon)

#### Lógica Custom + Preserve AR (con match_dim visible)

```
_custom_ar_updating: bool  — flag para evitar recursión en valueChanged

_on_keep_ar_changed() con preset=custom, al pasar OFF→ON:
    ajusta automáticamente la dimensión derivada según match_dim

_on_custom_w_changed() / _on_custom_h_changed() con preserve on:
    sincroniza W/H usando match_dim:
      - Match target width  → H = round(W * src_h/src_w)
      - Match target height → W = round(H * src_w/src_h)

_current_target_res(src_w, src_h) con preset=custom y preserve on:
    aplica la misma regla de match_dim por ítem (mantiene AR source)

post-proceso de resolución final (preview + run):
    1) check de upscale (si corresponde, vuelve a source)
    2) desanamorfizado (si está activo)
    3) forzar dimensiones pares (si está activo)
```

### Opciones — Manejo de originales (fila inferior)

| Control | Default | Notas |
|---------|---------|-------|
| ☑ Borrar `/Originals` al terminar | off | Los originales **siempre** se mueven a `_input/Originals/<plate>/` antes del transcode. Este checkbox solo controla si se borran al finalizar exitosamente. Tooltip explica el comportamiento al hacer hover. |

> El valor de "Borrar /Originals" es **persistente** (se guarda en el INI).
> Con `Transcode_TEST_Mode = True`, el checkbox queda deshabilitado y los originales no se mueven.

Cuando el flag global `Transcode_TEST_Mode = True` está activo (actualmente `False`):
- Aparece un aviso `🧪 TEST MODE` en la sección.
- El checkbox queda deshabilitado.
- El output del transcode se escribe en `{seq_path}/test_transcode/` sin mover nada.

#### Estructura de Originals (cuando `move_originals = True`)

Los originales se mueven a una subcarpeta dentro de `_input/Originals/`:

```
_input/
├── aPlate_v01/          ← item_path (dst del transcode — recibe los convertidos)
│   └── *.exr            ← EXRs convertidos
└── Originals/
    └── aPlate_v01/      ← originals_dir (item_path.parent / "Originals" / item_path.name)
        └── *.exr        ← EXRs originales movidos aquí antes del transcode
```

- Si hay varios plates, cada uno tiene su propia subcarpeta en `_input/Originals/`.
- Si `Borrar /Originals al terminar` está activo: se borra `_input/Originals/<plate>/`
  y, si la carpeta `_input/Originals/` queda vacía, también se borra.
- En caso de fallo del transcode, los EXRs originales se restauran a `item_path`.

#### Re-transcode / overwrite con Originals existente

Si `_input/Originals/<plate>/` ya existe, se considera un transcode anterior. Al elegir
`Sobreescribir`, la herramienta no debe borrar esos EXR originales. El flujo correcto es:

1. Borrar los EXR convertidos que quedaron en `item_path`.
2. Mover los EXR de `_input/Originals/<plate>/` de vuelta a `item_path`.
3. Eliminar la carpeta `_input/Originals/<plate>/` ya vacia.
4. Arrancar `TranscodeWorker`, que volvera a mover los EXR de `item_path` a
   `_input/Originals/<plate>/` y generara los nuevos convertidos.

Si `_input/Originals/<plate>/` existe pero esta vacia, se elimina esa carpeta y se conservan
los EXR actuales de `item_path` como unica fuente disponible para el re-transcode.

#### Protecciones contra perdida de plates

El transcode nunca debe dejar un plate sin EXR fuente recuperable. Antes de tocar archivos
en `item_path` o `_input/Originals/<plate>/`, la herramienta debe aplicar estas guardas:

- Hacer un preflight por job con conteo de EXR en `item_path` y en
  `_input/Originals/<plate>/`. (implementado y testeado en Hiero)
- Si ambos conteos son `0`, abortar el job antes de borrar o mover archivos y registrar el
  error con paths absolutos. (implementado y testeado en Hiero)
- No borrar nunca la ultima copia conocida de EXR: si solo existe una fuente valida, primero
  debe quedar confirmada otra copia o destino valido antes de eliminarla. (implementado y testeado en Hiero)
- En re-transcode con `Originals` existente, restaurar primero los EXR de
  `_input/Originals/<plate>/` a `item_path` y verificar que `item_path` vuelve a tener frames
  antes de eliminar la carpeta `Originals/<plate>`. (implementado y testeado en Hiero)
- Antes de borrar outputs convertidos en `item_path`, confirmar que existe una fuente segura
  en `_input/Originals/<plate>/` o que `item_path` conserva EXR fuente que no seran tocados.
  (implementado y testeado en Hiero)
- Si `Borrar /Originals al terminar` esta activo, borrar `Originals/<plate>` solo despues de
  validar que el transcode termino OK y que el output final tiene EXR. (implementado y testeado en Hiero)
- Validar rutas antes de cualquier `rmtree`: la ruta resuelta debe estar dentro de
  `_input/Originals/<plate>/` o del output esperado del job, nunca en `_input`, en el shot root
  ni en una carpeta comun. (implementado y testeado en Hiero)
- Si falla una restauracion, move o delete parcial, abortar el job, registrar conteos antes y
  despues, y no continuar con el siguiente paso destructivo. (implementado y testeado en Hiero)
- Guardar en el log una linea de snapshot por job con `item_path`, `originals_dir`,
  `item_exr_count`, `originals_exr_count`, accion elegida y resultado. (implementado y testeado en Hiero)

#### Borrado honesto y enlaces (transcode v1.02)

- `_safe_rmtree` ya no acepta `ignore_errors`. Devuelve la lista de lo que NO se pudo borrar
  (un archivo abierto por otro proceso, por ejemplo) y el log solo dice "eliminado
  (verificado)" si la carpeta ya no esta en disco. Si queda algo, lo nombra.
- Si hay un junction o symlink en el camino o en cualquier nivel del arbol, no se borra
  NADA. Ojo: `os.path.islink()` da False para un junction de Windows; se mira el atributo de
  reparse point. Detalle en `docs/Docu_Borrado_Seguro.md`.
- **Excepcion deliberada a "abortar el job":** el borrado de `Originals/<plate>` o
  `_tc_temp_src` DESPUES de un transcode OK nunca levanta excepcion
  (`_cleanup_after_success`). Si levantara, el `except` del worker llamaria a
  `_restore_exrs`, que borra todos los EXR convertidos y restaura solo los originales que
  quedaron: se perderian las dos cosas. Se informa con una linea `⚠` y se deja todo como esta.

#### Move y restore sin perdida (transcode v1.03)

- `_move_one_exr`: `os.rename` en el mismo disco; si falla, levanta y el EXR sigue entero en
  el origen (antes caia a `shutil.move`, que copia). Entre discos: copiar, verificar tamano y
  recien ahi borrar el origen. Nunca pisa un destino existente.
- `_restore_exrs` solo borra de `item_path` los EXR que tienen su original con el mismo nombre
  en la carpeta de origen. Antes borraba todo `*.exr`: si el move se habia cortado a mitad, se
  llevaba los originales que todavia no se habian movido.
- El overwrite (`delete_existing_outputs`, modo Originals) aborta sin borrar nada si algun EXR
  de `item_path` no tiene su original en `Originals/<plate>`. El caso real: un borrado anterior
  que quedo a medias por un original bloqueado deja 1 EXR de 5 en Originals.

#### Plate re-entregado: el overwrite solo restaura lo que puede demostrar (transcode v1.04)

- Un transcode OK que conserva `Originals/<plate>` deja ahi `.lga_transcode_outputs.json`: nombre,
  tamano y `mtime_ns` de cada EXR convertido que escribio en el plate.
- El overwrite solo restaura `Originals/<plate>` encima del plate si TODOS los EXR actuales
  coinciden con ese registro. Si falta el registro (transcode de una version anterior) o algo no
  coincide (llego un plate nuevo con los mismos nombres), aborta sin borrar y explica en ingles
  que hacer. Antes, un plate re-entregado se reemplazaba por el viejo.
- Por que ese criterio: la compresion o los metadatos no distinguen un convertido de un EXR de
  camara (tambien puede venir en DWAA), y el tamano solo no alcanza (un plate sin comprimir de la
  misma resolucion pesa igual). Un falso negativo solo lleva a no restaurar.
- El dialogo de overwrite ya dice que va a pasar: que se borran los convertidos, o que se va a
  rechazar.
- Modo sin Originals: si `_tc_temp_src` tiene EXR, son los originales de un transcode
  interrumpido. El overwrite ya no lo borra: aborta y explica como devolverlos a mano.

### Solución QSpinBox — `_ArrowSpinBox` (ganadora, implementada)

Clase de módulo definida en `LGA_import_shots.py` (junto a `_ArrowComboBox`).
Usada en los spinboxes W y H del panel Custom de resolución.

**Ronda 1 FALLADA**: CSS triangle, `subcontrol-origin:border/padding`, arrows nativos del SO
→ flechas invisibles en este build.

**Ronda 2 ganadora**: Subclase con `paintEvent` (Opción 7) — mismo patrón que `_ArrowComboBox`.
Opciones 5 (▲▼ externos) y 6 ([−] valor [+]) también funcionales como workaround.

Ver receta completa en `docs/Docu_PySide_UI_Aprendizajes.md — SpinBox`.

### Resumen

Una linea de texto sobre el log con totales (sin estimaciones):

```
3 secuencias · 1842 frames · 14.21 GB en disco
```

### Botones inferiores

| Boton | Estilo | Habilitado | Accion |
|-------|--------|------------|--------|
| Go Back | `_BTN_SECONDARY` | deshabilitado mientras hay jobs activos o en cola para esta ventana | vuelve a `PAGE_MEDIA` (preserva opciones) |
| Start Transcode | `_BTN_PRIMARY` | cuando hay ≥1 EXR chequeado | llama a `_run_transcode()` → lanza `TranscodeWorker` via `QThreadPool` |

**Comportamiento del boton "Go Back" durante transcode:**

- Al arrancar `_run_transcode()`: se deshabilita y su texto cambia a `"Transcoding, wait..."`.
- Al finalizar toda la cola (`_finalize_transcode()`): se re-habilita y vuelve a `"Go Back"`.
- El path de error fatal (`_on_transcode_error`) tambien llama a `_finalize_transcode`, asi que el restore cubre ese caso.
- El boton no tiene flecha (`←`); ninguno de los botones "Go Back" del dialogo la tiene.

### Log panel

3 lineas visibles, expandible con boton ▲/▼ a `setMaximumHeight(16777215)`.

> **Estado actual:** Implementado. El transcode corre via `LGA_EXR_Convert.py`
> (manifest JSON + subprocess) en un `QRunnable` separado para no bloquear la UI.
> El consumo de CPU se controla desde la ventana `Import Shots - Transcode Queue`
> mediante presets globales que escriben `workers` y `exrmetrics_threads` en el manifest.

### Robustez ante frames colgados (timeout adaptativo)

Si un proceso `oiiotool`/`exrmetrics` se cuelga convirtiendo un frame (EXR corrupto,
stall de I/O en disco de red, etc.), antes el worker quedaba esperando ese frame
para siempre y bloqueaba toda la cola. `LGA_NKS_Shared/LGA_EXR_Convert.py` ahora
aplica un timeout por frame:

- Durante un *warmup* de los primeros `5` frames OK se usa un timeout amplio
  (`120s`). Con esas muestras se fija un **timeout adaptativo** =
  `max(15s, tiempo_tipico x 20)` (mediana del warmup). Asi un frame
  legitimamente lento nunca se mata, pero un cuelgue real se detecta.
- Si un frame supera el timeout, el proceso se mata y el frame se **reintenta
  hasta `3` veces**.
- Si agota los reintentos, el frame se marca como error y la conversion termina
  reportando el fallo (`report["error"]`) en vez de quedar colgada.
- El timeout adaptativo calculado y los eventos de timeout/reintento se loguean
  en `logs/debugPy_EXRConvert.log`.

> Nota: la tool original de Hiero solo hace `EXR -> EXR`. El pipeline `MOV` y la
> flag de debug `transcode_timeout` existen unicamente en la app `MediaTools`.
