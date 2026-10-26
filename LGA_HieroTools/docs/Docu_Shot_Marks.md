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
- **Vendor con color.** `LGA_NKS_Shared/LGA_NKS_Vendor_Colors_Config.py` lee de la DB de PipeSync
  del contexto activo (studio o client) la tabla `project_vendor_groups` (token, nombre, color)
  y, de respaldo, `vendor_colors` del envelope del proyecto. Compara sin mayusculas ni signos
  (`Vendor-B` = `VENDORB`), primero en el proyecto del `.hrox` (nombre o prefijo) y si no esta, en
  todos, salvo que el mismo vendor tenga colores distintos. Sin color, se muestra el texto solo.
- **Letra mas grande.** 15 px el cuerpo y 19 px el titulo, por `apply_ui_font` y QFont: con el
  tamano del host (~12 px) no se leia. El titulo no usa `lgaTitle` porque esa regla fija 11 pt.
- **Los datos salen del tag, no del Excel.** Shot Marks guarda la fila en la metadata del tag
  (`tag.lga_shotmarks_tc_in`, `_tc_out`, `_brief`, `_description`, `_status`, `_vendor`,
  `_scene`, `_category`, `_episode`). Releer el Excel tardaria medio segundo por salto y fallaria
  si la planilla se mueve. Los tags creados antes de esta version solo tienen nombre y nota: la
  ventana muestra eso y pide volver a correr Shot Marks.

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
- Capturas: `+Building_Blocks/UI_Capture/fixtures/h11_shot_marks.py` -> `ShotMarks_Dialog.png`;
  `h11b_shot_mark_info.py` -> `ShotMarks_Info.png` y `ShotMarks_Info-OldTag.png`.
