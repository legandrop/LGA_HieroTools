# Labels de XYplorer en el Flow Pull

## Que hace y por que existe

Al terminar de procesar cada shot, el Flow Pull (solo Windows) le pone a la
carpeta del shot un **label** de XYplorer segun el estado de la task en Flow:
`Corrections`, `Rev_Sup`, `Rev_Lega`, `Rev Hold`, `ReviewDir` o `Approved`.
Asi, en XYplorer, las carpetas de shot quedan pintadas con el color del estado.
El mapeo estado -> label es la tercera columna de `TASK_STATUS_CATALOG`.

## Lo que costo descubrir

- **El comando se manda por `WM_COPYDATA`** a la ventana principal de XYplorer
  (clase `ThunderRT6FormDC`): `::tag '<label>', '<carpeta>';`. Si ese label no
  esta definido en ese XYplorer, XYplorer abre un cartel modal
  **«Label X is not defined.»**, y como el Pull etiqueta shot por shot, se
  apilan decenas de carteles. Le paso a un artista con XYplorer recien
  instalado, que solo trae los labels de fabrica (Red ... Grey).
- **Los labels no viven en `XYplorer.ini`**: estan en la cabecera de
  `tag.dat`, en la linea siguiente a `Labels:`, con el formato
  `nombre|color_texto|color_fondo;...`. El archivo es UTF-16 LE con BOM.
- **`tag.dat` guarda el label de cada archivo por POSICION en esa lista**
  (`C:\carpeta|3|...`), no por nombre. Reordenar o borrar labels cambia el
  color de todo lo ya etiquetado. Por eso el instalador solo agrega al final.
- **El color de la fila entera sale de otro lado**: los Color Filters de
  `XYplorer.ini`, seccion `[ColorFilter]`, entradas
  `+t:prop:#label:<nombre>>texto,fondo` y una linea `Count=`.
- **La carpeta de datos no es siempre la misma.** `Startup.ini` junto al exe
  puede fijarla (`[Appdata] Path=%appdata%\XYplorer64`); una instalacion
  portable la tiene junto al exe; si no, `%APPDATA%\XYplorer64` o
  `%APPDATA%\XYplorer`. Si el ini trae `TagDatCustom=`, el `tag.dat` es ese.
- Desde XYplorer no hay una forma simple de preguntarle que labels tiene (la
  respuesta volveria por otro `WM_COPYDATA` a una ventana nuestra), por eso se
  lee `tag.dat` directamente.

## Comportamiento desde Flow Pull v3.78

Antes de mandar el comando, el Pull lee los labels definidos en el `tag.dat`
del XYplorer abierto (la ruta sale del exe dueño de la ventana). Si el label no
esta, o no se encontro el `tag.dat`, **no etiqueta** y lo anota en
`logs/debugPy_FlowPull.log`. La lectura se cachea por ruta + fecha de
modificacion.

## Instalar los labels en otra maquina

`LGA_NKS_Flow_Rev_Panel_py/XYplorer_Labels/Install_XYplorer_Labels.bat`, con
XYplorer CERRADO (al salir, XYplorer reescribe sus archivos y pisaria el
cambio). Agrega los seis labels del Pull y un Color Filter por label, con los
colores de la PC de Lega, sin tocar lo existente; antes copia `tag.dat` y
`XYplorer.ini` con sufijo `.bak_<fecha>`. Si no encuentra la carpeta de datos,
acepta la ruta como argumento. Es idempotente: correrlo dos veces no duplica.

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/LGA_NKS_Flow_Pull.py`
  - `get_xy_hwnd()` — ventana principal de XYplorer.
  - `Send_WM_COPYDATA()` — manda el script.
  - `_xy_exe_dir()`, `_xy_read_ini_value()`, `_xy_tag_dat_path()` — ubican el `tag.dat` en uso.
  - `_xy_defined_labels()` — labels definidos (cache `_xy_labels_cache`).
  - `_tag_shot_folder_thread()`, `tag_shot_folder()` — etiquetado en thread; `XYPlorer_Tags` lo apaga.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_Status_Config.py`
  - `TASK_STATUS_CATALOG` — code -> (nombre, color de clip, label de XYplorer).
- `LGA_HieroTools/LGA_NKS_Flow_Rev_Panel_py/XYplorer_Labels/Install_XYplorer_Labels.ps1`
  (+ `.bat` lanzador) — instalador de labels y Color Filters.
