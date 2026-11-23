# LGA_BurnIn — soft effect de burn-in con metadata del clip visible

> **Sin BlinkScript (23 nov 2026).** Los fondos redondeados y las franjas de
> Band son Text2 que escriben con la fuente propia **LGA Shapes** (glifos con
> forma de tapa redondeada y de bloque). El BlinkScript dependia de la GPU y
> en maquinas sin una buena el efecto se volvia lento. Validado en el visor
> del timeline de NKS 17.0v4: Panels, Band, Text, los once campos, radio 0,
> costados girados y un proyecto guardado con el efecto viejo.

> Estado (12 nov 2026): **panel Burn-ins con mapa**, el diseno del menu
> Burn-ins de Shot Player (LGA Media Tools). La tabla X / Y / Size por campo
> se reemplazo por un mapa de ocho lugares con seis distribuciones; todo el
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
con Text2 y la fuente LGA Shapes del pack, y pinta en **rojo** lo que no
coincide con el objetivo del proyecto. Todos sus nodos son Text2: no usa
BlinkScript ni depende de la GPU mas que el BurnIn nativo.

## Campos

| Campo | Contenido | Rojo condicional |
|---|---|---|
| Clip | `hiero/clip` | no |
| Colorspace | `sourceMediaColourTransform()` del clip (por API + cache; no viaja en la metadata del stream) | no |
| Res | `input/width` x `input/height` | si: no coincide con NINGUNA de las resoluciones validas. **Solo compara plates** (`compare_res_exts`, default `exr`) |
| Frame | `Frame: <input/frame>` | no |
| TC | `TC: <input/timecode>` | si: difiere del TC del clip del track **aPlate** en ese frame del timeline (`timecodeStart` + `sourceIn` + offset, items cacheados 3 s; una edicion del aPlate se ve a los 3 s como mucho). Sin timecode en la metadata (comp sin TC) o sin aPlate en el frame, no compara |
| FPS | `input/frame_rate` | si: difiere del objetivo |
| Track | `Track: <nombre>`: el track del clip visible. Por API (`hiero/track` llega vacio en el stream, medido): el track item de la secuencia activa cuya fuente es el clip y cubre el frame, de arriba abajo; cache de 1,5 s | no |
| Date | fecha de modificacion del archivo visible (`input/mtime`, `AAAA-MM-DD`), no la del dia: decision de Lega (12-11-2026) | no |
| Codec | EXR: `exr/compressionName` con el nivel si es DWA (`DWAA 60`); otra media: la primera key de metadata que nombre un codec | no |
| Custom 1 / 2 | texto libre (`bi_custom1_text`, `bi_custom2_text`) | no |

Objetivos: `res_target` y `fps_target` — `"timeline"` (formato/fps de la
secuencia) o explicitos (`"3840x2160"`, `24`). `res_target` acepta una
**lista** separada por comas (`"timeline, 3840x2160"`, o una lista JSON): un
proyecto puede tener dos resoluciones correctas (en uno de Lega, el formato
del timeline y 3840x2160) y el rojo se apaga si el plate coincide con
cualquiera (`parse_res_targets` de la config, parseado una vez por config en
`_res_targets` de la logica). **Labels** (`bi_labels`)
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
cada linea una lista de campos de izquierda a derecha. Hay seis
distribuciones (Corners, Top & bottom, Bottom line, Edge, Left list, Classic) y cada
una recuerda como la dejo el usuario. **Classic** reproduce el orden de la pila
de Text2 amarillos que Lega usaba antes en un track BurnIn (leido de sus
.hrox el 23-11): Frame y debajo el clip abajo a la izquierda, TC abajo al
centro, y Res / FPS / Codec abajo a la derecha. Existe porque el ojo ya busca
el frame abajo a la izquierda. En la pila vieja el TC iba en la linea del
Frame; aca va en la linea de abajo (un lugar del centro con una sola linea
se apoya en el borde). La pila tenia ademas la letra de la unidad, el
dataWindow y el displayWindow, que no son campos del efecto. Todo viaja como JSON en el knob
invisible `bi_layout` (modelo en `LGA_NKS_BurnIn_Layout`).

**Por que:** la tabla obligaba a pensar en fracciones del formato y el ancho
de cada texto cambia de clip a clip, asi que dos campos "en la misma linea"
se pisaban o quedaban separados segun el clip. El mapa describe la
intencion (este campo abajo a la derecha, junto a este otro) y el render la
resuelve en pixeles en cada frame.

