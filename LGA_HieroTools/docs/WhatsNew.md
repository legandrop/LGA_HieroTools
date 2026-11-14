---
product: LGA HieroTools
release_repo: legandrop/LGA_HieroTools
tech_changelog: ChangeLog.md
version_heading: "v{v}:"
roles: [Coordinators, Reviewers]
editions: [studio, client]
platforms: [win, mac]
---
# What's new in LGA HieroTools
<!-- Editable while a version is unpublished. NOT append-only. Published versions are frozen. -->

## Unreleased

## v4.027
- [new] En LGA BurnIn, el timecode se pinta de rojo cuando no coincide con el del plate del track `aPlate` en ese frame, así ves enseguida un comp corrido.

## v4.026
- [improved] El panel de LGA BurnIn (botón `Open Burn-in Panel`) ahora funciona como el de Shot Player: elegís una distribución, arrastrás cada campo a su lugar del cuadro o lo escondés en `Hidden`, y el tamaño, el fondo (`Panels`, `Band` o `Text`) y el giro de los costados valen para todos los campos.
- [new] LGA BurnIn suma los campos `Track`, `Date` y `Codec`.
- [improved] LGA BurnIn arranca con un layout nuevo: el nombre del clip, los fps, la resolución, el codec y el colorspace abajo, y el timecode y el frame arriba a la derecha.
- [improved] Se quitó `LGA BurnIn v0` del menú Effects: queda un solo LGA BurnIn.
- [improved] Con una máscara en el viewer, incluso al 50%, los burn-ins de LGA BurnIn se corren hacia adentro y quedan a la vista, con cualquier aspect que elijas.
- [new] Shot Marks pone una marca por clip en un timeline de edit refs (un clip por shot), sin necesitar timecodes en la planilla: cada marca dura lo que su clip, y la vista previa te muestra los shots sin clip y los clips sin fila en la planilla.
- [improved] La ventana de la marca muestra también el grupo del shot (columna Grupo), y con el brief en dos idiomas usa el inglés.

## v4.025
- [new] En el panel Flow | S3, `Download Clip` con Ctrl+Alt+Click te deja elegir la carpeta donde se baja la última versión del clip, y con Ctrl+Alt+Shift+Click baja a la última carpeta que elegiste, sin preguntar (hace falta FileManager S3 actualizado).
- [improved] cuando cambiás un estado con los botones de Flow Push, PipeSync abierto lo muestra al instante en todos sus tabs, sin esperar al próximo sync (hace falta PipeSync actualizado).
- [fixed] Los botones de estado de Flow Push actúan siempre sobre el clip donde está el playhead: antes, con otro clip seleccionado, se cambiaba el estado del shot equivocado. Para enviar varios clips a la vez, seleccionalos y dejá el playhead sobre uno de ellos; si no, un cartel te avisa y no se envía nada.

