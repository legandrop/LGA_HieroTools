# LGA_BurnIn — soft effect de burn-in con metadata del clip visible

> Estado (12 nov 2026): **panel Burn-ins con mapa**, el diseno del menu
> Burn-ins de Shot Player (LGA Media Tools). La tabla X / Y / Size por campo
> se reemplazo por un mapa de ocho lugares con cinco distribuciones; todo el
> look es global. Once campos (suma Track, Date y Codec), fondo Panels /
> Band / Text, costados girados. Validado en NKS 17.0v4 por dev-link
> (render a archivo y panel real) y con el harness. La version anterior
> (LGA_BurnIn_v0, solo Text2) se borro el 12-11-2026: no se registra mas y su
> gizmo no existe. Un proyecto viejo que la use la muestra como efecto
> desconocido.

## Que es

Un unico soft effect para el timeline de Hiero/Nuke Studio (NKS) que
reemplaza la pila de soft effects Text con metadata. Es un **gizmo**
registrado en el menu Effects que muestra datos del **clip visible**
(respeta tracks prendidos/apagados) sobre **paneles redondeados** dibujados
en GPU por un kernel BlinkScript propio, y pinta en **rojo** lo que no
coincide con el objetivo del proyecto.

## Campos

| Campo | Contenido | Rojo condicional |
|---|---|---|
| Clip | `hiero/clip` | no |
| Colorspace | `sourceMediaColourTransform()` del clip (por API + cache; no viaja en la metadata del stream) | no |
| Res | `input/width` x `input/height` | si: difiere del objetivo. **Solo compara plates** (`compare_res_exts`, default `exr`) |
| Frame | `Frame: <input/frame>` | no |
| TC | `TC: <input/timecode>` | si: difiere del TC del clip del track **aPlate** en ese frame (`timecodeStart` + `sourceIn` + offset, items cacheados 3 s). Sin timecode en la metadata (comp sin TC) o sin aPlate en el frame, no compara |
| FPS | `input/frame_rate` | si: difiere del objetivo |
| Track | `Track: <nombre>`: el track del clip visible. Por API (`hiero/track` llega vacio en el stream, medido): el track item de la secuencia activa cuya fuente es el clip y cubre el frame, de arriba abajo; cache de 1,5 s | no |
| Date | fecha de modificacion del archivo visible (`input/mtime`, `AAAA-MM-DD`), no la del dia: decision de Lega (12-11-2026) | no |
| Codec | EXR: `exr/compressionName` con el nivel si es DWA (`DWAA 60`); otra media: la primera key de metadata que nombre un codec | no |
| Custom 1 / 2 | texto libre (`bi_custom1_text`, `bi_custom2_text`) | no |

Objetivos: `res_target` y `fps_target` — `"timeline"` (formato/fps de la
secuencia) o explicitos (`"3840x2160"`, `24`). **Labels** (`bi_labels`)
prende o apaga el prefijo `Frame:`, `TC:` y `Track:`.

## Default de fabrica

Lo que trae un efecto recien agregado es el default que Lega armo para
distribuir (12-11-2026): **Bottom line** con Clip abajo a la izquierda,
`FPS Res` abajo al centro, Codec y Colorspace abajo a la derecha, y TC y
Frame arriba a la derecha; fondo Panels al 79%, radio 29, Labels apagados,
Inter SemiBold, Size M. Vive en el codigo, no en la maquina de nadie:

- la distribucion, en `_PRESET_SLOTS["bottom"]` y `DEFAULT_PRESET` de
  `LGA_NKS_BurnIn_Layout` (tambien es lo que devuelve Reset);
- los valores del look, en el generador del gizmo
  (`gen_LGA_BurnIn_gizmo.py`, que se regenera) y en `_SLIDERS` del panel
  (el click en el rotulo de un slider vuelve a ese valor).

Para cambiarlo: armar el efecto en NKS, guardar el proyecto, leer del
`.hrox` el bloque `LGA_BurnIn { ... }` (knobs `bi_*` y `bi_layout`) y pasar
esos valores a los tres lugares.

