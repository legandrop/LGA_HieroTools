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
   y las columnas de shot, TC IN, TC OUT, episodio, status y nota. Todo se puede corregir en la
   ventana y queda guardado en `%APPDATA%\LGA\HieroTools\ShotMarks.ini`.
3. Prueba en seco en vivo: cuantas marcas, cuantas Omit salteadas, cuales no se pueden ubicar y por
   que. El log de cada corrida va a `LGA_NKS_Review_Panel_py/logs/DebugPy_LGA_NKS_ShotMarks.log`.
4. Al aplicar, en un solo undo: borra los tags que puso antes, opcionalmente alinea el TC de inicio
   del timeline y crea un tag de rango por shot (`Sequence.addTagToRange`), con el shot como nombre y
   el brief como nota.

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
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel.py`: boton `Shot Marks`,
  `execute_ShotMarks`.
- Captura: `+Building_Blocks/UI_Capture/fixtures/h11_shot_marks.py` -> `ShotMarks_Dialog.png`.