## v4.024
- [fixed] En la ventana de `Flow Pull`, `v_NKS` muestra la versión con la que quedó el clip después de actualizarlo; antes mostraba la anterior y parecía que faltaba bajar un clip que ya estaba al día.
- [fixed] `Import shot` hace lugar para todo el render de comp cuando es más largo que el plate, como en un plano realentado, y el preview te avisa que es un retime: antes el comp y el EditRef quedaban encima del shot siguiente.
- [fixed] Al importar un shot o soltar media en Projects Panel, un soft effect largo que pasa por el lugar donde entra lo nuevo se estira para cubrirlo, en vez de correrse y dejar sin efecto el principio de lo que tenía antes.
- [fixed] `Import shot` ya no pone el shot nuevo encima del anterior cuando el anterior tiene un render de comp: el anterior quedaba corrido a la derecha y sin plate ni EditRef.
- [improved] `Import shot` deja afuera el slate de los renders de comp que arrancan en el frame 1000, así el 1001 del render coincide con el 1001 del plate.
- [new] Podés arrastrar una o varias carpetas de shot desde el explorador al Edit Panel para importarlas con `Import shot`, sin tener que buscarlas en el selector.
- [improved] Los tooltips del Edit Panel son iguales a los de PipeSync: aparecen debajo del botón, apuntándolo con una flechita.
- [new] Desde la ventanita de cada shot podés cambiar la dificultad con un clic, corregir o agregar Notes y Budget Alternative, y dejar preguntas, sin salir de Nuke Studio: los cambios quedan guardados en tu computadora (nunca en la planilla) y `Export Changes` los baja a un CSV para revisarlos y pasarlos a la planilla.
- [improved] La columna Notes 2 de Shot Marks pasa a llamarse Alternative (Budget Alternative en la ventanita de cada shot), y se reconoce sola aunque en la planilla se llame «Alternativas para reducción de presupuesto».
- [new] Shot Marks lee la columna de dificultad de la planilla (Dificultad o Difficulty) y la ventanita de cada shot la muestra con un color según el nivel, de verde para lo muy fácil a rojo para lo muy difícil.
- [improved] La ventana de Shot Marks se reorganizó: a la izquierda elegís la planilla y las columnas, y a la derecha ves todas las marcas antes de escribirlas, con un filtro para ver solo lo que cambió o lo que tiene problemas. Si la planilla no tiene timecode, muestra las fotos de los shots que va a buscar.
- [improved] Los tooltips de la ventana de `Flow Pull` son iguales a los de PipeSync: aparecen debajo del control, apuntándolo con una flechita.
- [improved] En la ventana de `Flow Pull`, cada fila tiene su propia celda de descarga al lado de `v_NKS`: un clic baja el clip sin tener que seleccionar la fila; cuando el timeline tiene una versión más vieja que Flow, la versión y esa celda se pintan de violeta.
- [new] Con clic derecho sobre el nombre de un proyecto en Projects Panel podés abrir su carpeta (`Reveal in Explorer`) o guardar una copia para Nuke 16 (`Convert to Nuke 16...`), sin tener que arrastrar el archivo.
- [improved] Al guardar una copia para Nuke 16 elegís si mantiene el nombre con `_NKS16` al final (`Rename`) o si sube un número de versión (`Increment version`), y ves cómo va a quedar el nombre antes de guardar.
- [fixed] En Projects Panel, el clic derecho sobre el nombre de un proyecto ya no lo colapsa ni muestra Copy y Select All, y el menú de `Delete Timeline` ya no sale con el color del proyecto.
- [improved] Si abrís desde Projects Panel un proyecto que no tiene ningún timeline, ahora te avisa con un cartel, en vez de abrirlo sin que se vea ningún cambio.
- [improved][win] `Locate from Thumbnails` recuerda lo que revisaste en cada corte por separado: si el proyecto tiene dos armados de la misma película, revisar el nuevo no borra lo que confirmaste en el anterior.
- [improved] Shot Marks numera cada renglón del brief (1., 2., 3.…) en lugar de los guiones, y en la ventanita separa un poco cada pedido del siguiente, así la lista de cada shot se lee de un vistazo.
- [improved][win] Shot Marks guarda los thumbnails de la planilla en una carpeta junto al proyecto, así la ventanita de cada shot los muestra siempre, también si abrís el proyecto desde otra máquina.
- [fixed][win] `Locate from Thumbnails` de Shot Marks ya no deja marcas una encima de otra cuando la planilla repite la misma foto en varios shots, repite una fila o pone dos shots en lo que parecía un solo plano.
- [fixed] Al volver a correr Shot Marks con una planilla que cambió los nombres de los shots, ya no quedan las marcas rojas con el nombre viejo encima de las nuevas.
- [improved][win] En `Locate from Thumbnails`, los shots de tomas largas o de escenas muy oscuras se marcan de corte a corte y no en un solo cuadro.
- [fixed][win] `Locate from Thumbnails` recuerda lo que confirmaste aunque guardes el proyecto con otra versión; antes, al pasar por ejemplo de v04 a v05, había que revisar todo de nuevo.
- [fixed] Shot Marks elige sola la columna de nombres de shot que está completa cuando la planilla trae dos (por ejemplo `SHOT NAME` y `VFX SHOT NAME`); antes podía tomar la de nombres viejos y dejar muchos shots sin marcar o con el nombre anterior.
- [new] La ventanita de cada shot de Shot Marks muestra los comentarios que dejaron en la planilla de Google Sheets o Excel, con quién lo escribió, la fecha, la columna y las respuestas; los resueltos aparecen en gris.
- [new] Shot Marks suma las columnas `Notes` y `Notes 2` (toma solas las columnas Notas y Alternativa de la planilla): la ventanita de cada shot las muestra arriba de todo, resaltadas en dos colores, y solo cuando ese shot tiene algo escrito.
- [improved][win] Al revisar en `Locate from Thumbnails` de Shot Marks, una tira muestra todos los planos que hay entre el shot anterior y el siguiente de la planilla, con los dos vecinos en color; un click lleva el visor a ese plano. Cuando no queda nada por revisar, la ventana avisa que falta apretar `Use Timecodes` para agregar las marcas.
- [fixed][win] `Locate from Thumbnails` de Shot Marks busca cada shot entre sus vecinos de la planilla y ya no lo manda a otra parte de la película por un parecido flojo o por una imagen que se repite; en la revisión, los candidatos ofrecen también la otra opción.
- [fixed][win] `Locate from Thumbnails` de Shot Marks ya no deja las marcas corridas (o fuera del timeline) cuando Nuke Studio muestra el video con un timecode distinto del que trae el archivo.
- [fixed] En Shot Marks, los nombres de columna que en la planilla tienen un salto de línea se ven en una sola línea en los menús.