## Layout: el mapa

Lo que antes era un ancla X / Y por campo ahora es un **mapa**: ocho
lugares (cuatro esquinas, arriba y abajo al centro, los dos costados) y la
bandeja **Hidden**. Cada lugar es una lista de LINEAS de arriba abajo, y
cada linea una lista de campos de izquierda a derecha. Hay cinco
distribuciones (Corners, Top & bottom, Bottom line, Edge, Left list) y cada
una recuerda como la dejo el usuario. Todo viaja como JSON en el knob
invisible `bi_layout` (modelo en `LGA_NKS_BurnIn_Layout`).

**Por que:** la tabla obligaba a pensar en fracciones del formato y el ancho
de cada texto cambia de clip a clip, asi que dos campos "en la misma linea"
se pisaban o quedaban separados segun el clip. El mapa describe la
intencion (este campo abajo a la derecha, junto a este otro) y el render la
resuelve en pixeles en cada frame.

- **Geometria en render**: `field_geo(field, comp)` de la logica calcula el
  layout entero (`Layout.compute`) con los anchos medidos de los textos y lo
  cachea por (efecto, frame, estado). Los paneles del kernel y las cajas de
  los Text2 leen lo mismo, asi que el fondo no se separa del texto.
- **Solo se cachea con stream**: fuera del render (un `setValue`, el
  onCreate) el Input no tiene metadata y todos los textos dan vacio; ese
  layout vacio quedaba guardado y el render lo reusaba (todo apilado en el
  origen, medido).
- **Los paneles abrazan al texto**: el ancho se mide con el TTF real de
  Inter que usa Nuke; frame y TC con los digitos normalizados a "0" (el
  layout no "respira" entre frames). Un campo sin texto no ocupa lugar.
- **Tamano global**: Size S / M / L es una fraccion del alto del formato
  (`SIZE_FRACTIONS`; M = 50 px en 4K, el tamano historico).
- **Costados girados** (Sides = Rotated, default en Edge): el izquierdo gira
  90 (se lee de abajo arriba) y el derecho 270. El pivote es FIJO por
  costado (`Layout.side_pivot`): sale del formato del timeline, del tamano y
  del padding, no del ancho del texto. Lo escribe `apply_rotation` en
  `bi_<f>_ax/ay`, y lo leen el kernel y el blob del Text2.
- **Fondo** (`bi_bg_mode`): Panels (uno por campo), Band (una franja de lado
  a lado en cada borde usado: `field_geo('_band', t/b/l/r)`) o Text (sin
  fondo, con la sombra de los Text2).

## Mascara del viewer

Con una mascara en el viewer (cualquier aspect, elegida desde el menu del
viewer o con el boton del panel Viewer | TL), los burn-ins se corren hacia
adentro para quedar en el area visible. Cuenta tambien la mascara al 50%
(Half): ya los tapa a medias.

- **Deteccion**: `viewer_mask_aspect()` (Blink) lee `maskOverlayStyle()`,
  `maskOverlayName()` (`"3:2"`, `"2.35:1"`) y `overlaysShown()`. Ojo: el
  nombre queda puesto aunque el estilo sea None (medido en NKS 17), por eso
  manda el estilo.
- **Vigia**: un QTimer de 500 ms en el hilo principal (`_mask_tick` del
  registro). La mascara no tiene evento de hiero y el viewer se recrea al
  cambiar de timeline, asi que no alcanza con conectarse a sus senales. Solo
  cuando cambia el aspect o la secuencia activa recorre los LGA_BurnIn de la
  secuencia y escribe `bi_mask_aspect` (`apply_mask`). Un efecto nuevo toma
  la mascara en su onCreate (`setup`).
- **Layout**: `Layout.mask_inset(aspect, W, H)` da lo que tapa cada barra
  (3:2 en 3840x2160: 300 px por costado; 2.35:1: 263 px arriba y abajo) y
  `compute(..., inset=)` ubica todo dentro de lo visible. Las franjas de Band
  suman la barra a su grosor; el pivote de los costados girados tambien.
