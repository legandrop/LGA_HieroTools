# Binarios de terceros del pack

Los binarios de terceros viven en `LGA_NKS_Shared/` y viajan dentro del ZIP de
release. **Se distribuye solo lo que usan las herramientas.** Hasta v4.020 se
copiaban carpetas enteras (una distribución de OIIO con Qt, un entorno de conda
con Intel MKL y codecs de video adentro de `OpenEXR_Win`, y una compilación de
FFmpeg con todo) y el ZIP pesaba 435 MB para usar cinco ejecutables. Desde
v4.021 pesa unos 35 MB: los binarios de terceros pasaron de 1.208 MB a 53 MB
sin comprimir.

## Qué viaja y quién lo usa

| Ejecutable | Lo invoca | Para qué |
|---|---|---|
| `OIIO_Win/oiiotool.exe` | `LGA_import_shots.py`, `LGA_NKS_CreateV000.py`, `LGA_EXR_Convert.py` | Info de EXR, EXR negros del v000, recompresión, resize y conversión OCIO |
| `OpenEXR_Win/exrheader.exe` | `LGA_NKS_mediaMissingFrames.py` | Leer el header de un EXR |
| `OpenEXR_Win/exrmetrics.exe` | `LGA_EXR_Convert.py` | Recompresión rápida (motor `exrmetrics`) |
| `FFmpeg_Win/bin/ffprobe.exe` | `LGA_import_shots.py`, `LGA_NKS_CreateNKScript.py` | Resolución, fps, codec y frames de MOV/MXF |
| `OIIO_Win/bin/python/python.exe` | `LGA_import_shots_transcode.py` | Correr `LGA_EXR_Convert.py` fuera de NKS |

Junto a cada ejecutable van **solo** las DLL que importa, sacadas de su tabla de
imports y no a ojo. La config OCIO del round trip vive aparte, en
`LGA_NKS_Shared/OCIO/aces_ap0_ap1.ocio`, y no depende de ningún archivo de estas
carpetas.

El Python embebido lleva solo la librería estándar: `LGA_EXR_Convert.py` y
`LGA_NKS_Project_Downgrade.py` no importan nada más. No lleva `site-packages`
(numpy, pip, el módulo `oiio`), `test`, `idlelib`, `tkinter`, `ensurepip`,
`lib2to3`, `pydoc_data` ni `turtledemo`. El transcode lo corre con `-I`, aislado
del `PYTHONPATH`/`PYTHONHOME` que hereda de NKS, y si falta no cae a ningún
otro Python: la secuencia falla antes de mover un EXR, nombrando la ruta.

## Runtime de Visual C++

`oiiotool`, las DLL de OIIO, `exrheader`/`exrmetrics` y el Python embebido
necesitan el runtime de Visual C++ (`msvcp140.dll`, `msvcp140_codecvt_ids.dll`,
`vcruntime140.dll`, `vcruntime140_1.dll`). Ese runtime no viene con Windows: lo
instala el Visual C++ Redistributable, que la mayoría de las máquinas tiene
porque lo trae otro programa, pero no todas. Hasta v4.020 solo `OpenEXR_Win`
traía copia propia; oiiotool y el Python lo tomaban de `System32`, y en una
máquina sin el Redistributable Create V000, Import Shots y el transcode no
arrancaban. Ahora cada carpeta trae su copia (14.44, ~1 MB). Windows busca
primero en la carpeta del ejecutable, así que se usa esa.

Las `api-ms-win-crt-*.dll` (Universal CRT) sí son de Windows desde la 10.

## ffprobe mínimo

El ffprobe de hasta v4.020 era una compilación "gpl" completa de BtbN: 193 MB,
con x264, x265, Vulkan, Whisper, OpenCL y decenas de librerías. El código solo
le pide los datos del encabezado de un MOV/MXF (`-show_streams` y `nb_frames`).
Desde v4.021 viaja un ffprobe compilado a medida desde la fuente oficial,
estático y sin librerías externas.

**Receta** (MSYS2, entorno UCRT64, fuente `ffmpeg-9.0.2.tar.xz` de
`https://ffmpeg.org/releases/` verificada con su `.asc` contra la clave de
releases, huella `FCF986EA15E6E293A5644F10B4322F04D67658D8`):

