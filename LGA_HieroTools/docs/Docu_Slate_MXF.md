# Slate de los MXF de entrega

Algunas producciones piden que cada MXF entregado lleve **un frame de slate adelante**: el primer
frame del archivo, de un solo frame, con la misma resolución y el mismo formato que el video. El
slate lleva datos del shot, una imagen del plate y una nota del estudio para producción.

El slate lo arma una herramienta del editor de VFX que vive **fuera de NKS**, en PipeSync. HieroTools
aporta las dos cosas que tienen que estar en Flow antes de que el editor la use: la **Submission
Note** que escribe el supervisor y el **Slate Frame** que elige el coordinador.

## Las tres piezas y quién hace cada una

| Pieza | Quién | Dónde | Qué deja en Flow |
|---|---|---|---|
| Submission Note | Supervisor de VFX | Flow Review Panel, **Ctrl+Alt+Click en Rev Dir** | 3 campos de la Version |
| Slate Frame | Coordinador / editor | Panel Flow \| S3, botón **Slate Frame** | 1 campo del Shot |
| Slate del MXF | Editor de VFX | PipeSync, Tools tab | Nada: lee lo anterior y escribe el MXF con slate |

Todo existe **solo en el sitio studio de Flow**. En contexto client el gesto y el botón avisan y no
hacen nada.

## Campos de Flow

| Entidad | Código | Tipo | Lo escribe |
|---|---|---|---|
| Version | `sg_submission_note` | text | Ctrl+Alt+Click en Rev Dir |
| Version | `sg_submitting_for` | text | ídem (WIP, FINAL o texto libre) |
| Version | `sg_media_color` | text | ídem ("Rec709 with show LUT" / "Rec709 without show LUT") |
| Shot | `sg_slate_frame` | url (File/Link) | botón Slate Frame |

Los códigos viven en un solo lugar: `LGA_NKS_Shared/LGA_NKS_Slate_Config.py`. Los creó
`py_scr/bootstrap_slate_fields.py` de PipeSync (idempotente, con dry-run por defecto).

- **Tres campos de texto y no un JSON en uno:** se leen y se corrigen a mano en la web de Flow y se
  pueden mostrar como columnas en las páginas de Versions. Un JSON roto en un campo de texto no le
  avisa a nadie.
- **Media Color es texto y no lista:** los valores los pone el diálogo. Una lista exige un admin
  para sumar una opción.
- **Slate Frame es File/Link y no imagen:** la API no crea campos custom de tipo imagen. Se sube con
  `sg.upload("Shot", id, ruta, field_name="sg_slate_frame")` y se baja con
  `sg.download_attachment(valor_del_campo)`. Con `urllib` no alcanza: la URL de un adjunto pide
  sesión, a diferencia de la URL del thumbnail.

## Por qué la nota no es una Note

Una Note del push va dirigida al autor de la Version y a los asignados de la Task: les llega aviso
y la ven en el activity stream. La Submission Note es un texto para producción y **los artistas no
la tienen que ver**. Por eso se guarda en campos de la Version y el gesto no crea Note ni adjunta
imágenes (el diálogo, en ese modo, no ofrece arrastrar media).

Ocultar los campos a los artistas **no se puede hacer por API**: es un permiso por campo del rol de
los artistas en Flow (Permissions → rol → Fields), y se configura a mano. El registro de cambios de
Flow (EventLogEntry y la pestaña History de la Version) también guarda el valor escrito: hay que
comprobar con una cuenta de ese rol que no lo vea antes de escribir la primera nota real.

## Ctrl+Alt+Click en Rev Dir