- El boton viejo (`LGA_NKS_Viewer_Mask`) sigue moviendo los Text del track
  BurnIn con su `box`; a LGA_BurnIn no lo toca (no tiene `box`).

## Arquitectura del gizmo

```
Input -> Dot -> Crop_Format -> BlinkScript (Blink_Panels) -> 11x Text2 -> Output
```

**Fuente**: es **Inter**, fija (la del pack); el usuario elige solo el PESO
(Regular/SemiBold/Bold via `bi_weight`, que setea el `bi_font` invisible por
`apply_font()`). Para no depender de que Inter este instalada en la maquina,
el startup (`LGA_HieroTools_Startup.py`) antepone el fonts dir del repo
(`LGA_NKS_Shared/fonts/`, con los tres pesos) a `NUKE_FONT_PATH`, que Nuke
lee al escanear las fuentes (una vez, al arrancar; no en runtime). Asi Nuke
descubre el Inter del repo —incluido Bold, que el Inter de Windows no trae—
sin instalar nada. Al cambiar el peso, el fondo se recalcula (mide con el
TTF del peso nuevo).

- **Crop_Format**: Crop al formato (`box 0 0 width height`, `intersect`
  apagado) para que el bbox que ve el kernel sea EXACTAMENTE el formato. Sin
  el, con un clip reformateado que no llena justo el cuadro (1920x1080 en una
  secuencia 4094x2160 escalado al ancho: bbox de -74 a 2234) el kernel
  reparte sus coordenadas sobre el bbox y los paneles salian estirados en
  vertical respecto del texto (arriba pegados al borde, abajo corridos hacia
  abajo). Detalle en `Docu_SoftEffects_Aprendizajes.md`.
- **Blink_Panels**: kernel `LGA_RoundedPanels.blink` (SDF de rounded box,
  antialiasing 1px, los 11 paneles y las 4 franjas de Band en UNA pasada,
  params solo float; x/y/w/h atados a `field_geo()`). Desde v0.08 un
  `init()` precalcula por panel seno, coseno, centro, radio y la caja ya
  girada, y `process()` solo hace la SDF dentro de esas cajas (el resto del
  cuadro copia la entrada). Es el UNICO nodo que puede dibujar los paneles:
  ver "Rendimiento" abajo. Su
  `onCreate` llama a `LGA_NKS_BurnIn_Blink.setup()`, que compila el kernel
  via `kernelSourceFile` + Load (la unica via que compila por script en el
  timeline) y ata cada parametro a los knobs del gizmo padre por expresion
  (los knobs del kernel recien existen tras compilar, prefijados con el
  nombre del kernel).
- **Text2 x11** (9 de metadata + custom1/custom2): anatomia calcada del
  BurnIn nativo (blobs de estado incluidos — sin ellos el GPU los dibuja en
  el origen). Cada message llama a `LGA_NKS_BurnIn_Logic.bi_text()` con
  `[frame]`; res y fps llevan el color condicional via `bi_ok()` en los
  canales g/b. El texto se centra verticalmente dentro de su panel
  (`yjustify center`) con `text padding`. La caja de cada Text2 usa tres
  llamadas a `field_geo` (x, y, y2; el borde derecho es `width*3`) y suma
  `0*parent.bi_rev`, para que `nudge()` la haga re-evaluar.
- El gizmo se REGENERA con
  `+Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py` (tabla de layout +
  kernel + plantilla Text2). No editar el `.gizmo` a mano.

## Archivos