- **Geometria en render**: `field_geo(field, comp)` de la logica calcula el
  layout entero (`Layout.compute`) con los anchos medidos de los textos y lo
  cachea por (efecto, CUADRO QUE LLEGA, estado): ver "Clave del cache" en
  Rendimiento. Los Text2 de fondo y las cajas de los Text2 de texto leen lo
  mismo, asi que el fondo no se separa del texto.
- **Sin cuadro, clave aparte**: fuera del render (un `setValue`, el
  onCreate) y en muchas evaluaciones del propio Nuke el Input no tiene
  metadata y todos los textos dan vacio. Ese estado vacio va a su propia
  clave (`_NO_STREAM`) y un render con cuadro nunca lo usa. Antes de v1.15
  no se guardaba y se recalculaba en cada llamada (medido en un proyecto
  real: 252 veces en 3 s).
- **Los paneles abrazan al texto**: el ancho se mide con el TTF real de
  LGA Inter Tab que usa Nuke. Como sus digitos son tabulares (todos del
  mismo ancho), el fondo de frame y TC no cambia de ancho entre frames y
  queda centrado; los digitos se normalizan a "0" solo para que el cache de
  medidas tenga una entrada por campo. Un campo sin texto no ocupa lugar.
- **Tamano global**: Size S / M / L es una fraccion del alto del formato
  (`SIZE_FRACTIONS`; M = 50 px en 4K, el tamano historico).
- **Costados girados** (Sides = Rotated, default en Edge): el izquierdo gira
  90 (se lee de abajo arriba) y el derecho 270. El pivote es FIJO por
  costado (`Layout.side_pivot`): sale del formato del timeline, del tamano y
  del padding, no del ancho del texto. Lo escribe `apply_rotation` en
  `bi_<f>_ax/ay`, y va en el blob del Text2 del texto y en el de su fondo.
- **Fondo** (`bi_bg_mode`): Panels (uno por campo), Band (una franja de lado
  a lado en cada borde usado: `field_geo('_band', t/b/l/r)`; las de los
  costados entre la de arriba y la de abajo) o Text (sin
  fondo, con la sombra de los Text2).

## Mascara del viewer

Con una mascara en el viewer (cualquier aspect, elegida desde el menu del
viewer o con el boton del panel Viewer | TL), los burn-ins se corren hacia
adentro para quedar en el area visible. Cuenta tambien la mascara al 50%
(Half): ya los tapa a medias.

