> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Apply AMF (NKS): que pone, en que orden y que se midio

El boton **Apply AMF** del Edit Panel (`Shift+L`) pone o saca en los clips del timeline los soft effects de color del shot, a partir de lo que hay en `<shot>/_input/Look_Files`. Existe para no armar a mano, clip por clip, la cadena de color que el shot ya declara; y es un toggle porque dejar efectos colgados en el timeline todo el tiempo estorba. Su contraparte en Nuke es la entrada `AMF` de ToolPack-B (otro repo, otro codigo: las dos tools no comparten modulos, se mantienen por copia).

Con 2 o mas clips seleccionados trabaja sobre esos; con uno o ninguno, sobre los `.exr` bajo el playhead (Hiero autoselecciona el clip bajo el playhead, ver `SELECCION_MINIMA`). Que `.amf` se elige por plate esta en `Docu_Look_Files_y_Plates.md`; como se crean y borran los soft effects, en `Docu_SoftEffects_Aprendizajes.md`.

## Que archivos entiende

| Archivo | Efecto | De donde sale el working space |
|---|---|---|
| `.amf` | uno por cada `lookTransform` con `applied="false"` | del propio `.amf`; si no declara, ACES2065-1 |
| `.cdl` | `OCIOCDLTransform` | del `<cdlWorkingSpace>` del `.amf`; sin `.amf`, el default del nodo (`scene_linear`) |
| `.clf` | `OCIOFileTransform` | ACES2065-1 (un LMT `.clf` entra y sale en AP0) |
| `.cube` | `OCIOFileTransform` | del nombre del archivo; sin pista, ACEScct |

## Prioridad entre formatos

1. **El `.amf` manda.** Si hay uno, el plan sale de el: orden, `applied`, working space y archivos. El `.cdl` es el hermano del `.amf` elegido. Un `.cube` en la carpeta que el `.amf` NO nombra se ignora (apilarlo aplicaria el look dos veces).
2. **Un `.cube` que el `.amf` nombra** en su `<file>` entra por el camino del `.amf`, con ACES2065-1 (el espacio de la cadena del `.amf`), no por la regla del nombre de abajo. Si el `.amf` nombra un `.cube` que no esta en la carpeta, se usa el que elige `pick_cube`.
3. **Sin ningun `.amf`**, plan de respaldo (`_fallback_plan`): el `.cdl` suelto (si hay) mas **UN** LMT, que es el `.clf` y, si no hay, el `.cube`.
   - Con `.cdl` y `.cube` se aplican **los dos** (decision de Lega): son dos eslabones distintos, grade y LMT.
   - **Nunca `.clf` y `.cube` juntos**: son los dos el LMT del shot y aplicar ambos dobla el look. Gana el `.clf` y el `.cube` queda avisado en el log y en el RESUMEN.
4. Si el `.amf` no declara ningun `lookTransform`, se cae al mismo plan de respaldo.

## Varios `.cube`

La tool procesa muchos clips de una vez, asi que **no hay cartel de eleccion** (a diferencia de Nuke, donde se pregunta una sola vez). `pick_cube`:

1. Agrupa por nombre **sin el `_vNNN` final** (sin distinguir mayusculas: hay carpetas con `_V003`) y de cada LUT se queda la version mas alta. En un `.cube` el token anterior a `_vNNN` no es un plate: `PROJA_Preview_LMT_v001.cube` y `PROJA_Final_LMT_v001.cube` son LUT distintos.
2. Si quedan varios LUT distintos, elige el **ultimo por orden alfabetico** y lo avisa en el log y en el RESUMEN (`[AVISO] N distintos .cube...`, con los que no uso). No abre un cartel por clip.

La eleccion es determinista, no inteligente: si un show tiene dos LUT en la carpeta y el que importa es otro, hay que sacar el que sobra o renombrar.

## Working space de un `.cube`

Un `.cube` es un LUT 1D/3D pelado: no declara en que espacio espera su entrada. El knob `working_space` de `OCIOFileTransform` no dice "la entrada esta en", dice "aplicalo en" (ver `Docu_SoftEffects_Aprendizajes.md`). Se elige asi (`cube_working_space`):

1. Si el **nombre** lo dice: `ACEScct`, `ACEScc`, `ACEScg` o `AP1`, `ACES2065` o `AP0` o `Linear` (estos tres, ACES2065-1). Sin distinguir mayusculas, con cualquier separador; no matchea adentro de otra palabra (`acescc` no entra en `acescct`, `linear` no entra en `nonlinear`).
2. Si menciona varios (`ACEScg_to_ACEScct`), gana el **primero**, que por convencion es el de entrada, con aviso en el log.
3. Sin pista, **ACEScct**: es la convencion de los LMT de ACES en los templates de comp.

