> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios.

# Shot Marks (panel Review)

## Para que existe

Llega un corte bloqueado como un solo MOV del episodio y una planilla de breakdown con un REC TC por
shot. Hace falta ver en el timeline donde cae cada shot con VFX, saltar de uno al siguiente y cruzar
la planilla contra el corte. A mano son cientos de marcas, y hay que rehacerlas en cada update de
planilla o de corte. Shot Marks las pone todas de una vez y, al volver a correrla, reemplaza solo las
suyas y las pinta segun lo que cambio en la planilla desde la corrida anterior.

## Que hace

1. Lee la planilla (`.xlsx`, `.csv` o un link de Google Sheets, ver abajo) fuera del hilo de UI y
   sugiere la hoja con columnas de shot y REC TC (en un archivo de 55 hojas tarda ~1,5 s).
2. Detecta la fila de encabezado (puede no ser la primera: suele haber una tablita de resumen arriba)
   y las columnas de shot, TC IN, TC OUT, episodio, status, brief, descripcion, escena, vendor,
   categoria, dificultad, Notes y Notes 2. Todo se puede corregir en la
   ventana y queda guardado en `%APPDATA%\LGA\HieroTools\ShotMarks.ini`. Un encabezado con salto
   de linea en la celda (`STATUS` / `VFX`) se lee en una linea (`STATUS VFX`): con el salto, el
   combo lo mostraba en dos renglones cortados.
3. Prueba en seco en vivo: cuantas marcas, cuantas Omit salteadas, cuales no se pueden ubicar y por
   que. El log de cada corrida va a `LGA_NKS_Review_Panel_py/logs/DebugPy_LGA_NKS_ShotMarks.log`.
4. Al aplicar, en un solo undo: borra los tags que puso antes, opcionalmente alinea el TC de inicio
   del timeline y crea un tag de rango por shot (`Sequence.addTagToRange`), con el shot como nombre y
   el brief como nota.

## El dialogo: ajustes a la izquierda, vista previa a la derecha

**Por que tiene esta forma.** Hasta la `v1.10` era una grilla de doce combos con el mismo peso, un
parrafo de instrucciones arriba, otro de estado abajo y una tabla que en el modo thumbnails quedaba
vacia. Lo que se mira al correrla es la vista previa (que marcas se escriben, que cambio, que no se
puede ubicar); las columnas casi siempre se detectan bien solas. Por eso la vista previa ocupa la
ventana y los ajustes van en una columna angosta (`SIDE_WIDTH`, con scroll si se despliega todo).
La ventana se puede agrandar y la tabla se estira. Se eligio entre tres prototipos renderizados.

**Izquierda.**
- *Source*: switch **Google Sheet / File** (cambia el campo de entrada, no la planilla cargada). En
  Google se pega el link y Enter; en File, Browse o una ruta y Enter. Despues de cargar, el campo
  queda libre para pegar otra y arriba, en una **tarjeta**, se ve el **nombre** de la planilla (titulo
  de Google o archivo), con el link o la ruta completa en su tooltip: en esa columna un link no entra.
  Debajo, una linea de estado (`source_note`) con un punto de color: verde al dia, ambar si se uso la
  copia sin conexion, gris bajando o archivo local, rojo si fallo; la fecha va corta (`Nov 3, 10:40`,
  meses escritos en el codigo y no con `%b`, que sale en el idioma del sistema). El boton de la
  flecha circular recarga: vuelve a consultar Google (`fetch`, que baja solo si cambio) o relee el
  archivo, conservando la hoja elegida.
- *Columns*: solo **Shot, TC In y TC Out** a la vista. Las diez de datos (episodio, status, brief,
  Notes, Notes 2, descripcion, escena, vendor, categoria, dificultad) se despliegan dentro de la misma
  ventana con la fila plegable **Mark window columns** (a la derecha, cuantas hay asignadas: `6 of
  10`), sin dialogos nuevos ni popups. Si falta una
  imprescindible, su rotulo va en rojo con el aviso abajo; si el combo cayo en la primera columna
  porque ninguna se llamaba como se esperaba, en amarillo hasta que se elija a mano.
- *Timeline*: **Measure** dice solo Media / Timeline timecode; el inicio y el clip van en una linea
  gris debajo, cortada con `...` si no entra (el nombre del clip tiene ~60 caracteres y dentro del
  combo quedaba cortado a la mitad). Abajo, alinear el inicio del timeline, episodio y Skip omitted.
- **Forma de la columna**: cada seccion es una grilla de rotulo gris + campo con el mismo ancho de
  rotulo (`COLUMN_LABEL_WIDTH`) y el mismo aire (`ROW_GAP`, `SECTION_GAP`), separada de la
  siguiente por una linea. Antes la fila de Sheet y la grilla de columnas usaban espaciados distintos
  y sus campos no arrancaban en la misma vertical. Los combos sin datos quedan apagados hasta que
  hay planilla. Con la ventana en 1120 x 740 la columna entra sin scroll; con las columnas de datos
  desplegadas aparece el scroll del pack.

**Derecha**, en tres paginas (`QStackedWidget`):
- *Mensaje*: sin planilla ("Nothing to preview yet" y que va a aparecer), leyendo, bajando de Google
  (con los segundos que lleva) o un error en rojo, como el de sin conexion.
