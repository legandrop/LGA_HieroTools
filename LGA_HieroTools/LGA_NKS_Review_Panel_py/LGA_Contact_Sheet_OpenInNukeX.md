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
6. Devuelve el control a Nuke Studio y, en un thread, envia el unico comando TCP `paste_clipboard` a `localhost:54325`.
7. NukeX ejecuta `nuke.nodePaste("%clipboard%")` en su hilo principal.
8. OpenInNukeX carga `LGA_ContactSheet.nk`, conecta los Reads y el Viewer, y confirma el resultado al worker.
9. Si falla la conexion o el protocolo, una senal Qt devuelve el aviso al hilo principal de Nuke Studio.

## Metodo de seleccion

Este script usa seleccion explicita (`te.selection()`), no playhead.

La razon es que `Contact Sheet` es una operacion batch sobre varios clips elegidos por el usuario. La posicion del playhead no debe cambiar el conjunto de clips enviados a NukeX.

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
  - `trigger_hiero_copy()`: envia el `Ctrl+C` al widget enfocado del timeline y valida los formatos MIME.
  - `_send_paste_request()`: realiza la unica transaccion TCP, exclusivamente desde el worker.
  - `_send_paste_in_thread()`: crea el worker y entrega errores a Qt mediante `_PasteResultNotifier`.
  - `main()`: orquesta seleccion, copy y paste remoto.

- `C:\Users\leg4-pc\.nuke\LGA_OpenInNukeX\init.py`
  - `handle_client()`: recibe `paste_clipboard` por TCP.
  - `paste_clipboard_with_logging()`: pega los Reads, carga `LGA_ContactSheet.nk`, conecta sus inputs y el Viewer sin cerrar ni abrir scripts.
  - `nuke_server()`: escucha en `localhost:54325`.

- `C:\Users\leg4-pc\.nuke\LGA_NodePack\LGizmos\Other\LGA_ContactSheet.nk`
  - Define el Group que recibe los Reads.
  - Sus callbacks llaman a `LGA_ContactSheet_tools.py` para mantener inputs, burn-ins y grilla.

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\docs\Docu_Metodos_Seleccion_Clip.md`
  - Documenta `te.selection()` como metodo de seleccion explicita independiente del playhead.