```
configure --disable-everything --disable-autodetect --disable-doc --disable-debug
  --disable-network --disable-programs --enable-ffprobe
  --disable-avdevice --disable-avfilter --disable-swscale --disable-swresample
  --enable-small --enable-static --disable-shared --enable-zlib
  --enable-protocol=file,pipe
  --enable-demuxer=mov,mxf,avi,matroska,mpegts,mpegps
  --enable-decoder=prores,dnxhd,h264,hevc,mpeg1video,mpeg2video,mjpeg,dvvideo,rawvideo,v210,v210x,qtrle,png,cfhd
  --enable-decoder=pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_s32be,pcm_f32le,aac
  --enable-parser=h264,hevc,mpegvideo,mjpeg,dnxhd,png,aac
  --extra-ldflags=-static --pkg-config-flags=--static
make ffprobe.exe && strip ffprobe.exe
```

La receta completa está en `+Building_Blocks/Binarios_Pack/build_ffprobe.sh`.
Resultado: 3,2 MB, estático, solo pide DLL de Windows.

Los decodificadores están porque ffprobe decodifica unos frames de algunos
codecs para completar los datos del stream; sin ellos `-show_streams` puede
devolver otros valores. **Antes de reemplazarlo** se compara contra el ffprobe
completo con los dos comandos exactos del código
(`Binarios_Pack/comparar_ffprobe.py` y `comparar_create_nk.py`), sobre los clips
de `generar_media.sh` (ProRes 4444/422 HQ/LT, DNxHR en MXF OP1a y en MOV,
DNxHD OP-Atom, MPEG-2 en MXF, H.264, H.265, MJPEG, PNG, QT RLE, MKV) y sobre
MOV/MXF reales del estudio. Medido en v4.021: 95 de 95 iguales en lo que lee el
código (80 reales, 15 generados). Si aparece un codec nuevo que no lee bien, se
suma su `--enable-decoder` y se recompila.

**Trampa de FFmpeg 9 (medida):** un MOV con pista de timecode arma un *stream
group* "Track Reference", y con `-of default=nw=1:nk=1` ffprobe imprime
`nb_frames` dos veces (una por el stream y otra por el grupo): `239\n239`.
Create NK Script esperaba un número solo y devolvía None en 22 de los 80 MOV
reales. Pasa con cualquier ffprobe 9, no por ser mínimo. Desde
`LGA_NKS_CreateNKScript v1.19` se pide `-of json` y se lee `streams[0]`, como ya
hacía Import Shots. Al leer ffprobe, usar siempre JSON y la clave `streams`.

Licencia: sin x264/x265 la compilación es **LGPL 2.1** (configure lo dice al
final). `FFmpeg_Win/LICENSE.txt` va en el ZIP.

## FFmpeg no está en Git

Hasta v4.020 `FFmpeg_Win/` entera estaba en el `info/exclude` del repo, porque
el ffprobe completo pesaba más de los 100 MB por archivo que acepta GitHub, y su
único respaldo eran los ZIP de release. Desde v4.021 `ffprobe.exe` y
`LICENSE.txt` se versionan; solo `ffmpeg.exe` queda excluido. Sigue en el disco
de desarrollo (genera los clips de prueba) y el generador lo deja fuera del ZIP;
no está respaldado en ningún lado y se vuelve a bajar de la fuente oficial si
hace falta. `OIIO_Win` y `OpenEXR_Win` siempre estuvieron en Git: lo que se
borró en v4.021 se recupera del historial.

## Sumar un binario nuevo

1. Agregar el ejecutable a `ENTRADAS` en
   `+Building_Blocks/Binarios_Pack/verificar_binarios.py`, con quién lo usa.
2. Correrlo con el Python del pack:
   `LGA_NKS_Shared/OIIO_Win/bin/python/python.exe -I verificar_binarios.py`.
   `FALTA` lista las DLL que pide y no están: copiar esas, y solo esas, desde la
   distribución original. Nunca la carpeta entera.
3. Correrlo con `--probar`, que ejecuta cada comando como lo arma el código con
   el PATH vaciado (solo `System32`).
4. Actualizar la tabla de arriba.

`SOBRA` lista lo que nadie pide: se borra. El verificador compara nombres sin
distinguir mayúsculas, como Windows: Git guarda `msvcp140.dll` y la tabla de
imports pide `MSVCP140.dll`, y comparar con distinción borró una vez las DLL
del runtime.
