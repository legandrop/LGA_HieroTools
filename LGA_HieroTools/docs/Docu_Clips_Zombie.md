# Clips zombie, reconnect y replace

Qué son los clips "zombie" de NKS, cómo se detectan sin tirar abajo el host, y
qué hace cada uno de los tres botones del Edit Panel que los tocan:
**Reconnect Media**, **Replace Clip** y **Fix Zombies**.

## El síntoma

Un clip del timeline se ve y se reproduce bien, pero:

- doble click no abre nada en el **Properties panel**;
- no se puede leer su **metadata**;
- **Reconnect Media** no lo reconecta, aunque el archivo esté en disco;
- **Scan for Versions** falla con `RuntimeError: Version is null`;
- un **Self ReplaceClip** lo deja sano.

## La causa

En NKS cada clip vive en tres objetos encadenados:

    TrackItem  ->  Clip  ->  BinItem  ->  Version

El `BinItem` es la ficha del bin y la `Version` es la que une esa ficha con el
`Clip`. En un clip zombie el `BinItem` quedó **huérfano**: sigue colgado del
`Clip`, pero ya no pertenece a ningún bin ni a ningún proyecto. El timeline lo
sigue mostrando porque el `TrackItem` guarda su propia referencia al `Clip`,
pero todo lo que sube por la cadena hacia el bin falla.

Medido con la sonda `+Building_Blocks/explore_zombie_clip_probe.py` sobre un
clip roto:

| Llamada | Clip sano | Clip zombie |
|---|---|---|
| `clip.binItem()` | `BinItem('<nombre>')` | `BinItem('')` |
| `binItem.parentBin()` | el bin del shot | error: *Object does not have a parent bin* |
| `binItem.project()` | el proyecto | `None` |
| `binItem.activeVersion()` | la `Version` | error: *Model is null* |
| `binItem.activeItem()` | el mismo `Clip` | **crashea NKS** |

🔴 **`activeItem()` sobre un BinItem huérfano tira abajo NKS entero**, con
access violation adentro de `studio-<version>.dll`, sin excepción de Python que
se pueda atajar. Cualquier código que recorra clips tiene que chequear primero
`parentBin()` y `project()`, que son seguras, y no seguir si el BinItem está
huérfano.

**De dónde sale el huérfano:** de sacar del proyecto un BinItem que el timeline
todavía usa. No está confirmado cuál lo hace; los candidatos con código a la
vista son Clean Project (borra BinItems "sin uso" comparando NOMBRES, y borra
versiones offline sin mirar si el timeline las usa), y Create v000 (borra los
BinItems del v000 anterior antes de reimportar). Import Shot y Create v000 NO
dejan el clip roto al crearlo: se verificó con la sonda, recién importado y
después de guardar y reabrir.

## Qué hace cada botón

### Reconnect Media
El de siempre: abre un browser de **carpeta** y llama a
`trackItem.reconnectMedia(carpeta)`. Hiero busca ahí un archivo con el **mismo
nombre**. No sirve si el media cambió de nombre, ni si el clip está zombie.

### Replace Clip — `LGA_NKS_Edit_Panel_py/LGA_NKS_ReplaceClip.py`
Reemplaza el media del clip seleccionado por **el archivo que elige el
usuario**, aunque se llame distinto o esté en otra carpeta.

- El browser es de **archivo**: se elige cualquier frame y
  `hiero.core.MediaSource()` detecta la secuencia completa sola.
- Antes de tocar el timeline compara contra lo que el clip recuerda —que sigue
  disponible aunque esté offline—: **primer frame, cantidad de frames y
  resolución**. No compara nombres, justamente porque el caso de uso es que el
  nombre cambió. Si algo difiere, muestra las diferencias y pregunta.
- Después del replace verifica que la ruta haya cambiado de verdad, restaura
  los trims si se corrieron, el color del BinItem y el bin. Todo en un undo.
- Avisa si cambió la posición en el timeline o el fps.

### Fix Zombies — `LGA_NKS_Edit_Panel_py/LGA_NKS_FixZombieClips.py`
Recorre **todos** los clips del timeline, detecta los zombie con las dos
llamadas seguras y a cada uno le hace un self replace (`replaceClips` con su
propia ruta), que es lo que vuelve a armar la ficha del bin. Restaura trims y
color, vuelve a medir el clip y muestra un resumen.

**Los zombie con el media offline quedan afuera a propósito**: `replaceClips`
con una ruta sin media no arregla nada. El cartel los lista y hay que
arreglarlos a mano con Replace Clip, eligiendo el archivo.

## Sondas

En `+Building_Blocks/` (solo lectura, log crash-safe línea por línea):

- **`explore_zombie_clip_probe.py`** — estado de la cadena
  Clip/BinItem/Version de los clips seleccionados. El log acumula corridas, así
  que sirve para seguir el mismo clip recién importado, después de guardar y
  después de reabrir NKS. `RESET_LOG = True` para empezar de cero.
- **`explore_replace_clip_probe.py`** — lo que Hiero recuerda del media de un
  clip (incluso offline), qué hay en disco en esa ruta, y comparación contra un
  archivo elegido a mano. Es la que fijó el criterio de validación de Replace
  Clip.

## Pendiente

- Confirmar qué herramienta deja el BinItem huérfano.
- `LGA_NKS_Projects_Panel_py/LGA_NKS_CleanProject.py`: decide si un BinItem se usa comparando
  `bin_item.name()` contra `track_item.source().name()`. En los clips que
  importa el pack esos dos nombres **difieren** (`<shot>_aPlate` vs
  `<shot>_aPlate_v001`), así que puede borrar un BinItem en uso. Debería
  compararse por media o por objeto, no por nombre.