```
LGA_HieroTools/
  LGA_NKS_BurnIn.py                registro de LGA_BurnIn + eventos + vigia de mascara
  LGA_NKS_BurnIn_py/
    LGA_BurnIn.gizmo               el efecto (generado)
    LGA_RoundedPanels.blink        kernel de los paneles (produccion)
    LGA_RoundedPanel.blink         kernel de UN panel (sonda historica)
    LGA_NKS_BurnIn_Blink.py        setup del BlinkScript (compilar + atar params)
    LGA_NKS_BurnIn_Logic.py        textos, comparaciones, geometria en render
    LGA_NKS_BurnIn_Layout.py       modelo del mapa (Python puro, sin Nuke ni Qt)
    LGA_NKS_BurnIn_Config.py       capa pura de config (testeable sin Nuke)
    LGA_NKS_BurnIn_ProjectTag.py   override que viaja en el .hrox (tag)
    LGA_NKS_BurnIn_Panel.py        ventana Burn-ins (mapa + look)
    logs/DebugPy_LGA_NKS_BurnIn.log
  +Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py   generador (dev)
  +Building_Blocks/BurnIn/design/BurnIn_Panel_Mapa.html  mockup aprobado
  +Building_Blocks/UI_Capture/fixtures/h3_burnin_panel.py  fixture del harness
```

## Panel Burn-ins (Open Burn-in Panel)

El properties del gizmo quedo **pelado a un solo boton**, **Open Burn-in
Panel**; todo se edita en la ventana **Burn-ins** (`LGA_NKS_BurnIn_Panel`,
`Style.FORM`, captura en `UI_Captures/BurnIn_Panel.png`). Mockup aprobado
en `+Building_Blocks/BurnIn/design/BurnIn_Panel_Mapa.html`.

- **Presets**: las cinco distribuciones en un segmentado, y **Reset** vuelve
  la activa a la de fabrica (deshabilitado si ya lo esta).
- **Mapa** (`BurnInMap`, pintado con QPainter y tokens del modulo de
  estilo): se arrastra un campo a un lugar, o click en el campo y despues en
  el lugar. Soltarlo al costado de otro lo pone en la misma linea; arriba o
  abajo, en una linea nueva (el lado sale de la posicion relativa al centro
  del chip, normalizada por su medio ancho y medio alto, como Shot Player).
  En **Hidden** se oculta. Res, FPS y TC llevan un punto rojo si no coinciden.
- **Custom 1 / 2**: una fila de texto fija cada uno. Escribir en un Custom
  oculto lo muestra abajo al centro.
- **Look** (global, para todos los campos): Background Panels / Band / Text,
  Bg opacity, Text opacity, Size S / M / L, Labels, Weight (Inter Regular /
  SemiBold / Bold), Stack Row / Column, Sides Upright / Rotated, colores,
  Radius y Padding. Los sliders son de marcas (`TickSlider`, el de Shot
  Player): solo pintan al cambiar el valor o el hover, no consumen nada en
  reposo. Click en el rotulo vuelve al default.
- **Saved presets**: guardan mapa, look y textos con nombre en el
  BurnIn.json de AppData (formato `v: 3`). Un preset de la version con
  tabla (v2) aplica su estilo; sus x / y por campo se ignoran.
- **Project targets**: Save to Project escribe el tag `LGA_BurnIn_Settings`
  en el `tagsBin()` (key `tag.lga_burnin_config`), que viaja dentro del
  `.hrox` (Clean Project no toca tags; hay que guardar el proyecto). Save as
  Defaults escribe `%APPDATA%\LGA\HieroTools\BurnIn.json` (**no se
  versiona**: mapea nombres reales de proyectos; ejemplos siempre con
  `PROJA`). Despues de guardar, la ventana NUDGEA el efecto: el timeline no
  re-evalua las expresiones de color hasta que el nodo se ensucia (medido).
- **Keep on top** (default ON) abajo a la izquierda.

Lo que se saco a pedido de Lega: el switch de prender / apagar (en NKS el
efecto se apaga desde el timeline), la seleccion multiple y los ajustes por
campo (tamano, fondo, giro y offset son globales).

Si el boton no dispara en el panel del timeline, la ventana se abre desde
el Script Editor con `__import__('LGA_NKS_BurnIn_Panel').show_panel()`.

## Config en dos capas