- *Plan*: el numero de marcas en grande, la leyenda con la cuenta de cada color (solo si hay corrida
  anterior), una linea con lo demas (omitidas, otros episodios, no escritas, avisos, comentarios) y la
  tabla de siempre. El filtro **All / Changes / Problems** filtra la tabla de verdad: Changes son
  amarillas, naranjas y rojas; Problems, las filas que no se escriben, las que se escriben con aviso y
  las rojas que siguen en la planilla pero no se ubicaron. Las filas, su orden y el filtro salen de
  `LGA_NKS_ShotMarks_Preview.py`, sin host y con tests; el dialogo solo pone los colores.
- *Thumbnails*: cuantos shots hay para ubicar, una grilla con las primeras fotos de la planilla (shot
  y fila; la ultima celda dice cuantas quedan afuera), el EDL y el boton **Locate N Shots...**. Las
  fotos se extraen en un hilo con `extract_thumbs` a la misma cache que usa Locate
  (`ShotMarks_Locate\thumbs_src`, por sha1) y se escalan como `QImage` fuera del hilo de UI; el
  `QPixmap` se arma recien en el hilo de UI.

Volviendo de Locate (preset), la fuente queda fija: sin campo de entrada ni Reload, y el boton pasa a
Add / Update Marks con los TC ubicados. Los tooltips son los propios del pack (`set_custom_tooltip`),
en castellano, desde el dict `TOOLTIPS`.

## Planilla desde un link de Google Sheets

Los breakdowns suelen vivir en Google Sheets y cambian todos los dias: bajarlos a Excel en cada update
era un paso a mano que se olvidaba. El campo de la planilla acepta, ademas de un archivo, el link de un
Google Sheet (pegar y Enter). `LGA_NKS_ShotMarks_Google.py` (sin host, solo libreria estandar) lo baja
como `.xlsx` a `%LOCALAPPDATA%\LGA\HieroTools\ShotMarks_Google\<id>.xlsx` y el resto de Shot Marks lee
esa copia como cualquier Excel: hojas, comentarios en hilo y fotos ancladas viajan en el xlsx.