1. Solo en contexto studio y de a **un clip** (selección o playhead, igual que el push).
2. Lee los tres campos de la **Version exacta** del clip y el estado de la task, para que el
   diálogo los muestre y el supervisor corrija en vez de reescribir. Primero de `pipesync.db`
   (`DBManager.read_submission()`): el sync de Reviewer y Coordinator los baja, así que la
   ventana abre al instante. Si la base no alcanza (PipeSync sin las columnas nuevas, Version
   nunca sincronizada —campos en `NULL`—, o dos Versions con el mismo code) los lee de Flow en
   background (~2 s).
   **La base puede estar vieja** (el sync automático suele estar apagado, y el incremental no
   relee una Version a la que solo le cambió la nota). Por eso, al guardar —que ya corre en
   segundo plano— el conector compara contra Flow lo que mostró el diálogo
   (`submission_expected`, `submission_stale_reason()` en `LGA_NKS_Flow_Push_connector.py`): si
   la task entró a la cola de entrega o los tres campos cambiaron en Flow, **no guarda nada**,
   avisa, y la fila de la base vuelve a `NULL` (`forget_version_submission()`) para que el
   próximo Ctrl+Alt+Click lea de Flow. Si guarda bien, los tres campos se escriben en la base
   local, en la fila de esa Version (`version_sg_id`) y solo si el sync ya la mantiene (no
   `NULL`): en la base de un rol que no sincroniza estos campos, escribirlos los dejaría
   congelados.
3. El diálogo es el de notas del push con dos selectores en una fila arriba del texto: Submitting
   For (editable, ofrece WIP y FINAL, las dos opciones estándar del template del cliente) y Media
   Color. Los dos son `ArrowComboBox` (`LGA_NKS_Shared/LGA_NKS_ArrowComboBox.py`): `Style.COMBO`
   oculta la flecha nativa, y un combo con la hoja sola parecía un campo de texto. En este modo **Enter no
   confirma** (se confirma con OK o Ctrl+Enter): el primer widget es el combo editable y un Enter
   al escribir "Submitting For" mandaba la nota vacía.
4. El push escribe los tres campos **antes** de tocar la Task. Si Flow no los acepta, se corta sin
   cambiar nada. Después hace lo de siempre en Rev Dir: Task en `rev_di`, Version en `vwd`, color
   del clip y limpieza de tags (esta última recién cuando el push salió bien).

Lo que costó decidir:

- **Nunca la versión más alta como respaldo.** El push normal cae a la Version más alta si no
  encuentra la del clip. Acá eso pondría la nota en el slate de otra versión: es error.
- **Nunca una versión elegida a ciegas.** Si hay dos Versions con el mismo número y ninguna tiene
  el nombre exacto del clip (dos convenciones de naming conviviendo), el gesto se corta con el
  aviso en vez de elegir una.
- **No sacar un shot de la cola de entrega.** Si la task ya está en `pubsh`, `check` o `apr`,
  pregunta y ofrece guardar solo la nota sin volverla a Rev Dir (sin color ni tags).
- **AltGr.** En teclados con AltGr, Windows lo reporta como Ctrl+Alt: AltGr+Click dispara el mismo
  gesto. En macOS el gesto es Cmd+Option+Click.
- **El log del push guarda el texto.** `DebugPy_FlowPush.log` copia la nota (es la única copia si
  Flow fallara). Queda en la máquina del supervisor.

## Botón Slate Frame

Reusa `LGA_NKS_Flow_UpdateThumb` con el destino `slate_frame`: misma captura que Thumbnail (BurnIn
apagado, zoom to fill, recorte al aspecto de la secuencia), misma ventana de comparación, pero sube
al campo `sg_slate_frame` y no al thumbnail del shot. Es otra imagen a propósito: el thumbnail se
pisa seguido y el slate frame se elige una vez.

- Captura **lo que muestra el viewer**: el coordinador se para en el frame del aPlate que quiere.
- JPG calidad 95. En un slate de 1920 la imagen ocupa ~730 px de ancho: una captura más angosta se
  avisa (agrandar el viewer), no se bloquea.
- Cada reemplazo crea un adjunto nuevo en Flow; los anteriores quedan en la pestaña Files del Shot.

## La herramienta del editor (PipeSync)

Vive en el Tools tab de PipeSync, solo para usuarios autorizados y solo en contexto studio. Se
documenta en el repo de PipeSync. Lo que necesita de este lado:

- La Version se identifica por el **nombre del MXF**: su stem coincide con el `code` de la Version.
- La descripción del shot es la `task_description` de la task.
- Si falta la nota, sus selectores o el Slate Frame, la herramienta avisa y no deja seguir hasta
  completarlo a mano o marcarlo vacío.
