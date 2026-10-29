# FrameRev: el editor de imágenes de Review Pic y Snapshot

## Por qué existe

Review Pic (Flow Review Panel) y el Shift+Click de Viewer | Snapshot (ViewerTL Panel) abren
una imagen del viewer para anotarla. Hasta la v3.96 el editor era **ShareX ImageEditor LGA**,
el editor de ShareX extraído a un `.exe` propio, que viajaba dentro del pack en
`LGA_NKS_Flow_Rev_Panel_py/ShareX_ImageEditor_LGA/`: 5,5 MB y 103 archivos que solo
funcionaban en Windows. Se reemplazó por **FrameRev**, la app de anotación de LGA, y la
carpeta se borró.

**FrameRev NO viaja en el pack: el reviewer lo instala aparte**, desde
https://github.com/legandrop/LGA_FrameRev_Release/releases.

## Cómo se encuentra FrameRev

Todo pasa por `LGA_NKS_Shared/LGA_NKS_FrameRev.py`. FrameRev se ubica por el **registro
compartido de apps LGA**: cada app escribe al arrancar un `<App>.json` con su ejecutable y su
versión.

| Sistema | Archivo |
|---|---|
| Windows | `%APPDATA%\LGA\FrameRev.json` |
| macOS | `~/Library/Application Support/LGA/FrameRev.json` |

`find_framerev()` lee `executable` y `version` y devuelve un mensaje para el usuario si:

- **El JSON no existe, no se puede leer o no es un objeto.** FrameRev no está instalado, o se
  instaló y nunca se abrió: el JSON lo escribe la app al arrancar, no el instalador. El cartel
  pide abrirlo una vez. Se lee con `utf-8-sig`, así que un BOM no molesta.
- **El ejecutable registrado no existe.** La app se movió o se desinstaló.
- **La versión es anterior a `MIN_VERSION` (0.265).** Ver abajo.

**No hay ruta de instalación clavada como respaldo.** La regla de portabilidad del repo
prohíbe rutas que solo existen en una máquina, y una ruta adivinada podría apuntar a una
versión vieja sin forma de saberlo. Si el registro falta, se avisa.

## Las dos entradas de FrameRev

| Tool | Flag | Qué hace FrameRev | Qué pasa al guardar |
|---|---|---|---|
| Review Pic | `--edit-image <jpg>` | Abre el JPG del `ReviewPic_Cache` y **no lo borra** | Save pisa ese mismo JPG, que es el que Flow Push sube con la nota |
| Snapshot (Shift+Click) | `--open-capture <png> --capture-app-name Hiero` | Abre un PNG temporal y **lo borra apenas lo lee** | Save pregunta dónde guardar (nombre sugerido `Hiero_<fecha>_<hora>`) |

Las dos abren una **ventana secundaria** de FrameRev: sin ícono en la bandeja, sin atajos
globales, sin chequeo de updates, y la X cierra esa ventana sin tocar la FrameRev que ya
estaba abierta. El comportamiento de Save en FrameRev está documentado en
`Doc_GuardadoImagenProyecto.md` del repo de FrameRev.

Antes de abrir FrameRev, Snapshot copia la captura al portapapeles, igual que el click normal: si FrameRev
no está, la captura no se pierde.

Snapshot no usa `--edit-image` porque la captura no tiene archivo propio: con un temporal,
Save escribiría encima del temporal y la anotación se perdería. El temporal se crea con
`tempfile.mkstemp` (`LGA_HieroTools_Snapshot_*.png`); si FrameRev no arranca, se borra acá
mismo. El PNG se escribe con compresión baja (calidad 80), porque corre en el hilo de la UI de
Hiero. Si FrameRev arranca y se cae antes de leerlo, el temporal queda en `%TEMP%`: el barrido
de FrameRev solo limpia sus propios temporales.

## Por qué se exige FrameRev 0.265

FrameRev no tiene control de instancia única. Una versión anterior a la 0.265 no conoce
`--edit-image`: lo ignora **en silencio** y arranca una segunda copia completa de la app, con
su ícono en la bandeja y peleando por los atajos globales con la que ya estaba abierta, y sin
abrir la imagen. Por eso, por debajo de esa versión no se lanza nada y se pide actualizar.

## Lanzamiento

`_launch()` usa `subprocess.Popen` con la ruta absoluta del ejecutable, nunca el PATH. En
Windows va con `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`: sin consola heredada y en su
propio grupo, así que cerrar Hiero no cierra FrameRev. Cada llamada deja su log en
`LGA_HieroTools/logs/DebugPy_LGA_NKS_FrameRev.log`, con el registro leído, la versión y el
comando.

## Al frente y con foco (Windows)

Hasta `LGA_NKS_FrameRev v1.00`, FrameRev se abría **detrás de Hiero**. La ventana la muestra
un proceso nuevo, y Windows no deja que un proceso que no es el del frente se active solo: el
`activateWindow()` de FrameRev apenas hacía titilar su botón en la barra de tareas. El que sí
puede ceder el frente es Hiero, que es la app del frente en el momento del click.

Por eso, después del `Popen`, `_bring_to_front_when_ready()`:

1. Llama a `AllowSetForegroundWindow(pid)`: si Windows se lo respeta, FrameRev se activa solo.
2. Arranca un `QTimer` de 100 ms **en el hilo de la UI** (no bloquea: cada vuelta es un
   `EnumWindows`). Busca la ventana principal de FrameRev (`pick_main_window`: visible, sin
   dueño, que no sea tool window ni esté encapada, la más grande) y, si Hiero sigue al frente,
   le hace `SetForegroundWindow`. Tiene que ser desde el hilo de la UI de Hiero: el permiso es
   del proceso del frente.
3. Corta cuando FrameRev queda al frente, cuando FrameRev se cerró, a los 15 s, o **cuando el
   usuario ya está en otra app**: en ese caso no se le roba el foco. La decisión de cada vuelta
   es `front_step()`, pura y con test.

Nada de `HWND_TOPMOST`: la ventana queda adelante y con foco, pero no "siempre encima". FrameRev
encapa (DWM cloak) la ventana mientras ajusta el zoom de la captura, y Windows no trae al frente
una ventana encapada: por eso se la espera destapada. El resultado se agrega al final del log
(`Al frente: done a los 0.9 s (1 SetForegroundWindow)`).

## Otros consumidores

La galería de Snapshots de LGA_ToolPack (`LGA_viewer_SnapShot_Gallery.py`, Shift+click)
también abre FrameRev con `--edit-image`. Tiene su propia copia de la búsqueda en el registro,
porque los packs no importan código entre sí. Antes buscaba el ShareX de este repo.

## Tests

`LGA_NKS_Shared/tests/test_framerev.py`, sin Hiero: rutas del registro por sistema, versión
mínima, registro faltante, roto o con un ejecutable que ya no existe, comando de cada flag, y
que el temporal de Snapshot no quede en disco si FrameRev no arranca, y la elección de ventana
y la decisión de cada vuelta del traer-al-frente. En Windows además enumera ventanas reales
(solo lectura) para validar los tipos de `ctypes`. Se corre con el Python embebido del pack:

    LGA_NKS_Shared\OIIO_Win\bin\python\python.exe LGA_NKS_Shared\tests\test_framerev.py