## v4.023
- [new] La ventana de `Flow Pull` suma el checkbox `Shot Info`: prendido, al hacer click en una fila se abre el Shot Info de ese shot sin sacarle el foco a la ventana del Pull; se recuerda entre sesiones. `Keep this window on top` pasa a llamarse `Keep on top`.
- [new] La ventana de `Flow Pull` tiene un botón `Download Clip`: baja la última versión del clip de la fila que seleccionaste, igual que el del panel Flow S3, sin tener que buscar el clip en el timeline.
- [improved] En el panel Review, los botones de navegación pasan a ser `Previous Mark` y `Next Mark`: el clic salta de un shot de Shot Marks al otro, y con Shift+Click navegan las anotaciones del clip, como hacían antes.
- [new] Shift+Click en `Shot Marks` abre `Find Shot Mark`, una ventanita que queda siempre arriba: escribís un nombre de shot o cualquier texto de la planilla (descripción, brief, vendor, status) y `Find` salta a esa marca; `Next` sigue con la próxima que coincide.
- [new] En el Projects Panel podés borrar un timeline con clic derecho sobre su nombre y `Delete Timeline`; pide confirmación y se deshace con Ctrl+Z.
- [improved] Al volver a correr Shot Marks sobre un timeline que ya tenía marcas, te avisa antes de reemplazarlas y las pinta según lo que cambió en la planilla: verdes las que siguen igual, amarillas las que cambiaron de descripción, brief u otro dato, naranjas los shots nuevos y rojas los que ya no están; la ventanita de cada shot muestra qué cambió y cómo era antes.
- [fixed] Shot Marks trae el brief completo cuando la planilla es un csv: los briefs de varias líneas que empezaban con comillas quedaban cortados en la primera línea.
- [fixed][win] Snapshot (con Shift+Click) y Review Pic abren FrameRev adelante y listo para anotar, en vez de dejarlo escondido detrás de Nuke Studio.
- [fixed] La ventanita de Shot Marks vuelve a cambiar sola al arrastrar el playhead en los timelines donde la planilla no trae REC TC OUT (o lo trae igual al IN): antes solo cambiaba si el playhead caía justo en el primer cuadro del shot.

## v4.022
- [fixed] En los proyectos con color management, Fix Colorspaces deja en Rec.709 los mp4 y mov de los tracks de plates y de EditRef, en vez de pasarlos a ACEScg o dejarlos como venían.
- [new] Shot Marks, en el panel Review, lee la planilla de breakdown y marca cada shot en el timeline en su timecode; con Shift+Click en Previous Annotation y Next Annotation saltás de un shot al otro y se abre una ventanita con la descripción, el brief y los datos de ese shot en la planilla, con el vendor en su color; mientras está abierta, cambia sola cuando el playhead entra en otro shot.
- [new][win] Shot Marks también funciona con planillas sin timecode que solo traen una foto por shot: `Locate from Thumbnails...` encuentra cada foto en el video del timeline, marca el plano entero y te deja revisar los dudosos paso a paso sobre el visor, al lado de la foto; al navegar las marcas, la ventanita muestra la foto de la planilla y resalta los shots omitidos o posiblemente omitidos.
- [new][win] Si además le das el EDL del armado, Shot Marks marca cada shot exactamente de corte a corte y la ventanita muestra el clip de cámara y el SRC TC de cada uno.

## v4.021
- [improved] La descarga de LGA HieroTools pasa de 435 MB a unos 35 MB: el pack ya no trae programas de terceros que ninguna herramienta usa.
- [fixed][win] Create V000, Import Shots y el transcode de EXR ya no fallan en una máquina que no tiene instalado el runtime de Visual C++ de Microsoft.

## v4.020
- [improved] Apply AMF uses the shot's .csp LUT before any other look file: when there is one, it applies only that LUT, with linear interpolation in ACEScg.
- [improved] Create NK v000 loads the shot's .csp LUT into the template's look nodes (linear, ACEScg) and turns off the CDL nodes when there is one.
- [fixed] LGA BurnIn's background panels stay lined up with their text when the sequence format differs from the clip's.
- [fixed] Adding the LGA BurnIn soft effect no longer freezes the timeline viewer; moving the playhead updates the image right away.
- [new] Hover an open project in the Projects panel to save it as the next version with one click; if a newer version already exists on disk, it asks before using the next free number.
- [new] Hover an open project in the Projects panel to upload it to Wasabi through FileManager S3; the icon shows when the upload is running, finished or failed.

## v4.01
- [fixed] Flow Pull, Push, Shot Info and the other Flow tools find shots whose name has a single description block or a description that starts with a number, instead of reporting that they aren't in PipeSync.
- [improved] When Flow Pull finds none of the timeline shots, the warning tells you whether the project is missing from PipeSync or the shot names don't match Flow, and lists the names it searched for.