1. Usuario — `BurnIn.json` en AppData: `{"default": {...}, "projects":
   {"PROJA": {...}}}`; las keys de `projects` son PREFIJOS del nombre de
   proyecto (gana el mas largo).
2. Proyecto — el tag de arriba; pisa a la capa de usuario.

Cache por proyecto en la logica; se invalida en load/save/close de proyecto
y al cambiar el mtime del JSON.

## Rendimiento (medido 2026-11-14, NKS 17.0v4)

Toda la logica de Python lee de UN estado por frame
(`LGA_NKS_BurnIn_Logic._frame_state`): la metadata se pide una vez al Input,
los textos se miden una vez y el layout se calcula una vez; las ~60
expresiones del gizmo (cajas, params del kernel, mensajes, colores) solo
leen de ahi. El panel y el knobChanged piden la actualizacion a
`LGA_NKS_BurnIn_Blink.schedule_update`, que junta todo lo de un ciclo de
eventos en una sola por efecto, y `nudge()` escribe un solo knob.

Numeros (CPU del proceso, instancia aparte):

| Caso | CPU |
|---|---|
| Recorrer el timeline, efecto apagado | ~1 ms por frame |
| Recorrer el timeline, efecto prendido (publicado v4.026 o actual) | ~18 ms por frame |
| Python del efecto en un proyecto real (cientos de clips) | ~10 ms por frame |
| Abrir el panel | 77 ms, sin escribir ningun knob |
| Panel abierto y quieto | ~5 ms por segundo |
| Un movimiento de slider (cualquier soft effect, incluido el BurnIn nativo) | ~130-170 ms |

El costo de un movimiento de slider es NKS re-renderizando tras el cambio
de knob: el BurnIn nativo cuesta lo mismo. Varios writes en el mismo ciclo
de eventos se juntan en un solo re-render.

**Lo que NO funciona, medido:** reemplazar el BlinkScript por nodos nativos
(Crop + Expression + Merge, o Rectangle). En un render offline
(`Read -> gizmo -> Write`) da bien y hasta mas barato, pero en el timeline
esos nodos no dibujan nada (solo corren los nodos con motor de soft effect)
y tres o mas Merge2 encadenados tiran NKS 17. Detalle en
`Docu_SoftEffects_Aprendizajes.md`. Por eso el banco offline NO sirve para
decidir el diseno: todo cambio de estructura se valida mirando el visor del
timeline.

## Limitaciones conocidas

- Un burn-in por vez en la ventana: edita el primer efecto LGA_BurnIn que
  encuentra en la secuencia activa (boton Refresh para re-buscar).
- El colorspace se cachea por clip; un cambio a mano se refleja al
  guardar/reabrir el proyecto.
- Comparacion de resolucion solo para plates (EXR por default).
- El kernel es una pasada full-frame por instancia. En el timeline corre en
  GPU y cuesta poco; fuera del timeline (render offline en CPU) el
  BlinkScript tiene un costo fijo de ~40-70 ms por frame que no depende de
  lo que calcule adentro (medido: v0.06 y v0.08 dan lo mismo ahi).
- **Costados girados**: el pivote sale del formato de la secuencia que
  contiene el efecto (`_timeline_format`: la activa si lo contiene, si no la
  primera que lo contenga). Una secuencia sin formato da 0x0 (medido en una
  secuencia vacia) y se descarta: con 0x0 el pivote quedaba en (9.6, 9.6) y
  los campos girados fuera del cuadro. Mecanismo del giro en
  `Docu_SoftEffects_Aprendizajes.md`.
- **Leer knobs de texto con `getText()`**: `value()` de un String_Knob
  evalua los corchetes como TCL; con el JSON del mapa devuelve
  `missing close-bracket` (medido).
- **Refresco del viewer**: el efecto no fuerza ningun refresh; el cambio de un
  knob ya re-renderiza el frame. Nunca usar `Viewer.flushCache()`: pausa el
  cacheo en diferido y el viewer deja de dibujar frames al mover el playhead
  (era el cuelgue al agregar el efecto, hasta v1.04 de `LGA_NKS_BurnIn`).

