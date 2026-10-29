> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios.

# Shot Marks (panel Review)

## Para que existe

Llega un corte bloqueado como un solo MOV del episodio y una planilla de breakdown con un REC TC por
shot. Hace falta ver en el timeline donde cae cada shot con VFX, saltar de uno al siguiente y cruzar
la planilla contra el corte. A mano son cientos de marcas, y hay que rehacerlas en cada update de
planilla o de corte. Shot Marks las pone todas de una vez y, al volver a correrla, reemplaza solo las
suyas.

## Que hace

1. Lee la planilla (`.xlsx` o `.csv`) fuera del hilo de UI y sugiere la hoja con columnas de shot y
   REC TC (en un archivo de 55 hojas tarda ~1,5 s).
2. Detecta la fila de encabezado (puede no ser la primera: suele haber una tablita de resumen arriba)
   y las columnas de shot, TC IN, TC OUT, episodio, status, brief, descripcion, escena, vendor y
   categoria. Todo se puede corregir en la
   ventana y queda guardado en `%APPDATA%\LGA\HieroTools\ShotMarks.ini`.
3. Prueba en seco en vivo: cuantas marcas, cuantas Omit salteadas, cuales no se pueden ubicar y por
   que. El log de cada corrida va a `LGA_NKS_Review_Panel_py/logs/DebugPy_LGA_NKS_ShotMarks.log`.
4. Al aplicar, en un solo undo: borra los tags que puso antes, opcionalmente alinea el TC de inicio
   del timeline y crea un tag de rango por shot (`Sequence.addTagToRange`), con el shot como nombre y
   el brief como nota.

## Previous / Next Mark

Shift+Click en Previous Annotation / Next Annotation del panel Review (el Click normal sigue
navegando anotaciones del clip). Salta el playhead al IN de la marca anterior o siguiente del
timeline del visor y muestra su info en una ventanita: shot, REC TC IN y OUT de la planilla,
duracion, status, vendor, escena, categoria, descripcion y brief. En los extremos da la vuelta.
Previous, con el playhead adentro de un shot, vuelve al IN de ese shot.

- **Por que no alcanza el salto nativo.** Viewer > Next Tag salta, pero no muestra la nota, y la
  ventana del tag de Hiero la muestra recortada.
- **Una sola ventana.** El panel re-ejecuta el modulo en cada click, asi que la ventana no se
  guarda en una variable: se busca entre los `topLevelWidgets()` por `objectName`
  (`LGA_ShotMarkInfo`) y se actualiza en el lugar. Si cambio su API (`WINDOW_API`), se reemplaza
  por una nueva en la misma posicion.
- **Sin robar foco.** `Qt.Tool` con la ventana principal de NKS como padre (flota sobre NKS y
  se esconde con el) y `WA_ShowWithoutActivating`. Medido en NKS 16.0v4: tres saltos seguidos,
  la ventana nunca quedo activa y el primer plano de Windows no cambio.
- **Sigue al playhead.** Mientras esta abierta escucha `Viewer.timeChanged` del visor donde se
  salto. En cada cuadro, tambien en playback, solo lee `viewer.time()` y busca la marca con
  `mark_index_at` (busqueda binaria sobre los IN/OUT cacheados como enteros): medido ~8 µs por
  cuadro con un visor simulado. Redibuja solo al entrar en OTRA marca; entre marcas queda la
  ultima. `sequenceChanged` relee las marcas; cerrar la ventana desengancha el visor. El
  seguimiento se arma antes del `setTime` del salto, porque ese salto ya dispara `timeChanged`.
  Pendiente: medirlo en NKS en vivo (la senal y su frecuencia en playback).