Es una **convencion**, no una lectura del archivo: un `.cube` hecho para otro espacio que no lo diga en el nombre corre en ACEScct y sale mal sin avisar. La salvaguarda es el log (`working space: X, segun nombre|default`). La solucion es renombrar el LUT, no cambiar la tool.

## El bug de los configs OCIO v2

Cada opcion del enum `working_space` trae campos separados por **TAB**, y solo el primero es el nombre del colorspace:

    aces_1.2        'ACES - ACEScct\tColorspaces/ACES/ACES - ACEScct'
    configs v2      'ACEScct\tColorspaces/ACES/ACEScct\t\tACES - ACEScct,acescct_ap1'

(`fn-nuke_cg-config-v2.2.0_aces-v1.3`, `fn-nuke_studio-config-v2.2.0...` y los v3.0.0 de ACES 2.0 de Nuke 17.) La version vieja de `match_colorspace_option` devolvia la **cadena entera**. El knob la acepta y hasta la lee de vuelta con el nombre corto, pero con los configs v2 el nodo queda con error, entrega negro y no sale ningun aviso. Ahora se matchea contra el nombre corto (lo que va antes del primer TAB) y se devuelve ese, en tres pasadas: directos sin alias, no-alias, todo. Los alias van al final porque `aces_1.2` trae la familia `Utility/Aliases` (`acescct`, `acescg`...) en minuscula, que ganaria por igualdad exacta.

Medido contra los enums reales (NKS aces_1.2 y Nuke 17 con los cuatro configs v2), para los espacios que la tool pide (`ACEScct`, `ACEScc`, `ACEScg`, `ACES2065-1`) el nombre devuelto es **el primer campo de lo que devolvia antes**, en todos los configs; en `aces_1.2` la diferencia es solo que ya no arrastra el `\tColorspaces/...`, y el knob lee el mismo valor con las dos formas (`'ACES - ACEScct'`).

Verificacion de pixel en Nuke 17 (`configure_effect_node` sobre `OCIOFileTransform`, gris 0.18 con un `.cube` x0.5 en ACEScct; esperado 0.014609): `aces_1.2` 0.014609, `fn-nuke_cg-config-v2.2.0` 0.014609, `fn-nuke_studio-config-v2.2.0` 0.014609, `fn-nuke_cg-config-v3.0.0` 0.014609, `fn-nuke_studio-config-v3.0.0` 0.014609; con la funcion vieja los cuatro v2 daban `hasError=True` y pixel 0.0. `.cdl` slope 2 solo: 0.36; `.cdl` + `.cube`: 0.020661 en los cinco. Ojo al medir: despues de un nodo con error `nuke.sample` devuelve 0.0 en el mismo envio al host, asi que los casos rotos y los sanos se miden en envios separados.

## Detectar que un efecto no carga: ni `nodeHasError()` ni `Node.hasError()` deciden

Ninguno de los dos indicadores alcanza para decir que un efecto esta roto, y por eso la tool **no saca ni descarta ningun efecto por lo que digan**. Lo que frena la creacion es mirar el archivo antes.

**`EffectTrackItem.nodeHasError()` peca por defecto.** Medido en NKS con un `.cube` inexistente, vacio, solo con cabecera, corrupto y con filas de mas: devuelve `False` en todos. El `setValue` del knob `file` acepta cualquier ruta.

**`Node.hasError()` peca por exceso.** Ve esos archivos rotos (`True`), pero tambien marca efectos sanos. Valida el nodo contra el color management de `nuke.root()`, y en NKS ese no tiene por que ser el del proyecto. Medido en Nuke 16.0v4 y 17.0v4 (modo terminal, mismos resultados en los dos, con y sin input conectado, con y sin lifetime):

| Nodo | `Node.hasError()` | Mensaje de Nuke |
|---|---|---|
| `OCIOFileTransform` recien creado, sin `file` | **True** | `FileTransform: empty file path` |
| `OCIOCDLTransform` recien creado | False | |
| archivo valido, `working_space` que el config de `nuke.root()` SI tiene | False | |
| archivo valido, `working_space` que el config de `nuke.root()` NO tiene | **True** | `Invalid input LUT selected: <espacio>` |
| archivo inexistente | **True** | `The specified absolute file reference ... could not be located` |

