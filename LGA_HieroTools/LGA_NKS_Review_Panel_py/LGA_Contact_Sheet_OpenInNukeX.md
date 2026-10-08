> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_Contact_Sheet_OpenInNukeX

## Objetivo

`LGA_Contact_Sheet_OpenInNukeX.py` envia los clips seleccionados del timeline de Hiero/Nuke Studio al NukeX abierto, usando el servidor TCP existente de `LGA_OpenInNukeX`.

El proyecto abierto en NukeX no se cierra. Nuke pega los `Read`, carga el toolset `LGA_NodePack/LGizmos/Other/LGA_ContactSheet.nk`, conecta cada Read al grupo y conecta el primer Viewer al resultado. Los callbacks del NodePack sincronizan los inputs, burn-ins y la grilla interna del contact sheet.

## Flujo actual

1. El boton `Contact Sheet` del Review Panel ejecuta `LGA_Contact_Sheet_OpenInNukeX.py`.
2. El script valida que exista una secuencia activa.
3. Obtiene la seleccion explicita del timeline con `hiero.ui.getTimelineEditor(seq).selection()`.
4. Ignora items de efecto (`hiero.core.EffectTrackItem`).
5. Envia `Ctrl+C` al widget interno del timeline para obtener los formatos `x-foundry/x-clips` y `text/x-nuke-script`.
5b. Reescribe `text/x-nuke-script` con los Reads en el orden de inputs deseado (ver "Orden de los inputs").
6. Devuelve el control a Nuke Studio y, en un thread, envia el unico comando TCP `paste_clipboard` a `localhost:54325`.
7. NukeX ejecuta `nuke.nodePaste("%clipboard%")` en su hilo principal.
8. OpenInNukeX carga `LGA_ContactSheet.nk`, conecta los Reads y el Viewer, y confirma el resultado al worker.
9. Si falla la conexion o el protocolo, una senal Qt devuelve el aviso al hilo principal de Nuke Studio.

## Metodo de seleccion

Este script usa seleccion explicita (`te.selection()`), no playhead.

La razon es que `Contact Sheet` es una operacion batch sobre varios clips elegidos por el usuario. La posicion del playhead no debe cambiar el conjunto de clips enviados a NukeX.

## Orden de los inputs

Regla: el input 0 del Contact Sheet es el clip que empieza primero en el timeline (menor `timelineIn`). A igual tiempo, desempata el track de menor indice (V1 antes que V2). El orden en que el usuario clickeo los clips no cuenta.

Por que quedaba invertido (medido con clips de prueba en NKS y NukeX 17):

1. **El `Ctrl+C` de Hiero no ordena por tiempo.** `timeline_editor.selection()` devuelve los items por tiempo y despues track, pero el texto `text/x-nuke-script` que arma Hiero sale por track (V1 completo, despues V2...) y dentro de cada track por tiempo. Con un solo track coinciden; con varios, no. El texto no trae ninguna marca de tiempo ni de track: solo `Read` con `file`, `format`, `first`, `last`, etc., sin `name` ni posicion.
2. **NukeX conecta en el orden inverso al del texto.** Tras `nuke.nodePaste("%clipboard%")`, `nuke.selectedNodes()` (y `nuke.allNodes()`) devuelve los nodos nuevos del ultimo creado al primero. `paste_clipboard_with_logging()` de `LGA_OpenInNukeX/init.py` hace `for i, read in enumerate(read_nodes): setInput(i, read)` con esa lista, asi que el primer Read del texto cae en el ultimo input. Con 10 plates del 0100 al 1000 el input 0 era el 1000.

Solucion actual, del lado de HieroTools (`reorder_clipboard_reads()`): despues del `Ctrl+C` se parte el texto del clipboard en sus bloques `Read`, se calcula la permutacion entre el orden de Hiero (track, tiempo) y el deseado (tiempo, track), y se reescribe el mime `text/x-nuke-script` (los demas formatos pasan intactos). Como NukeX invierte, se escribe en orden inverso; eso lo controla la constante `NUKE_PASTE_REVERSES_ORDER = True`.

**Acoplamiento:** esa constante compensa el comportamiento actual de `LGA_OpenInNukeX`. Si ese pack se corrige para conectar en orden de creacion (por ejemplo `read_nodes = list(reversed(nuke.selectedNodes()))`), hay que poner la constante en `False`, o el orden vuelve a salir invertido. Las dos versiones se probaron de punta a punta y dan el mismo resultado.

Que se reordena y que se descarta: el texto de un Select All trae mas que Reads (un soft effect sale como bloque `Blur { ... }` con el cuerpo sin indentar, y puede haber `version`, `set cut_paste_input` o `push` sueltos). `_split_node_blocks()` parte el texto en bloques de nodo por su encabezado `Clase {`, cuenta llaves (ignorando las que estan dentro de strings) y descarta las lineas sueltas. Solo los `Read` se reordenan y se vuelven a escribir; los nodos de efecto se descartan, asi no se pega un `Blur` suelto en NukeX (que ademas ya solo usa los Reads).