- **Deteccion**: `viewer_mask_aspect()` (`LGA_NKS_BurnIn_Effect`) lee `maskOverlayStyle()`,
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
Input -> Dot -> Band_T/B/L/R -> 11x (Panel_<Campo> -> Text_<Campo>) -> Output
```

**Fuente**: es **LGA Inter Tab** (Inter con digitos tabulares, ver abajo),
fija (la del pack); el usuario elige solo el PESO
(Regular/SemiBold/Bold via `bi_weight`, que setea el `bi_font` invisible por
`apply_font()`). Para no depender de que Inter este instalada en la maquina,
el startup (`LGA_HieroTools_Startup.py`) antepone el fonts dir del repo
(`LGA_NKS_Shared/fonts/`, con los tres pesos) a `NUKE_FONT_PATH`, que Nuke
lee al escanear las fuentes (una vez, al arrancar; no en runtime). Asi Nuke
descubre el Inter del repo —incluido Bold, que el Inter de Windows no trae—
sin instalar nada. Al cambiar el peso, el fondo se recalcula (mide con el
TTF del peso nuevo).

**Digitos tabulares: LGA Inter Tab.** Text2 dibuja con los digitos
proporcionales de Inter (un "1" mide 0,41 em y un "4" 0,65 em) y no aplica el
rasgo OpenType `tnum` ni deja ubicar cada caracter por separado. Con Inter, el
texto de frame y TC cambiaba de ancho en cada frame y el fondo, reservado para
el digito ancho, quedaba vacio de un lado (medido en NKS 17 a 1080: margen de
22 px a la izquierda y de 28 a 45 a la derecha segun el frame). El Shot Player
de Media Tools resolvio lo mismo dibujando cada digito en una celda del ancho
del digito mas ancho; en Text2 eso se resuelve en la FUENTE: `LGA Inter Tab`
(`LGA_NKS_Shared/fonts/LGA_Inter_Tab-400/600/700.ttf`) es Inter con el cmap de
0-9 apuntado a sus digitos tabulares propios (`zero.tf`..`nine.tf`), renombrada
(Inter es OFL sin Reserved Font Name). Mismo look, cero costo en el render
(medido: 0,19-0,20 ms por estado calculado con las dos fuentes). Despues: fondo
fijo y margenes 23/24 px en 1001, 1011, 1044 y 1111. Los demas campos tambien
usan esta fuente; solo cambian sus digitos. La genera
`+Building_Blocks/BurnIn/gen_LGA_Inter_Tab_font.py` (necesita fontTools, solo
en desarrollo). `apply_font()` corre en el onCreate: un proyecto guardado con
Inter pasa solo a la fuente nueva al abrirse (medido).

- **Dot1**: lleva el `onCreate`, que llama a
  `LGA_NKS_BurnIn_Effect.setup()`: fuentes (`bi_font` LGA Inter Tab del peso y
  `bi_shape_font` LGA Shapes), mascara del viewer y layout.
- **Band_T/B/L/R** y **Panel_<Campo>**: un Text2 por fondo, con la fuente
  **LGA Shapes** (`LGA_NKS_Shared/fonts/LGA_Shapes.ttf`, generada por
  `+Building_Blocks/BurnIn/gen_LGA_Shapes_font.py`). El mensaje es
  `tapa izquierda + bloques + tapa derecha` y mide justo el rect del fondo
  (`LGA_NKS_BurnIn_Logic.shape_msg`); la caja y el alto (`global_font_scale
  = h / 100`) salen de `shape_geo`. Un Text2 compone todos sus glifos como
  una sola forma: la opacidad queda pareja. Las franjas de los costados van
  solo entre la de arriba y la de abajo, para no pintar dos veces las
  esquinas. Cada panel va antes que su texto y gira con el mismo blob.
  Medido al pixel en NKS 17 (detalle y trampas en
  `Docu_SoftEffects_Aprendizajes.md`, "Fondos redondeados sin BlinkScript").
- **Text2 x11** (9 de metadata + custom1/custom2): anatomia calcada del
  BurnIn nativo (blobs de estado incluidos — sin ellos el GPU los dibuja en
  el origen). Cada message llama a `LGA_NKS_BurnIn_Logic.bi_text()` con
  `[frame]`. **Todas** las llamadas python del gizmo (cajas, fondos, color)
  reciben el `[frame]` de TCL, nunca `nuke.frame()`: ese es el frame global
  del root y reproduciendo vale 0 en la mitad de las evaluaciones (medido;
  generador v12); res y fps llevan el color condicional via `bi_ok()` en los
  canales g/b. El texto se centra verticalmente dentro de su panel
  (`yjustify center`) con `text padding`. La caja de cada Text2 usa tres
  llamadas a `field_geo` (x, y, y2; el borde derecho es `width*3`) y suma
  `0*parent.bi_rev`, para que `nudge()` la haga re-evaluar.
- El gizmo se REGENERA con
  `+Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py` (tabla de layout +
  plantillas Text2 de fondo y de texto). No editar el `.gizmo` a mano.

## Archivos

```
LGA_HieroTools/
  LGA_NKS_BurnIn.py                registro de LGA_BurnIn + eventos + vigia de mascara
  LGA_NKS_BurnIn_py/
    LGA_BurnIn.gizmo               el efecto (generado)
    LGA_NKS_BurnIn_Effect.py       puente gizmo <-> knobs (fuentes, layout, giro)
    LGA_NKS_BurnIn_Logic.py        textos, comparaciones, geometria en render
    LGA_NKS_BurnIn_Layout.py       modelo del mapa (Python puro, sin Nuke ni Qt)
    LGA_NKS_BurnIn_Config.py       capa pura de config (testeable sin Nuke)
    LGA_NKS_BurnIn_ProjectTag.py   override que viaja en el .hrox (tag)
    LGA_NKS_BurnIn_Panel.py        ventana Burn-ins (mapa + look)
    logs/DebugPy_LGA_NKS_BurnIn.log
  LGA_NKS_Shared/fonts/LGA_Shapes.ttf               fuente de los fondos
  LGA_NKS_Shared/fonts/LGA_Inter_Tab-*.ttf          fuente del texto (Inter, digitos tabulares)
  +Building_Blocks/BurnIn/gen_LGA_Inter_Tab_font.py generador de LGA Inter Tab (dev)
  +Building_Blocks/BurnIn/gen_LGA_BurnIn_gizmo.py   generador (dev)
  +Building_Blocks/BurnIn/gen_LGA_Shapes_font.py    generador de la fuente (dev)
  +Building_Blocks/BurnIn/design/BurnIn_Panel_Mapa.html  mockup aprobado
  +Building_Blocks/UI_Capture/fixtures/h3_burnin_panel.py  fixture del harness