La cuarta fila es la trampa: el `.cdl` se lee bien (el nodo muestra slope, offset y power del archivo) y `hasError()` da `True` igual. En una sesion real de NKS 16.0v4, con un proyecto en `aces_1.2`, un `.cdl` y un `.clf` validos quedaron los dos con `hasError()=True` despues de configurarlos. La version que sacaba del timeline todo efecto con `hasError()` no aplicaba nada en esa sesion y avisaba que los archivos no se podian cargar. Python no expone el texto del error del nodo, asi que desde la tool no se puede distinguir la cuarta fila de la quinta.

Que se hace entonces:

1. **Antes de crear** (`motivo_archivo_inutil`): el archivo tiene que existir, poder leerse, no estar vacio, y tener forma (`.cube`: header con `LUT_1D_SIZE`/`LUT_3D_SIZE` y exactamente las filas esperadas; OCIO tambien rechaza las filas de MAS; `.cdl` y `.clf`: XML bien formado). Si no, el efecto **no se crea** y el motivo sube al cartel unico del final. Cacheado por ruta (un `.cube` 65^3 son ~7 MB y ~210 ms de lectura, una vez por corrida). Es el unico control que frena.
2. **Despues de configurar**, `Node.hasError()` solo se **loguea**, por etapa: `[ESTADO] recien creado`, `con el archivo cargado` y `con el working space` (`_estado_error`). La etapa en la que pasa a `True` dice que knob lo dispara. Si queda en `True` sale un `[WARN]` y el efecto se deja puesto.
3. **Una vez por corrida** (`_log_contexto_color`) el log trae el color management de `nuke.root()` (`colorManagement`, `OCIO_config`, `customOCIOConfigPath`, `workingSpaceLUT`) y el del proyecto (`ocioConfigName`, `ocioConfigPath`, working space), mas la variable `OCIO`. Si no coinciden, un `hasError()=True` en la etapa del working space es el falso positivo de la tabla.

Lo que queda sin red: un archivo con forma valida que OCIO igual rechaza (un `.clf` XML bien formado pero sin operaciones). Ese efecto se crea, entrega negro y el unico aviso es el `[WARN]` del log.

## El config OCIO del proyecto NO cambia el enum de los soft effects

Lo que llena el enum de `working_space` de un soft effect en NKS es el `OCIO_config` de `nuke.root()`, no el del proyecto. Medido: `project.setOcioConfigPath(<config v2>)` cambia `ocioConfigPath()` del proyecto, pero un efecto creado despues sigue listando las 364 opciones de `aces_1.2`. `nuke.root()['OCIO_config'].setValue(...)` en el mismo envio tampoco lo cambia, y de paso **ensucia la lista de opciones del knob** (se le agregan entradas duplicadas) en la sesion en curso. Consecuencia para probar: en NKS no se puede ejercitar un config v2 sin tocar el estado global de la sesion; el comportamiento con v2 se mide en Nuke, donde los nodos `OCIOFileTransform` y `OCIOCDLTransform` son los mismos, llamando a `configure_effect_node` con cada config (ver abajo).

## Donde van los efectos: un bloque contiguo por encima de lo que hay

**Crear un efecto en `subTrackIndex=N` sobre un subtrack ocupado en el mismo rango BORRA en silencio el efecto que estaba** (queda `isValid()=False`, sin error ni aviso). Medido en NKS 17: Blur en sub 0 y Text en sub 1, crear el CDL en sub 0 deja el Blur invalido. La tool antes ponia la cadena siempre en el 0 y el 1, asi que se llevaba puestos los efectos del artista; con `.cdl` + `.cube` perdia los dos.

**Orden de aplicacion, medido** (exportando el clip con `TrackItem.addToNukeScript(script, includeEffects=True)` y leyendo el orden de los nodos): el subtrack mas BAJO se aplica primero y el mas alto despues; los huecos entre subtracks no cambian nada. Con Add en sub 0, Grade en sub 1 y Multiply en sub 2 el script sale Add, Grade, Multiply; con un Blur en el 5 y otro efecto en el 3, sigue el orden de indices.