Salvaguardas: se compara la cantidad de Reads con la de clips seleccionados (`selection()` sin `EffectTrackItem`; un clip de audio cuenta y genera su Read). Si no coincide, o un bloque no cierra, no se toca el clipboard (queda el orden de Hiero) y el motivo queda en el log.

Audio: un clip de audio entra como input en su posicion. Ojo con la clave de track: `trackIndex()` es relativo a cada tipo, asi que V1 y A1 valen ambos 0 y el Ctrl+C de Hiero los mezcla por tiempo. El modelo usa esa misma clave. Si dos items con la misma clave empatan en tiempo, el orden entre ellos queda como lo da la seleccion.

Ctrl+C no confiable: tras activar la ventana, el foco a veces queda en un `QWidget` generico y el Ctrl+C no llega al timeline (medido: ~1 de cada 4 corridas seguidas). Antes eso pasaba inadvertido porque se validaba el clipboard viejo, y el script reordenaba (e invertia otra vez) el contenido de la corrida anterior. Ahora el clipboard se vacia antes de copiar y se reintenta (`COPY_MAX_ATTEMPTS`) hasta que el foco sea el `QAbstractScrollArea` del timeline.

## Protocolo con OpenInNukeX

El servidor de `LGA_OpenInNukeX` mantiene el comando existente:

- `run_script||<path>`: cierra el proyecto actual y abre el `.nk` indicado.

Y suma el comando:

- `paste_clipboard`: pega el contenido actual del clipboard en NukeX sin llamar a `nuke.scriptClose()` ni a `nuke.scriptOpen()`, y arma el `LGA_ContactSheet` con los Reads pegados.

El comando `paste_clipboard` debe ejecutarse con NukeX ya abierto y con el servidor de `OpenInNukeX` activo.

## Hallazgos

- El paste manual desde Hiero a NukeX ya genera `Read` nodes con caracteristicas del clip de Hiero. Por eso se aprovecha el clipboard en lugar de reconstruir manualmente los `Read`.
- `OpenInNukeX` originalmente solo aceptaba `ping` y `run_script||<path>`. Se agrego `paste_clipboard` para cubrir este caso sin cerrar el proyecto abierto.
- El `ping` sincrono previo bloqueaba la UI hasta 10 segundos. No hace falta: la conexion del propio `paste_clipboard` ya valida que el servidor este disponible, por eso toda la transaccion TCP corre en background.
- La copia del timeline debe ejecutarse en el hilo principal porque usa widgets Qt; el socket y la espera de NukeX no.
- OpenInNukeX solo confirma exito despues de validar los Reads, cargar el toolset, encontrar el Group y conectar sus inputs. Cualquiera de esos fallos vuelve como error de protocolo al worker.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel.py`
  - `ReviewPanel.buttons`: define el boton `Contact Sheet`.
  - `ReviewPanel.execute_ContactSheet()`: ejecuta el script externo.
  - `ReviewPanel.execute_external_script()`: carga y llama `main()` en scripts del folder `LGA_NKS_Review_Panel_py`.

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_Contact_Sheet_OpenInNukeX.py`
  - `get_selected_clips()`: obtiene la seleccion explicita del timeline y filtra efectos.
  - `trigger_hiero_copy()`: vacia el clipboard, envia el `Ctrl+C` al widget enfocado del timeline (con reintentos) y valida los formatos MIME.
  - `_send_paste_request()`: realiza la unica transaccion TCP, exclusivamente desde el worker.
  - `_send_paste_in_thread()`: crea el worker y entrega errores a Qt mediante `_PasteResultNotifier`.
  - `reorder_clipboard_reads()`: reescribe el clipboard con los Reads en orden de timeline.
  - `_compute_clipboard_permutation()`: permutacion entre el orden de Hiero (track, tiempo) y el de inputs (tiempo, track).
  - `_split_node_blocks()` / `_read_chunks()`: parten el texto del clipboard en bloques de nodo y se quedan con los `Read`.
  - `NUKE_PASTE_REVERSES_ORDER`: compensa la inversion de `nuke.selectedNodes()` del lado de NukeX.
  - `main()`: orquesta seleccion, copy, reorden y paste remoto.

- `C:\Users\leg4-pc\.nuke\LGA_OpenInNukeX\init.py`
  - `handle_client()`: recibe `paste_clipboard` por TCP.
  - `paste_clipboard_with_logging()`: pega los Reads, carga `LGA_ContactSheet.nk`, conecta sus inputs y el Viewer sin cerrar ni abrir scripts. Conecta en el orden de `nuke.selectedNodes()`, que es el inverso al de creacion (ver "Orden de los inputs").
  - `nuke_server()`: escucha en `localhost:54325`.

- `C:\Users\leg4-pc\.nuke\LGA_NodePack\LGizmos\Other\LGA_ContactSheet.nk`
  - Define el Group que recibe los Reads.
  - Sus callbacks llaman a `LGA_ContactSheet_tools.py` para mantener inputs, burn-ins y grilla.

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\Docu_Metodos_Seleccion_Clip.md`
  - Documenta `te.selection()` como metodo de seleccion explicita independiente del playhead.