- **Permiso.** Cliente OAuth de escritorio de Google en `~/.lga-keys/google-oauth.env`
  (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`; las variables de entorno ganan). La primera
  vez abre el navegador por defecto para el login (`drive.readonly`, PKCE, callback en `127.0.0.1`) y
  guarda el refresh token en `~/.lga-keys/google-oauth-token.env`; despues se renueva solo (~0,2 s).
  Por ahora es solo para la maquina de Lega: en otra maquina sin esos archivos el switch Google Sheet
  no aparece (`available()`), la fuente es un archivo, y un link pegado igual dice que falta el cliente. Una API key no sirve: solo abre datos publicos, y los breakdowns se comparten por cuenta.
- **No usar `files.export` de la API.** Tiene un tope de 10 MB y una planilla con fotos lo pasa: medido,
  `403 exportSizeLimitExceeded` con una de 51 MB. Se usa el `exportLinks` de xlsx con el token, que
  redirige a `doc-NN-NN-sheets.googleusercontent.com` y no tiene tope (51 MB en 12 s, ~10 s de esos
  esperando a que Google arme el archivo).
- **Cache por fecha.** Antes de bajar se pide `modifiedTime` (0,4 s); si es la misma de la copia, no se
  baja. Sin conexion y con copia, se usa la copia y el dialogo lo avisa en ambar.
- **Reintentos.** Ante un error de conexion cada pedido se reintenta 3 veces, con 5 s entre intentos:
  un firewall por aplicacion sin driver (GateBouncer, en la maquina de Lega) pierde el primer intento a
  cada IP nueva aunque ya haya regla, y Google rota las IP del servidor de descarga. Con 2 s entre
  intentos, en NKS los 4 caian dentro del bloqueo. Los errores HTTP no se reintentan.
- **Origen de la marca.** `tag.lga_shotmarks_source` lleva el titulo de Google con `(Google Sheets)` y
  la hoja; la carpeta de thumbs junto al `.hrox` toma el titulo (`safe_name`), no el id de la cache.
  `ShotMarks.ini` recuerda el link como `last_file`: al reabrir el dialogo vuelve a consultar a Google.

## Brief numerado

Un brief de varios renglones es una lista de pedidos. Al armar el plan, cada renglon con texto
lleva su numero (`1. ...`, `2. ...`, `numbered_brief` del `_Sheet v1.15`): se lee de un vistazo y
se puede nombrar un pedido ("el 3"). La marca que traiga el renglon (`- `, `-`, una vineta o una
numeracion `1. ` / `1) ` previa) se reemplaza por el numero, asi numerar dos veces da lo mismo. Un
guion en medio del renglon no se toca. Los renglones vacios separan grupos (`dudas:`, `wishlist:`)
y quedan sin numero. Un brief de un solo renglon queda como esta: no es una lista. Va numerado a
la nota del tag y a `_brief`; la planilla no se toca.

En la ventanita (`_Nav v1.11`, `_brief_html`) cada item es un parrafo con `BRIEF_ITEM_GAP` (5 px) de
aire arriba, menos que media linea, y el numero va en `Color.TEXT_MARKER`, un escalon mas claro que
el texto y mas oscuro que el titulo Brief. El parrafo y su margen salen del rich text del QLabel
(`<p style="margin-top">`); con `<br>` no hay forma de separar un item del otro.

## Notes y Budget Alternative

Notas eventuales del shot: no son el brief (el trabajo) ni la descripcion (que pasa en el plano),
sino lo que hay que mirar con atencion ("maybe wishlist", "no tocar los arboles", "omit vfx"). Por eso
la ventanita de la marca las pone arriba de todo, cada una en una caja con borde de color: Notes en
ambar y Budget Alternative en celeste (`NOTE_SECTIONS` del Nav). Sin texto, la caja se reemplaza por
una punteada para agregarla (ver «Cambios locales desde la ventanita»).

- **Budget Alternative** se llamaba Notes 2 hasta la `_Nav v1.13` / dialogo `v1.12`. La columna
  (`Alternativa`, «Alternativas para reduccion de presupuesto») anota que se podria dejar de hacer, o
  como hacerlo de otra forma, para bajar el costo del plano. En el dialogo el rotulo es
  `Alternative`: el nombre entero no entra en el ancho de rotulo de la columna de ajustes (74 px), y
  ensancharlo le quitaba lugar a todos los combos. Por dentro el rol sigue siendo `notes2`
  (metadata `_notes2`): renombrarlo dejaba sin dato a las marcas ya escritas.
- Se sugieren solas: Notes con `Notas` / `Notes` / `Nota` / `VFX Notes` (`NOTES_HEADERS`); Budget
  Alternative con `Alternativa(s)` / `Alternative(s)` / `Notes 2` / `Budget Alternative`
  (`NOTES2_HEADERS`) y, si ningun nombre coincide entero, con la primera columna que contenga
  `alternativ` (`PARTIAL_HEADERS`, `_Sheet v1.18`). No se busca `presupuesto` suelto: una columna
  Presupuesto con montos no es la alternativa.
- Hasta la `_Sheet v1.08`, `Notas` caia en el brief si la planilla no tenia columna `Brief`. Ahora el
  brief solo se sugiere con `Brief` / `VFX Brief`.
- Viajan a la metadata (`_notes`, `_notes2`), cuentan como cambio (amarillo) y Find las busca.
- Los `Vendor Notes` o `On Set sup Notes` no se toman: el nombre tiene que ser exacto.

## Dificultad

Cuanto cuesta cada shot es lo primero que se mira al repartir trabajo, y en la planilla esta en una
columna que la ventana de la marca no mostraba. Rol `difficulty` (`_Sheet v1.17`): se sugiere con
`Dificultad` / `Difficulty` / `Complejidad` / `Complexity` (`DIFFICULTY_HEADERS`) y en el dialogo
va entre las columnas de «Mark window».

- `difficulty_level` lleva el texto a un nivel de 1 a 5 (`DIFFICULTY_LEVELS`), sin mayusculas ni
  acentos: very easy / muy facil, easy / facil, mid / medium / media, hard / dificil, very hard / muy
  dificil, o un numero suelto de 1 a 5. Medido en una planilla real: Very Easy 22, Easy 255, mid 365,
  hard 157, Very hard 15, con mayusculas mezcladas.
- La ventana de la marca (`_Nav v1.12`, `DIFFICULTY_COLORS`) la pone despues del status, con un punto
  y el texto en el color del nivel, de verde agua (1) a rojo (5). Un valor que no es un nivel conocido
  va como texto comun: no se adivina.
- Cuenta como cambio (amarillo) y Find la busca. Las marcas de antes de la v1.17 guardan en `_compared`
  la lista sin `difficulty`, asi que la primera corrida nueva no las pinta por la dificultad.

## Cambios locales desde la ventanita

Al revisar el corte las correcciones aparecen mirando el shot: subir la dificultad, ajustar una nota,
proponer una alternativa mas barata, dejar una pregunta. Abrir la planilla para cada una corta la
revision, y escribirle desde NKS podria pisar lo que otra persona esta cambiando en ese momento. Por
eso la ventanita (`_Nav v1.13`) guarda esos cambios en un archivo local y nunca toca la planilla ni
el tag.

- **Que se cambia.** La dificultad, con cinco pildoras siempre a la vista (`DifficultyStrip`,
  dibujadas a mano porque el color es dato): un click la cambia y la de borde punteado es la que dice
  la planilla. Notes y Budget Alternative: click en el texto (o en la caja punteada `+ Add ...`) abre
  un editor con Save / Cancel / Use Sheet Value; Ctrl+Enter guarda, Esc cancela. Preguntas: un campo
  al pie, Enter la guarda y la `x` la borra.
- **Donde.** `LGA_NKS_ShotMarks_Edits` (sin host): `<carpeta del .hrox>/<proyecto sin
  version>_ShotMarks_Edits.json`, uno por proyecto, asi el cambio se ve en todos los timelines del
  proyecto que tengan ese shot y sobrevive al pasar de v10 a v11. Sin `.hrox` guardado, en
  `%LOCALAPPDATA%/LGA/HieroTools/ShotMarks_Edits`.
- **Un cambio por shot y campo.** Guarda el valor que tenia la planilla al hacerlo (`before`); editar
  de nuevo conserva ese valor, y volver al de la planilla borra el cambio. La ortografia de la
  dificultad sale de las marcas del timeline (`mid`, `Very hard`), para pegarla igual en la planilla.
- **Como se ve.** El valor cambiado reemplaza al de la marca, con la etiqueta EDITED y debajo «In the
  sheet: ...». Si la planilla cambio despues del cambio local (la marca ya no dice el `before`), un
  aviso ambar: hay que decidir a mano. El pie dice cuantos cambios pendientes tiene el proyecto.
- **Export Changes...** baja los pendientes a un CSV (UTF-8 con BOM: Excel lo abre con acentos y
  Google Sheets lo importa) con shot, fila, campo, valor de la planilla al cambiar, valor nuevo, lo
  que dice la marca ahora, autor y fecha. Es la base para pasarlos a la planilla revisando uno por
  uno; esa herramienta es el paso siguiente.
- **Cierre solo.** Cuando la planilla ya tiene el valor nuevo y se vuelve a correr Shot Marks, la
  ventanita lo detecta al mostrar el shot y lo marca `applied` (queda como historial en el archivo).
  Las preguntas no se pueden detectar asi: se borran a mano o las cerrara la herramienta de pase.
- **Foco.** La ventana se sigue mostrando sin activarse; toma el teclado recien con el click para
  escribir y, al guardar o cancelar, se lo devuelve a NKS. Mientras se escribe no sigue al playhead
  (se guardaria en otro shot); Previous / Next guardan lo escrito antes de saltar.
- Medido en NKS 17 con 640 marcas: leer las dificultades del timeline 6 ms, dibujar la ficha 16 ms.

## Comentarios de la planilla

Las consultas que se dejan en la planilla (comentarios de Google Sheets o de Excel) van a la ventana
de la marca de su shot, en la seccion Comments: autor, fecha, columna donde se dejo, texto y
respuestas. Los resueltos van enteros en gris; el titulo dice cuantos siguen abiertos. Sin
comentarios en la fila, la seccion no aparece. Find tambien busca en ellos.

- **Viajan al xlsx.** Medido en una planilla bajada de Google Drive como `.xlsx`: los hilos (autor,
  fecha, menciones, respuestas con `parentId`, `done="1"` si esta resuelto) van en
  `xl/threadedComments/threadedComment<N>.xml`, los autores en `xl/persons/person.xml`, y cada hoja
  los apunta desde `xl/worksheets/_rels/sheet<N>.xml.rels`. La celda va en `ref` (`E611`): de ahi
  sale la fila, y por la fila, el shot. El `.csv` no trae comentarios.
- **Que se toma** (`read_comments`): los hilos, y de `xl/comments<N>.xml` solo las notas con autor
  (las de Excel). Ahi Google deja un espejo de cada hilo con autor `tc={id}` (se descarta: ya esta en
  el hilo) y sus "notas" de celda sin autor. Esas se descartan a proposito: en la planilla medida eran
  39 copias de un mismo rotulo de costos y aparecian en 39 tarjetas.
- **Comentarios fuera de las filas de shot** (el encabezado, una fila de resumen) no van a ninguna
  marca. El resumen del dialogo los cuenta: "2 comments ... go to the mark window of their shots
  (3 on other rows are not shown)".
- Viajan a la metadata como JSON (`_comments`, con la columna por nombre). **No cuentan como cambio**
  de planilla: un comentario nuevo o resuelto no pinta la marca de amarillo.
- Se leen junto con la hoja, fuera del hilo de UI: medido 0,5 s en una planilla de 845 filas.

## Actualizar: colores contra la corrida anterior

Llega una planilla nueva y lo que importa es que cambio. Si el timeline ya tiene marcas de Shot Marks,
la corrida compara por nombre de shot (`compare_marks`, en el nucleo sin host) y cada tag toma un
icono del bin Markers de los Tag Presets de NKS (`icons:TagGreen.png`, etc.):

| Color | Cuando |
|---|---|
| Verde | El shot sigue y sus datos de planilla son iguales. Moverse en el corte NO es un cambio. |
| Amarillo | Cambio el brief, la descripcion, Notes, Notes 2, el status, la escena, el vendor, la categoria o la dificultad (`CHANGE_FIELDS`). |
| Naranja | Shot nuevo: no tenia marca en la corrida anterior. |
| Rojo | Tenia marca y ahora no: ya no esta en la planilla, o esta pero no se ubica en este timeline. |

- **Las rojas se recrean en su lugar de antes**, con su metadata, para que se vea que se fueron. Si
  el shot sigue en la planilla y no se ubico (por ejemplo `Outside the timeline`: la planilla ya trae
  los TC de un corte mas largo), la marca guarda el motivo y la ventanita lo dice. Medido en un
  episodio: de 32 rojas, 24 eran eso y no shots borrados.
- **Las rojas viven una corrida.** La siguiente no las compara y las borra; si el shot vuelve, es
  naranja. Si no, se acumularian para siempre.
- **Una roja que caeria encima de una marca nueva no se crea** (`drop_covered_removed`,
  `ShotMarks v1.08`). Casi siempre es el mismo plano con otro nombre: medido con una planilla
  renumerada, quedaban 231 rojas con el nombre viejo encima de las marcas con el nuevo, dos tags por
  plano. El log las lista.
- **La comparacion es contra la corrida anterior, no contra la primera.** Un amarillo que se vuelve a
  correr con la misma planilla pasa a verde.
- Sin corrida anterior no hay contra que comparar: icono comun, sin columna Change.
- **Se compara texto normalizado**: fin de linea (`\r\n`), espacios al borde de cada renglon y
  marcas de lista (guion, vineta o numero al principio del renglon) no cuentan: numerar el brief no
  pinta de amarillo las marcas de una corrida anterior sin numerar. Comillas si: arreglar las
  comillas de un brief es un cambio real del texto.
- Los tags de la v1.00 no guardaban columnas: de esos solo se compara el brief (la nota).
- **Solo se comparan los campos que la corrida anterior guardaba.** Cada marca guarda en `_compared`
  la lista de `CHANGE_FIELDS` de esa version. Sin eso, al sumar Notes, la primera corrida nueva
  habria pintado de amarillo cada shot con una nota ("Notes (was empty)"). Las marcas sin `_compared`
  (hasta la `_Sheet v1.08`) comparan `LEGACY_CHANGE_FIELDS`.
- **Antes de borrar se pregunta** (`ask_question`), con la cuenta de cada color. La vista previa suma la
  columna Change y pone arriba los rojos, amarillos y naranjas.
- Metadata nueva del tag: `_change`, `_changed` (campos separados por coma), `_prev_<campo>` con el
  texto anterior de cada campo que cambio y `_change_reason` en las rojas no ubicadas.
- **`hiero.core.Tag(nombre)` nace con la metadata de un tag que ya existio con ese nombre** (medido en
  NKS 16: un tag nuevo traia el `_prev_brief` de dos corridas antes; con otro nombre nace solo con
  `tag.label`). `DataCollection` no tiene `removeKey`, asi que `_add_tag` vacia las keys propias que
  esta corrida no escribe. Sin eso, un status o un vendor borrados en la planilla seguian apareciendo
  en la ventanita. Vaciar keys no rompe el undo: medido, deshacer deja la metadata identica.

Verificado en NKS 16 sobre una copia del proyecto y de la planilla, con cambios hechos a mano en la
copia: descripcion y brief cambiados (amarillo), un TC corrido 10 cuadros (verde, en su lugar nuevo),
un shot renombrado (rojo el viejo, naranja el nuevo) y una fila borrada (rojo). Una tercera corrida con
la misma planilla dejo todo verde y borro las rojas.

## Previous / Next Mark

Click en Previous Mark / Next Mark del panel Review (con Shift+Click esos botones navegan las
anotaciones del clip: hasta la v2.89 del panel era al reves y se llamaban Previous / Next
Annotation, pero las marcas se usan mucho mas). Salta el playhead al IN de la marca anterior o siguiente del
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
- **Cambio contra la corrida anterior.** Una linea en el color del tag: sin cambios, nuevo, que
  campos cambiaron (los cortos con su valor anterior: `Status (was WIP)`), o por que una roja no esta.
  Si cambio la descripcion, el brief o una nota, el texto anterior va debajo, en gris
  (`Before: ...`). Si la nota se borro, su caja no aparece y el texto anterior va en esta linea.
- **Notes y Notes 2 resaltadas.** Arriba de la descripcion, en cajas con borde ambar y celeste;
  ver "Notes y Notes 2". Debajo, los comentarios de la planilla (ver "Comentarios de la planilla").
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
  (`tag.lga_shotmarks_tc_in`, `_tc_out`, `_brief`, `_description`, `_notes`, `_notes2`, `_status`,
  `_vendor`, `_scene`, `_category`, `_episode`). Releer el Excel tardaria medio segundo por salto y fallaria
  si la planilla se mueve. Los tags creados antes de esta version solo tienen nombre y nota: la
  ventana muestra eso y pide volver a correr Shot Marks.

## Find Shot Mark

Shift+Click en Shot Marks. Con cientos de marcas, Previous / Next no sirve para ir a un shot puntual
ni a "el del humo de la sopa". Una ventanita con un campo: se escribe un nombre de shot o cualquier
texto de la planilla y Find salta a esa marca, mostrandola en la ventanita de Previous / Next Mark.

- **Donde busca.** En la metadata de los tags (`mark_info_from_metadata`), no en el Excel: shot,
  descripcion, brief, Notes, Notes 2, comentarios (autor y texto), status, vendor, escena, categoria, episodio, TC IN/OUT y clip
  (`SEARCH_FIELDS`). No pide el color del vendor a la DB de PipeSync (lo hace `mark_info` del Nav
  solo para la marca que se muestra): buscar es instantaneo aunque el timeline tenga cientos.
- **Como compara.** Sin mayusculas ni acentos y con los espacios unidos (`search_text`): un brief
  de varias lineas se encuentra escribiendo un espacio donde hay un salto. El estado dice en que
  campo aparecio si no fue el nombre del shot.
- **Find** salta al shot que se llama exactamente asi; si no hay, al primer resultado del timeline.
  Asi `PROJA_010_0100` no cae en `PROJA_010_01000` ni en un brief que lo nombre.
- **Next** sigue desde el ultimo resultado mientras el playhead siga en su IN (dos marcas pueden
  empezar en el mismo cuadro); si el usuario movio el playhead, desde el playhead. Despues del
  ultimo vuelve al primero y lo avisa. Enter con el mismo texto es Next; con texto nuevo, Find.
- **Siempre arriba** (`Keep this window on top`, prendido por defecto, en
  `%APPDATA%\LGA\HieroTools\ShotMarksFind.ini`), con el mismo mecanismo que el Flow Pull: en
  Windows `SetWindowPos` con `HWND_TOPMOST`, que cambia solo el z-order. Hornear
  `WindowStaysOnTopHint` en los flags y cambiarlo despues recrea la ventana nativa (parpadeo); se
  usa solo fuera de Windows. Se aplica con `singleShot(0)` despues del `show`, porque Qt
  reposiciona la ventana al mostrarla y pisa el topmost. `argtypes` declarados: sin ellos ctypes
  trunca el HWND de 64 bits.
- **INI propio y no `ShotMarks.ini`**: el dialogo de Shot Marks reescribe ese archivo entero con su
  seccion y se llevaria cualquier otra.
- Una sola ventana, buscada por `objectName` (`LGA_ShotMarkFind`) como la de info. Al abrirse si
  toma el foco (es para escribir) y queda a la derecha de la ventanita de info, sin taparla; los
  saltos no se lo sacan, porque la de info se muestra sin activarse. Esc la cierra.

## Planillas sin timecode: ubicar desde los thumbnails (solo Windows)

Hay breakdowns que no traen REC TC: solo una foto por shot, pegada en la hoja. Si la hoja elegida
no tiene columna de TC pero sus filas de shot tienen imagen, la vista previa muestra sus fotos y el
boton del dialogo pasa a **Locate N Shots...**, que abre **Locate from Thumbnails**: busca cada
foto en el MOV del timeline y marca el plano que la
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
   **El orden gana** (`choose_candidates`, desde `_Locate_Engine v1.02`):
   - Un ancla que cae fuera de orden se vuelve a buscar entre sus vecinas, y si ahi da casi lo
     mismo (`ORDER_TOLERANCE` 0,05) queda ahi. Medido: una imagen repetida en la pelicula
     (flashback) empataba exacto (0,904 y 0,904) con su gemelo una hora y media despues; el margen
     solo mira planos cercanos, asi que el gemelo no la hacia dudosa, y quedaba lejos.
   - Fuera de orden solo gana un parecido fuerte (>= 0,90) y claramente mejor. Un 0,66 lejano le
     ganaba a un 0,47 entre las vecinas: si ninguno es bueno, el plano casi seguro esta en orden
     (otra toma u otro encuadre que el de la foto), y la fila queda ahi, en revision.
   - Lo que esta a menos de 2400 cuadros de la ventana compite como si estuviera adentro: dentro de
     una escena los planos a veces se reordenan unos segundos. El margen se mide como antes contra
     la ventana, para que un plano parecido de la escena, justo afuera, no vuelva dudosa a una
     automatica.
   - Los candidatos (botones 1-5 de la revision) traen al final el mejor de la otra busqueda, y la
     nota de la fila dice cual es.
   Medido sobre una corrida real de 437 filas: fuera de orden 60 -> 2; a revisar entre sus vecinas
   75 de 105 -> 87 de 100; 5 filas pasan a automaticas (en orden, >= 0,99) y ninguna automatica
   pasa a revision.
5. **Dos shots distintos no pueden caer en el mismo plano**: el de menor puntaje pasa a revision.
6. **Cuadro exacto**: a 32x18 los cuadros vecinos de un plano empatan; se decodifican +-24
   cuadros a 192x104 y se elige el mejor (~0,4 s por shot, en paralelo).
7. **IN/OUT**: el plano del EDL que contiene el cuadro (ver abajo). Sin EDL, el plano entre los
   cortes de `scdet` (picos locales con puntaje > 6; de dos detecciones a menos de 3 cuadros
   queda la mas fuerte), y un "plano" de mas de 60 s es un encadenado o un corte que no se vio:
   el motor deja la marca en el cuadro del thumb, y al pasar los TC (Use Timecodes) se le da un
   tramo: ver "Marcas sin superponerse".

**Niveles**: `auto` (aceptado solo), `review` (puntaje >= 0,60 sin las condiciones de `auto`),
`not_found`; y los que pone el usuario: `confirmed` y `not_in_cut`. Los seguros se aceptan solos
desde la primera corrida; los `review` se marcan igual, como no confirmados.

**Lo que ningun metodo por imagen resuelve**: una captura de dailies de un cuadro que no esta en
el corte (otra toma, otro tramo de la toma). Medido: esos dan 0,73-0,77 aunque sea la escena
correcta; cuando el cuadro de una captura de dailies si esta en el corte da >= 0,88. Por eso van a
revision y nunca se aceptan solos. El EDL no lo resuelve: la planilla no trae el clip de camara
de cada foto (su "Shooting name" es escena_plano_toma, no el nombre del clip), asi que no hay con
que cruzar el SRC TC.

**El TC de los cuadros ubicados es el del clip segun NKS, no el del archivo.** El motor trabaja en
cuadros del archivo; la ventana los pasa a TC con `clip.timecodeStart()` (`TimelineInfo.media_tc`),
que es el mismo TC que resta el plan. Hasta `_Locate v1.01` usaba el que lee ffprobe del archivo, y
no siempre coinciden: medido en NKS 17 con un MP4 de TC 00:59:50:00 que NKS mostraba en 00:00:00:00,
todas las marcas caian 86160 cuadros mas adelante (o fuera del timeline). Con el de NKS, las 336
marcas de esa corrida caen en su cuadro. Si difieren, el log de Locate lo avisa.

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
- **Tira de planos entre vecinas** (`_Locate v1.03`, `strip_shots` en `_Sheet v1.11`): debajo de
  la comparacion, un cuadro por plano desde la fila ubicada anterior (auto o confirmada, celeste)
  hasta la siguiente (violeta), fijas en los extremos; los planos del medio se desplazan si no
  entran (hasta 24, los del centro se omiten y se cuentan). El plano donde cae hoy la fila va en
  ambar y el del visor con borde grueso; click lleva el visor a ese plano. Existe porque los
  dudosos de verdad son fotos de otra toma o de otro encuadre: el cuadro no esta en el corte y
  ningun puntaje sube, pero el plano casi siempre esta entre las vecinas, y verlos todos juntos es
  mas rapido que ir cuadro a cuadro. Medido en una corrida real: entre las vecinas de una fila de
  0,47 hay 7 planos de la misma escena, y el correcto se reconoce a ojo.
- **Un histograma de color no ayuda a elegir entre esos planos.** Medido sobre cuatro filas: entre
  las vecinas todos dan 0,52-0,72, y en una fila el plano correcto (las mismas actrices) dio el
  valor mas bajo. Por eso la tira no ordena ni marca un favorito.
- **Revisar no escribe nada en el timeline.** Las confirmaciones se guardan al momento, pero las
  marcas se escriben recien con Use Timecodes (que reabre Shot Marks con los TC ubicados) y el
  Update de ese dialogo. Paso en uso real: con la revision terminada y la lista vacia parecia el
  final, y el timeline seguia con las marcas viejas. Por eso las instrucciones nombran el ultimo
  paso y, sin dudosos, el resumen de abajo dice que hay que apretar Use Timecodes (`_Locate v1.04`).
- Teclas: flechas, un cuadro; Shift, un segundo; RePag/AvPag, corte anterior/siguiente; 1-5,
  candidatos; Enter, usar este cuadro; N, no esta en el corte; Arriba/Abajo, otra fila. La lista
  no toma el foco para que las flechas sean de la navegacion.
- `Viewer.setSequence` pide dos argumentos en NKS 16 (secuencia e indice de entrada).

**Decisiones guardadas** en `%LOCALAPPDATA%\LGA\HieroTools\ShotMarks_Locate\decisions\<proyecto>.json`,
con el nombre del proyecto **sin version** (`decisions_base`: `PROJA_Spotting_v05` -> `PROJA_Spotting`).
Hasta `_Locate v1.06` llevaba la version, y al guardar el proyecto como v05 Locate buscaba un archivo
nuevo: se perdian todas las confirmaciones a mano. `load_decisions` suma primero los archivos viejos
con version del mismo proyecto y el sin version manda. La clave es **la foto y el shot**
(`decision_key`: `sha1|shot`), no la fila (las filas se mueven). Hasta `_Sheet v1.12` era solo la
foto, y una planilla que repite la foto en shots distintos (la del plano de dos para el
contraplano) mandaba a todos al cuadro que se confirmo para uno: medido, seis shots de una pelea en
el mismo cuadro. Las decisiones viejas por foto valen si esa foto es de un solo shot; si la comparten
varios se ignoran (`find_decision`). Cada confirmacion guarda tambien la huella del cuadro elegido:
con un corte nuevo se busca ese cuadro en lugar del thumb. No se escribe nada en el Excel.

**Una decision por corte** (`_Sheet v1.16`, `_Locate v1.07`, `_Locate_Engine v1.04`). Un mismo proyecto
puede tener dos cortes de la pelicula (un timeline por armado) y el archivo de decisiones es uno por
proyecto: con una sola clave por foto y shot, revisar el corte nuevo borraba lo confirmado en el
anterior. `store_decision` guarda cada decision dos veces: en `sha1|shot@<video_key>` (la de ese corte)
y en `sha1|shot` (la ultima, que con un corte que todavia no tiene decision propia sirve de huella para
re-buscar). Antes de pisar `sha1|shot`, si ahi habia una de otro video sin su clave propia, la pasa a
`sha1|shot@<ese video>`. El motor pide primero la del video que esta ubicando (`find_decision(..., video)`).
Los archivos viejos siguen valiendo: sin clave por video se usa la sin video, como antes.

**Marcas sin superponerse** (`_Sheet v1.13`, `_Locate v1.06`). Medido en un largo de 654 filas: 36
grupos de marcas superpuestas. Ademas de la clave por foto y shot:

- **Fila repetida = una marca.** La planilla repite filas enteras (mismo shot, misma foto); `build_plan`
  no escribe la segunda si cae en el mismo rango ("Repeated row"). Un shot repetido con otra foto y
  en otro lugar si lleva su propia marca.
- **Plano que comparten dos shots distintos** (`split_shared_ranges`, al pasar los TC): `scdet` no vio
  el corte entre ellos (medido: picos de 4,6-5,9 contra el umbral de 6) y los dos quedaban de corte a
  corte del mismo "plano". Se recortan a su tramo entre los picos >= `SOFT_CUT_SCORE` (3,0) de
  `scd.bin`, y si siguen juntos se parten en el pico mas fuerte entre sus cuadros.
- **Marca en un "plano" de mas de 60 s** (`soft_shot_range`): antes quedaba de un cuadro. Va del pico
  >= 3,0 anterior a su cuadro al siguiente; sin ningun pico en el plano es una toma larga y lleva el
  plano entero. Medido en un largo: un plano secuencia de 285 s no pasa de 1,2 en todo el plano,
  y una escena oscura de 177 s tiene 28 picos de 3,1-5,1, cortes reales entre planos de la misma luz.

**En la ventanita de Previous/Next Mark** las marcas ubicadas muestran el thumb de la planilla
(JPG de 480 px, `tag.lga_shotmarks_thumb`) y como se ubico (`_located`): aceptado
solo, confirmado a mano o sin confirmar. El status de omit va en rojo y el de posible omit en
ambar. Con EDL, dos renglones con el clip y el SRC TC IN/OUT (el evento, en el tooltip): en uno
solo, un nombre de clip real (~30 caracteres) partia el SRC TC.

**Los thumbs viajan con el proyecto** (`ShotMarks v1.09`, `_Sheet v1.14`, `_Nav v1.10`). Al
aplicar marcas ubicadas desde thumbnails, cada JPG se copia a una subcarpeta junto al `.hrox` con
el nombre de la planilla (`T:\VFX-PROJA\PROJA_SUP\PROJA_Sheet_v02\<sha1>_480.jpg`, en un hilo:
a una unidad de red son segundos) y el tag guarda la ruta relativa (`PROJA_Sheet_v02/<sha1>_480.jpg`).
Antes guardaba la absoluta de la cache de Locate de esta maquina: se perdia al limpiar la cache o
al abrir el proyecto en otra maquina. Con el proyecto sin guardar no hay carpeta y queda la de la
cache. La ventanita resuelve el thumb con `resolve_thumb`: relativo a la carpeta del proyecto y,
si no esta, por nombre en la cache de Locate (marcas viejas). **Una ruta relativa nunca se abre
tal cual**: `QImage` la resuelve contra el directorio actual de NKS, que depende de como se abrio
(con los launchers del dev-link es `DevLink_Studio`), y el thumb aparecia o no segun eso.

**Columna de shot con dos candidatas** (`_Sheet v1.12`, `ShotMarks v1.07`): una planilla puede traer
"SHOT NAME" y "VFX SHOT NAME". Se elige la que tiene mas nombres de shot completos
(`shot_name_count`), y esa le gana tambien a la columna recordada de la corrida anterior si la
recordada tiene menos. Medido en una planilla renumerada: "SHOT NAME" guardaba los nombres viejos
(547 completos, 290 filas como `PROJA_002_`) y "VFX SHOT NAME" los nuevos (842). Con "SHOT NAME",
esas 290 filas se tomaban por titulos de grupo y no se marcaban, y las demas quedaban con el
nombre viejo. El log de Locate anota cada fila sin nombre completo y su status.

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
  un tag propio se pierde al re-correr; los tags hechos a mano no se tocan. Que se pinta de cada
  color: seccion "Actualizar".
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
  `parse_timecode`, `build_plan`, `compare_marks`, `previous_mark`, `change_counts`. Sin host; probado por `tests/test_shot_marks_sheet.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks.py`:
  `TimelineInfo` (TC de secuencia y de media), `own_tags`, `previous_marks`, `apply_plan`, `guess_episode`,
  `ShotMarksDialog`, `main`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Preview.py`:
  `preview_entries`, `filter_entries`, `filter_counts`, `missing_required`, `data_column_count`,
  `grid_rows`. Sin host; probado por `tests/test_shot_marks_preview.py`.