- **Marcas de un cuadro: se estiran hasta la siguiente para seguir al playhead.** Una planilla con
  REC TC OUT igual al IN (o vacio) deja marcas de un cuadro. Medido en NKS 17 en un episodio con
  las 174 asi: al arrastrar, la ventana solo cambiaba si el playhead pisaba el IN exacto, y el log
  lo delataba (cada cambio caia justo en un IN). `follow_ends` les da, solo para el seguimiento,
  un OUT en el cuadro anterior a la marca siguiente; el tag no se toca y las marcas con rango real
  siguen igual. El log anota cuantas se estiraron y cada entrada del playhead a un cuadro sin
  marca (una linea por hueco, no por cuadro).
- **Vendor con color.** `LGA_NKS_Shared/LGA_NKS_Vendor_Colors_Config.py` lee de la DB de PipeSync
  del contexto activo (studio o client) la tabla `project_vendor_groups` (token, nombre, color)
  y, de respaldo, `vendor_colors` del envelope del proyecto. Compara sin mayusculas ni signos
  (`Vendor-B` = `VENDORB`), primero en el proyecto del `.hrox` (nombre o prefijo) y si no esta, en
  todos, salvo que el mismo vendor tenga colores distintos. Sin color, se muestra el texto solo.
  Una celda con varios vendors (`Vendor A, Vendor B`) se separa por coma, barra, `+`, `&`, `;`
  o "y"/"and" como palabra sola, y cada uno lleva su color; el guion no separa. Si la celda
  entera ya es un vendor conocido, no se parte.
- **El alto se mide con los layouts invalidados.** La ventana tiene ancho fijo y alto segun el
  texto. Al cambiar el texto de un label, el layout recien se entera por un evento diferido: si
  se mide en el mismo paso devuelve el alto de la marca anterior. Medido en NKS 16 al pasar de
  una marca con Category en una linea a otra con dos: la ventana quedaba con el alto viejo, la
  descripcion cortada a un renglon y restos del pie anterior abajo. `_fit()` invalida el layout
  del encabezado, llama `updateGeometry()` del encabezado (su alto lo cachea el layout de
  arriba) e invalida el de la ventana antes de medir.
- **Letra mas grande.** 15 px el cuerpo y 19 px el titulo, por `apply_ui_font` y QFont: con el
  tamano del host (~12 px) no se leia. El titulo no usa `lgaTitle` porque esa regla fija 11 pt.
- **Los datos salen del tag, no del Excel.** Shot Marks guarda la fila en la metadata del tag
  (`tag.lga_shotmarks_tc_in`, `_tc_out`, `_brief`, `_description`, `_status`, `_vendor`,
  `_scene`, `_category`, `_episode`). Releer el Excel tardaria medio segundo por salto y fallaria
  si la planilla se mueve. Los tags creados antes de esta version solo tienen nombre y nota: la
  ventana muestra eso y pide volver a correr Shot Marks.

## Planillas sin timecode: ubicar desde los thumbnails (solo Windows)

Hay breakdowns que no traen REC TC: solo una foto por shot, pegada en la hoja. Si la hoja elegida
no tiene columna de TC pero sus filas de shot tienen imagen, el boton del dialogo pasa a
**Locate from Thumbnails...**: busca cada foto en el MOV del timeline y marca el plano que la
contiene, de corte a corte. Al terminar, el dialogo se reabre con los TC ubicados como columnas
nuevas (`REC TC IN (located)` / `OUT`) y sigue igual que con una planilla con TC.

**Piezas**

- `LGA_NKS_ShotMarks_Thumbs.py`: que imagen esta anclada en que fila (`xl/drawings/drawingN.xml`,
  `twoCellAnchor` / `oneCellAnchor`). Una foto que termina en el borde de la fila siguiente es de
  la primera; una que cruza varias, de la del medio. Varias fotos en una fila: gana la de la
  columna mas a la izquierda. Se extraen una vez con su sha1 de nombre. Las imagenes "en celda"
  (`xl/richData/`) son otro formato y todavia no se leen.
- `LGA_NKS_ShotMarks_Locate_Engine.py`: el motor. **Corre como proceso aparte** con el Python
  embebido del pack (`QProcess`), no en un hilo de NKS: es ~1 min de Python puro que en un hilo
  se pelearia el GIL con la UI. Solo libreria estandar; progreso por stdout en lineas JSON.