**Criterio** (`subtracks_para_la_cadena(efectos, n)`): la cadena (CDL + LMT) es un bloque y un efecto del artista no puede quedar partiendola por el medio. Va en `n` subtracks consecutivos que empiezan en el primero POR ENCIMA del mas alto ocupado por cualquier efecto que solape el clip (nuestro o ajeno; el escaneo `scan_clip_effects` guarda el `sub` de cada uno), o en 0 si no hay ninguno. Los huecos que dejen los ajenos por debajo no se usan. Asi la cadena se aplica despues de todo lo que ya habia, con el CDL antes que el LMT, y sin ajenos es el 0 y el 1 de siempre. Si algun efecto no dice su subtrack, no se crea nada en ese clip y se avisa en el cartel unico (mejor no crear que pisar). El toggle de borrado no cambio: solo saca lo que carga un archivo de `Look_Files`.

| Clip | Cadena (CDL, LMT) | Orden de aplicacion |
|---|---|---|
| sin ajenos | sub 0 y 1 | CDL, LMT |
| ajeno en sub 0 | sub 1 y 2 | ajeno, CDL, LMT |
| Blur en 0 y Text en 1 | sub 2 y 3 | Blur, Text, CDL, LMT |
| ajeno solo en sub 1 | sub 2 y 3 | ajeno, CDL, LMT (no se usa el hueco del 0: partiria la cadena) |
| `.cdl` roto + `.cube` valido | solo el `.cube`, sub 0 | LMT (un eslabon descartado no deja hueco) |

Lo ajeno tampoco hace saltear lo nuestro: un `OCIOFileTransform` (o `OCIOCDLTransform`) cuyo `file` no esta en `Look_Files` no cuenta como "el clip ya lo tiene" (`find_existing_effect` exige `_apunta_al_look`). Ojo: Hiero **compacta** los subtracks al borrar (un Blur que estaba en el sub 1 vuelve al 0 despues del toggle), asi que los indices de los efectos ajenos pueden cambiar tras un toggle sin que se haya tocado el efecto.

## Toggle

El toggle ya funciona con el `.cube`: `AMF_EFFECT_TYPES` incluye `OCIOFileTransform`, y `_apunta_al_look` reconoce cualquier efecto cuyo `file` este bajo `.../Look_Files/`, sea `.cube`, `.clf` o `.cdl`. Un `OCIOFileTransform` que alguien puso a mano con un archivo de otra carpeta no se borra.

## Pruebas: dos trampas del banco

- `root.createClip()` con una ruta con **barras invertidas** deja la media con la ruta mutilada (`firstpath()` devuelve `C:Usersleg4-pc...` sin separadores y `\101` se vuelve `A`): el shot no se resuelve. En un banco de pruebas, siempre barras `/`.
- OCIO cachea el LUT por ruta: reescribir un `.cube` en el mismo path y recrear el nodo en la misma sesion devuelve el LUT viejo. Un banco que regenere el LUT tiene que usar nombres distintos.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel_py\LGA_NKS_ApplyAMF.py`
  - `build_effect_plan` / `_build_effect_plan_sin_cache`: plan segun el `.amf`; `_fallback_plan`: plan sin `.amf` (`.cdl` + `.clf` o `.cube`).
  - `pick_cube`, `parse_lut_name`, `cube_working_space`, `cube_spec`: el `.cube` como look (`CUBE_DEFAULT_SPACE`, `_CUBE_SPACE_HINTS`).
  - `motivo_archivo_inutil`, `_motivo_cube_invalido`: validacion previa del archivo.
  - `match_colorspace_option`, `configure_effect_node`: resolucion del nombre corto contra el enum del knob.
  - `_node_has_error`, `_estado_error`, `_log_contexto_color`, `apply_effect`: el estado de error del nodo y el color management de la sesion, solo para el log.
  - `subtracks_para_la_cadena`, `scan_clip_effects` (campo `sub`), `find_existing_effect`: donde va la cadena y que cuenta como "ya lo tiene".
  - `_anotar_fallo`, `_avisar_fallos`: el cartel unico del final; `_AVISOS_CORRIDA`: avisos que no abren cartel (van al log y al RESUMEN).
  - `collect_amf_effects`, `_apunta_al_look`, `remove_amf_effects`: el lado de borrado del toggle.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Edit_Panel.py` — el boton y su tooltip (`apply_amf`).
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\tests\test_apply_amf_nks.py` — tests unitarios (`hiero` stubbeado): validacion de `.cube`, `pick_cube`, working space, `match_colorspace_option` con opciones con TAB y `subtracks_para_la_cadena`.
- Contraparte en Nuke: `C:\Users\leg4-pc\.nuke\LGA_ToolPack-B\py\LGA_ApplyAMF.py` y su `docs\Docu_ApplyAMF.md`.