- Capturas del dialogo: fixture `+Building_Blocks/UI_Capture/fixtures/h11_shot_marks.py`, PNG
  `ShotMarks_Dialog*.png` en `_LGA_Release/UI_Captures`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Google.py`:
  `sheet_id`, `fetch`, `access_token`, `login`, `cached`, `needs_download`, `safe_name`. Sin host;
  probado sin red por `tests/test_shot_marks_google.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Nav.py`:
  `go_to_mark`, `show_mark_at`, `mark_tags`, `mark_info`, `ShotMarkInfoWindow`, `DifficultyStrip`,
  `info_window`. La
  eleccion del salto es `next_mark_index` y la metadata `mark_metadata` / `mark_info_from_metadata`,
  en el nucleo sin host.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Edits.py`:
  `edits_path`, `load`, `save`, `set_value`, `add_question`, `overlay`, `mark_applied`, `export_csv`.
  Sin host; probado por `tests/test_shot_marks_edits.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Find.py`:
  `ShotMarkFindWindow`, `mark_entries`, `find_window`. La busqueda es `search_marks` /
  `find_match` / `next_match` en el nucleo sin host, probada en `tests/test_shot_marks_sheet.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel.py`: boton `Shot Marks`,
  `execute_ShotMarks` (Shift+Click: `execute_FindShotMark`); Previous / Next Mark en
  `execute_PreviousMark` / `execute_NextMark` (Shift+Click: las anotaciones).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_Locate_Engine.py`,
  `LGA_NKS_ShotMarks_Locate.py` y `LGA_NKS_ShotMarks_Thumbs.py`: ubicar desde thumbnails. El motor
  y el lector de thumbs se prueban sin host en `tests/test_shot_marks_locate.py`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_ShotMarks_EDL.py`:
  `parse_edl`, `align`, `cut_frames`, `segments`, `segment_at`, `source_info`. El motor lo carga
  por ruta (corre con `-I`) en `load_edl`. Tests: `tests/test_shot_marks_edl.py`.
- Capturas: `+Building_Blocks/UI_Capture/fixtures/h11_shot_marks.py` -> `ShotMarks_Dialog.png`,
  `ShotMarks_Dialog-Thumbnails.png` y `ShotMarks_Dialog-Thumbnails-EDL.png`; `h11b_shot_mark_info.py` -> `ShotMarks_Info.png`,
  `ShotMarks_Info-OldTag.png`, `ShotMarks_Info-Located.png`, `ShotMarks_Info-Edits.png` y
  `ShotMarks_Info-Editing.png`; `h11c_shot_marks_locate.py` ->
  `ShotMarks_Locate.png`; `h11d_shot_mark_find.py` -> `ShotMarks_Find.png`,
  `ShotMarks_Find-Result.png` y `ShotMarks_Find-NoMatch.png`.