- `LGA_NKS_ShotMarks_Locate.py`: la ventana de revision.
- `LGA_NKS_Shared/FFmpeg_Win/bin/ffmpeg_lga.exe`: un ffmpeg minimo propio (4,2 MB, LGPL), con la
  misma receta que el ffprobe (`+Building_Blocks/Binarios_Pack/build_ffmpeg_lga.sh`). Solo trae
  los demuxers/decoders de MOV, MXF, JPG y PNG y los filtros que usa el motor.

**El motor, paso a paso**

1. **Indice del video**, una vez por video (clave: ruta + tamano + fecha), en
   `%LOCALAPPDATA%\LGA\HieroTools\ShotMarks_Locate\index\`. Una sola pasada de ffmpeg guarda por
   cuadro una huella 9x8 gris (dHash, 64 bits), otra 32x18 gris y el puntaje de cambio de escena
   de `scdet`. Medido: 225.498 cuadros (2,6 h ProRes LT HD) en ~3,5 min; despues queda en cache.
2. **Thumbs**: se detecta el area de imagen (sin barras ni la UI de un player de dailies) y se
   recorta igual que el video: mismo 92 % central, mismo paso por 160x86. **El recorte es por
   lote**: todos los thumbs del mismo tamano usan la moda de las detecciones con buen aspecto. El
   recorte de cada uno fallaba en escenas oscuras (aspectos de 0,99 a 2,86 medidos sobre un video
   de 1,85) y daba por ausentes shots que estaban.
3. **Busqueda global**: dHash contra todos los cuadros (filtro barato), los 30 planos mas cercanos,
   y en cada uno la correlacion normalizada (NCC) en gris, que tolera un grade distinto. 8
   procesos, ~13 s para 450 thumbs.
4. **Anclas y orden**: los seguros (NCC >= 0,90 y margen >= 0,10 contra el mejor de OTRO plano a
   menos de 2400 cuadros) son anclas. Un ancla que cae antes o despues de todas sus vecinas en
   orden de planilla se marca como escena movida en el montaje. El resto se busca solo entre el
   ancla anterior y la siguiente: asi se resuelven los planos que vuelven en el montaje (A-B-A),
   que el dHash solo no distingue. El orden es por FILA y no por shot: un mismo shot puede estar
   en varias filas intercaladas.
5. **Dos shots distintos no pueden caer en el mismo plano**: el de menor puntaje pasa a revision.
6. **Cuadro exacto**: a 32x18 los cuadros vecinos de un plano empatan; se decodifican +-24
   cuadros a 192x104 y se elige el mejor (~0,4 s por shot, en paralelo).
7. **IN/OUT**: el plano del EDL que contiene el cuadro (ver abajo). Sin EDL, el plano entre los
   cortes de `scdet` (picos locales con puntaje > 6; de dos detecciones a menos de 3 cuadros
   queda la mas fuerte), y un "plano" de mas de 60 s es un encadenado o un corte que no se vio:
   la marca va solo en el cuadro del thumb.

**Niveles**: `auto` (aceptado solo), `review` (puntaje >= 0,60 sin las condiciones de `auto`),
`not_found`; y los que pone el usuario: `confirmed` y `not_in_cut`. Los seguros se aceptan solos
desde la primera corrida; los `review` se marcan igual, como no confirmados.

**Lo que ningun metodo por imagen resuelve**: una captura de dailies de un cuadro que no esta en
el corte (otra toma, otro tramo de la toma). Medido: esos dan 0,73-0,77 aunque sea la escena
correcta; cuando el cuadro de una captura de dailies si esta en el corte da >= 0,88. Por eso van a
revision y nunca se aceptan solos. El EDL no lo resuelve: la planilla no trae el clip de camara
de cada foto (su "Shooting name" es escena_plano_toma, no el nombre del clip), asi que no hay con
que cruzar el SRC TC.

### EDL del armado (opcional)

El dialogo, en modo thumbnails, tiene un campo **EDL** (se recuerda en `ShotMarks.ini`,
`last_edl`). Va el EDL de la pista de video del mismo armado que el MOV.

**Por que.** Medido contra el EDL de un armado de 2,6 h (1567 planos, 1586 cortes): `scdet` acerto
1460 cortes al cuadro, perdio 126 y marco 35 que no existen. Los perdidos son cortes entre planos
de la misma escena y la misma luz, con puntaje 2-6 contra el umbral de 6; los de mas son
flashes, relampagos y movimientos rapidos (puntajes de 6 a 25). Mover el umbral cambia un error
por el otro. Sin EDL, 46 de 407 filas quedaban con IN/OUT corrido o de un cuadro, y dos shots
distintos se daban por el mismo plano porque scdet fundia sus planos.

**Como entra** (`LGA_NKS_ShotMarks_EDL.py`, sin host):

- CMX 3600: solo eventos de video con largo; el reel puede tener espacios; el lado "desde" de
  una disolvencia (evento de largo cero) se descarta y el plano entrante empieza en el REC IN del
  evento `D`; `* FROM CLIP NAME:` da el clip (en los titulos, solo la primera linea); `M2` marca
  cambio de velocidad (sin SRC TC por cuadro). `FCM: DROP FRAME` se respeta para 30/60.
- **Se verifica contra la imagen antes de usarlo.** El REC TC se lleva al cuadro del MOV con el
  TC del MOV y se cruzan sus cortes con los de `scdet`, probando desfasajes de +-400 cuadros
  (entra la cola de 10 s). Se usa si coincide al menos la mitad al cuadro; ante casi empate gana
  el desfasaje 0. Un EDL de otro armado no pasa: se sigue con `scdet` y la ventana lo dice. En el
  armado medido coinciden 1460 de 1586 con desfasaje 0.
- Con EDL, sus planos reemplazan a los de `scdet` en todo: unidad de busqueda, "dos shots no
  pueden caer en el mismo plano", IN/OUT (sin el tope de 60 s) y RePag/AvPag en la revision. Un
  cuadro en un hueco de la pista usa el criterio de `scdet`.
- Cada fila lleva el clip de camara, el SRC TC IN/OUT del plano y el evento. Viajan a la
  planilla ubicada como columna `LGA Clip` (`clip | src in | src out | evento`) y a la metadata
  del tag como `tag.lga_shotmarks_clip`. **No se llama `source`**: `tag.lga_shotmarks_source` ya
  es el origen de la marca (archivo y hoja), y un rol con ese nombre lo pisaba.
- **Plano que vuelve (A-B-A).** Si el segundo candidato de una fila dudosa es el mismo clip en
  otro evento, la fila dice "Same clip also at candidate 2": el thumb puede ser de cualquiera de
  los dos. Medido: una fila pasa de aceptada a revisar por esto (el clip esta dos veces en
  15 s) y otra pasa de revisar a aceptada (el falso "mismo plano" de scdet).

Verificado en NKS 17.0v4 por dev-link: 336 marcas, todas con el IN sobre un corte del EDL, ninguna
de un cuadro, y el clip y el origen en la metadata de cada tag.

**Revision**

- La lista ordena primero lo dudoso. Cada fila mueve el playhead del timeline al cuadro
  propuesto, y el usuario lo ve en el visor de NKS. La ventana muestra ese mismo cuadro al lado del
  thumb (o mezclado al 50 %, o como diferencia) con la similitud en vivo; lo decodifica del MOV con
  `ffmpeg_lga.exe` en otro hilo (960 px de ancho, el pedido viejo se descarta si el usuario siguio
  moviendose).
- **No usar `currentViewer().image()` para esto.** Llamada ~90 ms despues de `setTime`, con el
  visor todavia decodificando el cuadro nuevo, tiro abajo NKS 16.0v4 con un access violation
  (medido en una instancia aparte, MOV ProRes en una unidad de red; el volcado de faulthandler
  apunta a esa linea).
- Teclas: flechas, un cuadro; Shift, un segundo; RePag/AvPag, corte anterior/siguiente; 1-5,
  candidatos; Enter, usar este cuadro; N, no esta en el corte; Arriba/Abajo, otra fila. La lista
  no toma el foco para que las flechas sean de la navegacion.
- `Viewer.setSequence` pide dos argumentos en NKS 16 (secuencia e indice de entrada).

**Decisiones guardadas** en `%LOCALAPPDATA%\LGA\HieroTools\ShotMarks_Locate\decisions\<proyecto>.json`,
por sha1 del thumb (no por fila ni por shot: las filas se mueven y los shots se repiten). Cada
confirmacion guarda tambien la huella del cuadro elegido: con un corte nuevo se busca ese cuadro
en lugar del thumb. No se escribe nada en el Excel.

**En la ventanita de Previous/Next Mark** las marcas ubicadas muestran el thumb de la planilla
(JPG de 480 px en la cache, `tag.lga_shotmarks_thumb`) y como se ubico (`_located`): aceptado
solo, confirmado a mano o sin confirmar. El status de omit va en rojo y el de posible omit en
ambar. Con EDL, dos renglones con el clip y el SRC TC IN/OUT (el evento, en el tooltip): en uno
solo, un nombre de clip real (~30 caracteres) partia el SRC TC.

**Filas que no se ubican**: los titulos de grupo (`PROJA_001_`, nombre terminado en `_`, `-` o
`.`) aunque tengan foto. "POSIBLE VFX OMIT (en corte)" no cuenta como omit: sigue en el corte.

**Ruta en la raiz de una unidad**: Hiero devuelve `Y:clip.mov` (sin barra) para un archivo en la
raiz de una unidad. Es una ruta relativa al directorio actual de esa unidad; `media_path` le
agrega la barra antes de pasarla a ffmpeg. Medido en NKS 16.

## Decisiones que no se deducen del codigo

- **Tags y no anotaciones.** Viewer > Next Tag / Previous Tag (`Alt+Shift+Right/Left`) navega los
  tags de rango de la secuencia de forma nativa (medido en NKS 16.0v4: saltos exactos al IN de cada
  tag). Las anotaciones no tienen navegacion nativa en 16.0, cambiaron de sistema en 16.1/17 (ver
  `Docu_Project_Downgrade.md`), y `VideoTrack.addSubTrackItem` corta o borra los subtrack items que
  se solapan en el mismo subtrack, asi que podria pisar anotaciones hechas a mano.
- **Next Tag necesita el foco en el viewer.** Disparada sin foco, la accion no mueve el playhead.
  Para probarla desde afuera hay que activar la ventana, y eso le roba el foco al usuario: no se hace
  en pruebas automaticas; se verifica la posicion de los tags.
- **El REC TC OUT es exclusivo.** En las planillas de montaje el OUT de un shot es el IN del
  siguiente; el tag termina un cuadro antes para que dos shots pegados no se solapen.
- **Contra que TC se mide.** Si el timeline tiene un solo clip habilitado y sin retime (el MOV del
  episodio), el REC TC se mide contra el TC de esa media en el cuadro 0, que es el que se ve quemado
  en la imagen. El TC de la secuencia puede venir distinto: un timeline creado a mano arranca en
  `01:00:00:00` mientras la media arranca en `00:59:50:00` por la cola de 10 s del montaje, y medir
  contra la secuencia corre todas las marcas 240 cuadros. Verificado con deteccion de cortes en la
  media: 11 de 11 cortes caen exactos al cuadro, en dos episodios y hasta el final de cada uno. Con
  varios clips (un corte conformado) el TC de fuente es el de camara, asi que se usa el de la
  secuencia.
- **Alinear el TC del timeline es opcional** y se ofrece solo si difiere del de la media. Cambia lo
  que muestra el timeline y lo que sale en exports y EDL; el mapeo es correcto con o sin alinear.
- **Re-correr reemplaza solo lo propio.** Los tags propios llevan metadata `tag.lga_shotmarks`. La
  key tiene que empezar con `tag.`: si no, `setValue` tira RuntimeError. Una nota agregada a mano a
  un tag propio se pierde al re-correr; los tags hechos a mano no se tocan.
- **Filas raras.** IN = OUT o sin OUT: marca de un cuadro con aviso. Sin TC IN, TC invalido o fuera
  del timeline: no se escribe y se lista en rojo. Shot repetido o solapado: se escribe con aviso.
- **xlsx sin openpyxl.** NKS no lo trae. El xlsx es un zip: se leen `xl/workbook.xml`, sus rels,
  `sharedStrings.xml` y el XML de la hoja con `iterparse`, sin cargar las imagenes. `sharedStrings`
  se lee una sola vez por archivo: releerlo por hoja tardaba 14 s al sugerir la hoja.
- **csv: del `csv.Sniffer` solo se usa el separador.** El Sniffer mira los primeros 4096
  caracteres; si ahi no hay ningun `""`, adivina `doublequote=False`. En una exportacion de Google
  Sheets un brief de varias lineas que empieza con comilla se escribe `"""-Agregado...`, y con esa
  adivinanza la celda se cortaba en la primera linea y el resto se derramaba en filas sueltas (793
  filas en vez de 788). Las comillas se leen siempre como `csv.excel`, que es como escriben Excel
  y Google. Los saltos de linea del brief sobreviven al tag, a la metadata y a guardar el `.hrox`
  (medido en NKS 16): si un brief sale cortado, mirar primero la lectura de la planilla.
- **Episodio.** Excel guarda `101` como `101.0`; se normaliza. Se sugiere el episodio que aparece
  como numero suelto en el nombre del timeline.
- **Frame rate.** Se cuentan cuadros al fps nominal de la secuencia, sin drop-frame.

## Referencias

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Sheet.py`:
  `list_sheets`, `suggest_sheet`, `load_table`, `detect_header_row`, `detect_columns`,
  `parse_timecode`, `build_plan`. Sin host; probado por `tests/test_shot_marks_sheet.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks.py`:
  `TimelineInfo` (TC de secuencia y de media), `own_tags`, `apply_plan`, `guess_episode`,
  `ShotMarksDialog`, `main`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Nav.py`:
  `go_to_mark`, `mark_tags`, `mark_info`, `ShotMarkInfoWindow`, `info_window`. La eleccion del
  salto es `next_mark_index` y la metadata `mark_metadata` / `mark_info_from_metadata`, en el
  nucleo sin host.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel.py`: boton `Shot Marks`,
  `execute_ShotMarks`; Shift+Click de Previous/Next Annotation en `execute_PreviousMark` /
  `execute_NextMark`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Locate_Engine.py`,
  `LGA_NKS_ShotMarks_Locate.py` y `LGA_NKS_ShotMarks_Thumbs.py`: ubicar desde thumbnails. El motor
  y el lector de thumbs se prueban sin host en `tests/test_shot_marks_locate.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_EDL.py`:
  `parse_edl`, `align`, `cut_frames`, `segments`, `segment_at`, `source_info`. El motor lo carga
  por ruta (corre con `-I`) en `load_edl`. Tests: `tests/test_shot_marks_edl.py`.
- Capturas: `+Building_Blocks/UI_Capture/fixtures/h11_shot_marks.py` -> `ShotMarks_Dialog.png`,
  `ShotMarks_Dialog-Thumbnails.png` y `ShotMarks_Dialog-Thumbnails-EDL.png`; `h11b_shot_mark_info.py` -> `ShotMarks_Info.png`,
  `ShotMarks_Info-OldTag.png` y `ShotMarks_Info-Located.png`; `h11c_shot_marks_locate.py` ->
  `ShotMarks_Locate.png`.