## Pendientes

- Aplicar defaults de config a instancias nuevas (hoy los defaults viven en
  el gizmo generado).
- **Texto un poco desalineado dentro de su panel** (visto por Lega el 17-10,
  tras el fix de paneles alineados en cualquier formato): el panel ya sigue al
  texto, pero el texto no queda del todo centrado en la caja. Falta medirlo
  en NKS con `viewer.image()` en una secuencia de formato distinto al del clip
  y en una igual, y corregirlo. Se dejo para cuando la GPU este libre.

## Como probarlo sin el visor

El visor de una instancia aparte SI dibuja si el cacheo no esta pausado:
`viewer.resumeCaching()`, esperar ~1 s, `setTime()` a un frame NUEVO y
`viewer.image()` (medido 2026-11-14). Es la unica forma de validar lo que se
ve en el timeline (ver "Rendimiento"). Lo de abajo sirve solo para el
render offline. Para validar el
render se arma dentro de NKS, por dev-link, un `Read -> LGA_BurnIn ->
Write` con `nuke.execute` a un PNG: el gizmo es un nodo comun y el render es
deterministico. Ahi no hay metadata `hiero/*` (Clip vacio) ni secuencia
duena (el pivote se fuerza con el formato del Read).

## Referencias tecnicas

| Modulo | Import | Funciones clave |
|---|---|---|
| `LGA_HieroTools/LGA_NKS_BurnIn.py` | registro (startup) | `_register`, `_on_knob_changed`, `_es_derivado`, `_start_mask_watcher`, `_mask_tick` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Layout.py` | `import LGA_NKS_BurnIn_Layout` | `parse`, `dump`, `active`, `default_state`, `fresh_arrangement`, `move_to`, `move_next_to`, `slot_of`, `visible_fields`, `stack_state`, `set_stack`, `is_default`, `compute`, `mask_inset`, `side_pivot`, `line_height` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Logic.py` | `import LGA_NKS_BurnIn_Logic` | `bi_text`, `bi_ok`, `field_geo`, `_frame_state`, `layout_text`, `mask_inset_px`, `line_height_px`, `_plate_tc_frames` (TC de aPlate), `invalidate_cache` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Blink.py` | `import LGA_NKS_BurnIn_Blink` | `setup`, `schedule_update`, `update_now`, `is_busy`, `apply_layout`, `apply_rotation`, `apply_font`, `nudge`, `viewer_mask_aspect`, `apply_mask`, `_timeline_format` |
| `LGA_HieroTools/LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Viewer_Mask.py` | `from LGA_NKS_ViewerTL_Panel_py import LGA_NKS_Viewer_Mask` | `set_mask`, `apply_mask` (el boton 3:2; solo pone la mascara para LGA_BurnIn) |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Panel.py` | `import LGA_NKS_BurnIn_Panel` | `show_panel`, `BurnInPanel`, `BurnInMap`, `TickSlider`, `Segmented`, `HieroController` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Config.py` | `import LGA_NKS_BurnIn_Config` | `resolve`, `load_user_file`, `save_user_file`, `list_presets`, `load_preset`, `save_preset` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_ProjectTag.py` | `import LGA_NKS_BurnIn_ProjectTag` | `find_project`, `read_config_json`, `write_config` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_RoundedPanels.blink` | kernel `LGARoundedPanels` v0.08 | `init` (cajas por panel), `process` (SDF + franjas Band) |
| `LGA_HieroTools/LGA_NKS_Shared/LGA_UI_Style_HieroTools.py` | `from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, Metric` | `apply_ui_font`, `semibold_css`, `emphasis` |
| `LGA_HieroTools/LGA_NKS_Shared/LGA_UI_CustomTooltip_HieroTools.py` | `from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip` | tooltips del panel |

## Deuda de diagnostico

Todo lo aprendido (y sufrido) esta en `Docu_SoftEffects_Aprendizajes.md`.