## v4.00
- [improved] Flow Shot Info separates the responsible artists from Viewers who retain task access, while preserving version and assignment history.
- [new] Drop a Nuke Studio or Hiero 17 project onto the Projects panel to save a separate Nuke 16.0 copy, with an editable next-version name, a folder chooser and an explicit choice to discard incompatible annotations.
- [fixed] Switching timelines in the Projects panel keeps one Media Spreadsheet tab instead of accumulating duplicates.
- [improved] TL | Refresh and timeline switches apply the preferred Media Spreadsheet column order, widths and visibility, with rows sorted by Clip.
- [new] In projects framed for 3:2, the Projects panel now turns the 3:2 viewer mask on at half opacity every time you switch to one of their timelines.
- [improved] Download AMF downloads the look files of every selected shot at once when two or more clips are selected, instead of one shot at a time.
- [fixed] Apply AMF applies the shot's .cdl and .clf again instead of reporting that valid look files could not be loaded.
- [improved] Shot Info opens as tall as its content instead of at a fixed size, so a shot with little to show no longer opens a mostly empty window.

## v3.99
- [improved] Apply AMF now applies the shot's .cube LUT, together with the .cdl grade when there is one.
- [fixed] Apply AMF no longer deletes effects you had added to the clip: the look goes on top of them.
- [fixed] Apply AMF works with the OCIO v2 configs that ship with Nuke 17, and warns when a look file is missing or corrupt instead of leaving the clip black.
- [fixed] Compare Versions now loads the previous version in the same color space as the comp in color-managed projects, so the difference compares like with like.
- [improved] Fix Colorspaces, and the automatic fix after a Flow Pull, now also fix the other loaded versions of each clip, so switching versions keeps the right color space.
- [fixed] Fix Colorspaces no longer skips plates and comps it used to report as having no color transform available.
- [fixed] Contact Sheet connects the clips in timeline order: the first clip on the left is input 0, even when the selection includes effects.
- [fixed] Create NK v000 now trims the review range (without handles) on every movie output of the template, whatever the Write node is named.
- [improved] Create NK v000 points LUT look nodes that use a .cube file to the shot's .cube in Look_Files.

## v3.98
- [fixed] Create NK v000 no longer rejects shots whose name has no vendor code at the end.
- [improved] Create NK v000 works with a template that only has the plates the project uses: aPlate is the only one it needs, and the plate Reads can be empty with just their label.
- [improved] The Flow Pull results window remembers its Only in review and Only for me checkboxes, the same way it already remembers Keep this window on top.
- [fixed] Nuke Studio no longer prints a "Can't restore panel" message for every HieroTools panel at startup: the installer now sets this up on its own.

## v3.97
- [new] TL | Solo EditRef in the Viewer | TL panel (Alt+Shift+D) turns off every video track except EditRef and BurnIn to watch the edit on its own; press it again to turn them all back on.
- [new] The Import Shots transcode queue has a Skip Current button: a plate that hangs can be skipped, its originals go back in place and the queue moves on to the next one; failed plates show the reason when you hover over Error.
- [improved] Review Pic and Viewer | Snapshot trim only the black around the image, so zoomed or panned shots are no longer cut.
- [improved] Review Pic and the Shift+Click of Viewer | Snapshot open the picture in FrameRev to annotate it, replacing the ShareX image editor that came inside HieroTools, which is no longer included. FrameRev 0.265 or later has to be installed and opened once; otherwise a message says so.
- [new][mac] Review Pic and the Shift+Click of Viewer | Snapshot now work on macOS too, opening the picture in FrameRev to annotate it.
- [new][studio] Ctrl+Alt+Click on Rev Dir in the Flow Review panel opens the delivery slate's Submission Note with Submitting For and Media Color; it never overwrites a newer note and asks before saving an empty one.
- [new][studio] The Slate Frame button in the Flow | S3 panel saves the viewer image as the shot's slate frame for the delivery slate.
- [improved] Every status button in the Flow Review panel now has a tooltip listing its click gestures.
- [new][client] The Flow Review panel has Rev Netflix and SL Approved status buttons.
- [new] The Flow Pull results window can show only the shots in review (Only in review).
- [new][for: Reviewers][studio] the Flow Pull results window can also show only your own reviews (Only for me).
- [new] HieroTools now answers PipeSync's Show shot in NukeStudio: it opens the project if needed, switches to the sequence, marks the shot and brings NukeStudio to the front.
- [improved] Create Shot now creates the task folders in lowercase, the same as PipeSync, so a task no longer ends up with two folders that differ only in capitalization.
- [fixed] Shot Info, Push, Assign and Clear Assignees now find the shot when the clip's path has the project name in lowercase.