```

## Panel Burn-ins (Open Burn-in Panel)

El properties del gizmo quedo **pelado a un solo boton**, **Open Burn-in
Panel**; todo se edita en la ventana **Burn-ins** (`LGA_NKS_BurnIn_Panel`,
`Style.FORM`, captura en `UI_Captures/BurnIn_Panel.png`). Mockup aprobado
en `+Building_Blocks/BurnIn/design/BurnIn_Panel_Mapa.html`.

- **Presets**: las seis distribuciones en un segmentado, y **Reset** vuelve
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
- **Project targets**: Plate res acepta varias resoluciones separadas por
  comas; al guardar se normaliza (`format_res_targets`: `timeline,
  3840x2160`) y si hay un valor que no se entiende avisa y no guarda. Save to
  Project escribe el tag `LGA_BurnIn_Settings`
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
expresiones del gizmo (cajas, mensajes de texto y de fondo, colores) solo
leen de ahi. El panel y el knobChanged piden la actualizacion a
`LGA_NKS_BurnIn_Effect.schedule_update`, que junta todo lo de un ciclo de
eventos en una sola por efecto, y `nudge()` escribe un solo knob.

**Sin BlinkScript (23-11-2026).** Render offline a 4K (CPU de Nuke, 10
cuadros, mediana de 3, NKS 17): plate solo 237 ms por cuadro, LGA_BurnIn
nuevo 224, el viejo con BlinkScript 306 en GPU y 256 forzado a CPU. Todo
dentro del ruido de escribir el EXR: el efecto nuevo no se distingue del
plate solo. Sus nodos son todos Text2, como el BurnIn nativo.

**Contra la pila vieja de Text2 amarillos (23-11-2026).** En el visor del
timeline de una instancia aparte de NKS 17: plate EXR 4K, 600 cuadros sin
cache, cinco rondas alternadas de 30 cuadros, se espera la senal
`frameDisplayed` de cada uno (sonda `+Building_Blocks/BurnIn/perf_stack.py`).
La pila son los 4 Text2 de los .hrox viejos (Frame/TC/clip, Reso, Drive,
Fps), con `[metadata]` en TCL; el LGA BurnIn va en Classic (6 campos).

| Caso | Pared por cuadro (mediana) | CPU del proceso por cuadro |
|---|---|---|
| Sin burn-in | 26 ms | 65 ms |
| Pila vieja (4 Text2) | 47 ms | 89 ms |
| LGA BurnIn Classic | 45 ms | 148 ms |

La pared es muy ruidosa (cada caso va de 20 a 90 ms segun la ronda): en
tiempo de visor no se distinguen. La CPU si: el LGA BurnIn usa del orden de
60 ms mas por cuadro que la pila. Una parte se midio aparte: el Python de
sus expresiones son 6,8 ms por cuadro en 309 llamadas, y tiene 12 Text2
activos (texto y fondo de cada campo) contra 4. Es el proximo lugar para
optimizar (ver Pendientes).

Numeros de la version con BlinkScript (CPU del proceso, instancia aparte):

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

**Lo que NO funciona, medido:** dibujar los fondos con nodos nativos
(Crop + Expression + Merge, o Rectangle). En un render offline
(`Read -> gizmo -> Write`) da bien y hasta mas barato, pero en el timeline
esos nodos no dibujan nada (solo corren los nodos con motor de soft effect)
y tres o mas Merge2 encadenados tiran NKS 17. Detalle en
`Docu_SoftEffects_Aprendizajes.md`. Por eso el banco offline NO sirve para
decidir el diseno: todo cambio de estructura se valida mirando el visor del
timeline.

**Clave del cache: el cuadro que llega (v1.15, 23-11-2026).** Lega vio en
el primer cuadro de un plano el frame y el TC del plano anterior (TC en rojo);
un cuadro despues se veia bien. Medido en NKS 17: el estado se guardaba por
(efecto, frame), pero fuera del render (el punto rojo del panel con
`nuke.frame()`, que por API vale 1; el Properties; el knobChanged) el frame
no corresponde al cuadro que tiene el Input en ese momento, y el estado
guardado con el cuadro de otro plano lo reusaba despues el render. En su
proyecto, el estado del frame del corte tenia un plano de otra parte de la
secuencia. Ademas las cajas, los fondos y el color usaban `nuke.frame()`,
que reproduciendo vale 0 en la mitad de las evaluaciones: todas leian el
estado viejo del frame 0, y el TC se comparaba contra el aPlate del frame 0.

Ahora la clave es el cuadro que llega (`_stream_id`: `input/filename` +
`input/frame`, dos lecturas de ~1 us), sin el frame del timeline; el rojo del
TC va aparte, por (frame, version de los items de aPlate). Todas las
llamadas reciben `[frame]`. Reproduciendo, un estado por cuadro (antes, dos
o reusados equivocados) y 16,0 us por llamada contra 14,9 us antes (el
formato se lee del Input1, 0,7 us contra 3 us del grupo, y la firma con
`getValue()`). Prueba de corte armada en una instancia aparte: dos planos
pegados, aPlate que cubre solo una parte, el cache ensuciado a proposito con
llamadas por API en frames equivocados; primer y ultimo cuadro de cada plano
correctos y el TC rojo solo donde el aPlate no coincide.

**Prueba de estres (23-11-2026, NKS 17, copia de un proyecto real de 6819
frames con EXR 4K en red, nunca guardada).** 1900 acciones al azar en cuatro
tandas, una cada 120 ms: agregar y sacar el efecto, prenderlo y apagarlo,
saltar a cuadros y a cortes, reproducir y parar, prender y apagar tracks,
abrir y cerrar el panel, cambiar presets y knobs. Cero errores y cero
cuelgues. Sin el efecto (linea de base, 400 acciones) no hay trabas de mas
de 0,5 s; con el efecto hay 5 a 10 por tanda, de 0,5 a 0,9 s, siempre
despues de prender o apagar un track o de agregar el efecto.

Medido en esa copia (peor demora del hilo principal en los 2 s despues de
prender o apagar un track): NKS re-evalua las expresiones de los cuadros que
tiene cacheados, 5000 a 8000 llamadas `[python]` por cambio. Con la llamada
real, 410-670 ms; con `[python 0]` en las 99 expresiones numericas, 125-155
ms (el mecanismo TCL a python es barato); con la llamada real pero sin la
logica (estado fijo), la mitad. Lo que pesa adentro es la primera lectura de
metadata del Input (12-30 us con los EXR reales, 1 us con media chica: Nuke
arma la metadata entera); por eso `_stream_id` lee `input/frame` solo si el
archivo no es de una secuencia. El BurnIn nativo traba 33-116 ms. No es nuevo
de v1.15 (con `nuke.frame()` da lo mismo). Bajarlo de verdad pide menos
expresiones `[python]` por nodo (ver Pendientes). Descartado, medido: la
escala de los fondos en TCL puro (dispara MAS evaluaciones: 11000 contra
8400) y leer la metadata por TCL desde python (232 us por lectura).

Agregar CUALQUIER efecto por API con la reproduccion andando (tambien un
Text2 comun) traba NKS 10 s exactos; parado tarda 5-20 ms: es de NKS.

## Diagnostico en otra maquina: log de tiempos [Perf]

Existe porque a un usuario con una RTX 3080 el efecto le andaba lentisimo
en su maquina (en la de Lega anda bien): lento al agregarlo, al prender o
apagar cosas, y NKS se trababa al apretar Open Burn-in Panel. En la maquina
de Lega abrir el panel tarda ~16 ms y no escribe ningun knob (medido el
23-11), asi que la causa hay que medirla en la maquina que falla. Con v4.029
(sin BlinkScript) se le pide al usuario que repita lo que le andaba lento y
que mande el log.

- **Donde:** `LGA_HieroTools/LGA_NKS_BurnIn_py/logs/DebugPy_LGA_NKS_BurnIn.log`,
  dentro del pack instalado. Se pisa en cada sesion de NKS: hay que mandarlo
  ANTES de volver a abrir NKS. Con dos NKS abiertos a la vez escriben el
  mismo archivo (la linea `sesion` lleva el pid para separarlos).
- **Siempre prendido y barato:** el render solo suma contadores; nada se
  escribe por frame.

Lineas, todas con el prefijo `[Perf]`:

| Linea | Que dice | Quien la escribe |
|---|---|---|
| `sesion: NKS ..., HieroTools ..., Windows ..., N nucleos, pid ...` | con que se corre | `perf_header` (al registrar el efecto) |
| `setup <efecto>: X ms (fuente, layout, nudge)` | agregar el efecto o cargar un proyecto que lo tiene | `LGA_NKS_BurnIn_Effect.setup` |
| `actualizacion <efecto>: X ms (...)` | cada cambio de knob o del panel (agrupado por ciclo de eventos) | `LGA_NKS_BurnIn_Effect.update_now` |
| `abrir panel: X ms (buscar efecto, armar, fuente, mostrar)` | el costo del panel en si | `LGA_NKS_BurnIn_Panel._perf_open` |
| `panel visible y NKS libre a los X ms del click` | cuando NKS vuelve a atender eventos con la ventana mostrada; si aca hay segundos y la linea anterior es chica, lo lento es lo que NKS hace al mostrarla, no el panel | idem (QTimer de 0 ms) |
| `render X s: N expresiones, M estados calculados (total, el peor)` | cuanto trabajo Python le pide el render; cada ~2 s y solo si hubo render | `perf_flush`, desde el vigia |
| `NKS trabado ~X ms (ultima actividad del efecto: ...)` | el hilo principal estuvo trabado mas de 0,7 s; nombra lo ultimo que hizo el efecto (knob, actualizacion, abrir el panel, setup) | `_perf_tick` del vigia de la mascara (`LGA_NKS_BurnIn.py`) |

Como leerlo: si los `NKS trabado` son largos y los `render` y
`actualizacion` chicos, el tiempo no se va en el Python del efecto sino en
el render del propio NKS (los Text2, la lectura del media, la GPU). Si
`ultima actividad` dice `ninguna`, el efecto no hizo nada antes del trabado
(por ejemplo al arrancar NKS).

## Limitaciones conocidas

- Un burn-in por vez en la ventana: edita el primer efecto LGA_BurnIn que
  encuentra en la secuencia activa (boton Refresh para re-buscar).
- El colorspace se cachea por clip; un cambio a mano se refleja al
  guardar/reabrir el proyecto.
- Comparacion de resolucion solo para plates (EXR por default).
- **Fuentes del pack**: si `LGA Shapes` o `LGA Inter Tab` no estan
  registradas, los fondos no se dibujan o el texto sale con otra letra
  (cache de
  fuentes de Nuke viejo), los fondos no se dibujan. El startup borra ese
  cache cuando le falta una fuente del pack (`_refresh_font_cache`).
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

- **Agregar un efecto reproduciendo** (por API, cualquier efecto) traba NKS
  10 s; parar antes (medido el 23-11).

## Pendientes

- **Bajar la CPU por cuadro hasta la de la pila vieja** (medido el 23-11,
  ver «Contra la pila vieja» en Rendimiento): 309 llamadas de Python por
  cuadro con 6 campos visibles, y 12 Text2 activos contra 4.
- **Traba al prender o apagar un track con el efecto puesto** (0,4-0,9 s en
  un proyecto real con EXR 4K; el nativo 33-116 ms; ver "Prueba de estres").
  Viene de la cantidad de expresiones `[python]` que NKS re-evalua por
  cuadro cacheado (~190 por cuadro). Opcion a medir: menos llamadas por nodo
  (por ejemplo, que y2 no llame a python) sin que Nuke sume evaluaciones.

- **Usuario con RTX 3080 al que todo le anda lento** (ver «Diagnostico en
  otra maquina»): pasarle v4.029, que repita lo que le andaba lento
  (agregar el efecto, prender y apagar, abrir el panel) y mandar el log.
- Aplicar defaults de config a instancias nuevas (hoy los defaults viven en
  el gizmo generado).
- **Texto un poco desalineado dentro de su panel** (visto por Lega el 17-10,
  tras el fix de paneles alineados en cualquier formato): el panel ya sigue al
  texto, pero el texto no queda del todo centrado en la caja. Una causa
  medida el 23-11: el fondo de glifos quedaba 2 px mas arriba que su caja
  (corregido con `_GLYPH_DY` en `shape_geo`). Falta confirmar a ojo con
  material real en un formato distinto al del clip.

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
| `LGA_HieroTools/LGA_NKS_BurnIn.py` | registro (startup) | `_register`, `_on_knob_changed`, `_es_derivado`, `_start_mask_watcher`, `_mask_tick`, `_perf_tick` (log de NKS trabado y resumen del render) |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Layout.py` | `import LGA_NKS_BurnIn_Layout` | `parse`, `dump`, `active`, `default_state`, `fresh_arrangement`, `move_to`, `move_next_to`, `slot_of`, `visible_fields`, `stack_state`, `set_stack`, `is_default`, `compute`, `mask_inset`, `side_pivot`, `line_height` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Logic.py` | `import LGA_NKS_BurnIn_Logic` | `bi_text`, `bi_ok`, `field_geo`, `shape_msg`, `shape_geo`, `shape_message`, `_shapes`, `_frame_state`, `_stream_id` (clave del cache: el cuadro que llega), `viewer_frame` (playhead, para el panel), `_plate_version`, `_res_targets` / `_res_matches` (varias resoluciones), `layout_text`, `mask_inset_px`, `line_height_px`, `_plate_tc_frames` (TC de aPlate), `invalidate_cache`, `TEXT_FAMILY`, `_measure_text`, `_font_path`, `_qt_family`, `_digit_template`, `_compute_state`, `perf_log`, `perf_mark`, `perf_last`, `perf_flush`, `perf_header` (log [Perf]) |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Effect.py` | `import LGA_NKS_BurnIn_Effect` | `setup`, `schedule_update`, `update_now`, `is_busy`, `apply_layout`, `apply_rotation`, `apply_font`, `nudge`, `viewer_mask_aspect`, `apply_mask`, `_timeline_format`, `_perf_update` |
| `LGA_HieroTools/LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Viewer_Mask.py` | `from LGA_NKS_ViewerTL_Panel_py import LGA_NKS_Viewer_Mask` | `set_mask`, `apply_mask` (el boton 3:2; solo pone la mascara para LGA_BurnIn) |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Panel.py` | `import LGA_NKS_BurnIn_Panel` | `show_panel`, `_perf_open`, `BurnInPanel`, `BurnInMap`, `TickSlider`, `Segmented`, `HieroController` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_Config.py` | `import LGA_NKS_BurnIn_Config` | `resolve`, `parse_res`, `parse_res_targets`, `format_res_targets`, `parse_fps`, `load_user_file`, `save_user_file`, `list_presets`, `load_preset`, `save_preset` |
| `LGA_HieroTools/LGA_NKS_BurnIn_py/LGA_NKS_BurnIn_ProjectTag.py` | `import LGA_NKS_BurnIn_ProjectTag` | `find_project`, `read_config_json`, `write_config` |
| `Python/Startup/LGA_HieroTools_Startup.py` (fuera del paquete) | startup | `NUKE_FONT_PATH`, `_refresh_font_cache`, `_font_cache_dirs` |
| `LGA_HieroTools/LGA_NKS_Shared/fonts/LGA_Inter_Tab-400/600/700.ttf` | fuente (generada por `+Building_Blocks/BurnIn/gen_LGA_Inter_Tab_font.py` desde `Inter-*.ttf`) | familia `LGA Inter Tab`, estilos Regular / SemiBold / Bold; digitos 0-9 = `zero.tf`..`nine.tf` de Inter |
| `LGA_HieroTools/LGA_NKS_Shared/fonts/LGA_Shapes.ttf` | fuente (generada por `+Building_Blocks/BurnIn/gen_LGA_Shapes_font.py`) | tapas `U+E000+i` / `U+E100+i`, bloques `U+E200..E203`, bloques sin solape `U+E210..E213` |
| `LGA_HieroTools/LGA_NKS_Shared/LGA_UI_Style_HieroTools.py` | `from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, Metric` | `apply_ui_font`, `semibold_css`, `emphasis` |
| `LGA_HieroTools/LGA_NKS_Shared/LGA_UI_CustomTooltip_HieroTools.py` | `from LGA_NKS_Shared.LGA_UI_CustomTooltip_HieroTools import set_custom_tooltip` | tooltips del panel |

## Deuda de diagnostico

Todo lo aprendido (y sufrido) esta en `Docu_SoftEffects_Aprendizajes.md`.
