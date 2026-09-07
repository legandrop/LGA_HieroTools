# LGA_HieroTools — Color Management por proyecto

## Objetivo

Que el boton **Fix Colorspaces** del Edit Panel deje de aplicar una regla fija y use los espacios
de color que el proyecto declara, configurados desde PipeSync.

> **La fuente de verdad del contrato del dato vive en el otro repo**:
> `C:\Portable\LGA_PipeSync_2\Docs\Doc_Color_Management.md`. Ahi estan el formato del envelope, por
> que se guarda un token neutro y no el nombre del colorspace, y los serializadores que hay que
> tocar juntos del lado de PipeSync. Este doc cubre **solo** el lado de Hiero.

## De donde sale la configuracion

No se consulta Flow. Se lee la copia que PipeSync ya bajo a su cache local, con el mismo patron que
ya usaban los colores de proyecto (`LGA_NKS_Project_Colors_Config.py`) y los vendors
(`LGA_NKS_Vendors_Config.py`):

```
pipesync_stats.db  ->  tabla project_settings_cache, columna settings_json
                       JOIN projects por project_id, sqlite3 en modo READ-ONLY
                       clave `color_management` del envelope JSON
```

El modulo es `LGA_NKS_Shared/LGA_NKS_ColorManagement_Config.py`, con cache por TTL y stamp de la DB,
copiado de `LGA_NKS_Vendors_Config.py`. Si la DB no existe, si falta la tabla, o si el JSON esta
corrupto, devuelve "ningun proyecto configurado" **sin excepcion**, y `Fix Colorspaces` cae al
camino de siempre.

El nombre del proyecto se resuelve por la **ruta del media** (`VFX-<PROYECTO>`), no por el nombre
del `.hrox`: `extract_project_name_from_path()` de `LGA_NKS_Flow_NamingUtils.py`, con
`extract_project_name()` como fallback. Es el mismo patron que usa
`LGA_NKS_Flow_CheckTimelineShots.py`.

### 🔴 La trampa: hay DOS bases, y este repo lee la del PipeSync INSTALADO

`LGA_NKS_PipeSyncPaths.get_pipesync_db_path()` apunta **siempre** al PipeSync instalado
(`C:/Portable/LGA/PipeSync/cache` en Windows studio), **nunca** al arbol de desarrollo
(`C:/Portable/LGA_PipeSync_2/cache`). Es a proposito y esta comentado en la cabecera de ese modulo:
ignora el `CachePath` del `config.secure` justamente para no leer el build de dev.

La consecuencia muerde al probar: **si configuras un proyecto desde el PipeSync compilado del repo
de desarrollo, HieroTools no lo va a ver.** El sintoma es exactamente este par de lineas en el log:

```
[managed] Proyecto (desde ruta): PROJA
[main] project_name='PROJA' managed=False, camino viejo
```

o sea, el proyecto se resuelve bien pero sale como no managed. Antes de buscar el problema en el
codigo, comparar las dos bases:

```sql
SELECT p.project_name, c.settings_json FROM projects p
JOIN project_settings_cache c ON c.project_id = p.id WHERE p.project_name = 'PROJA';
```

Si la clave `color_management` esta en la del arbol de desarrollo y no en la del instalado, no hay
ningun bug: se guardo desde la edicion equivocada.

## Los dos caminos del boton

### Proyecto NO color managed — el comportamiento de siempre

Recorre `project.clips()` —el **bin**, no el timeline— y a todo clip cuyo knob `colorspace` del Read
diga `rec709` o `gamma2.2` le pone `Output - Rec.709`.

🔴 **Con una sola diferencia, y es a proposito: no toca clips que pertenecen a un proyecto color
managed.** `hiero.core.projects()` devuelve TODOS los proyectos abiertos, y en Nuke Studio es normal
tener dos. Antes eso era inofensivo porque todos recibian el mismo tratamiento; ahora no, porque un
proyecto managed tiene su propia paleta. Sin el filtro, apretar el boton con un proyecto no managed
activo le pisaba el colorspace de los plates al managed que estuviera abierto al lado, sin aviso y
sin pasar por la deteccion de conflictos —que solo corre del lado managed—. El filtro va por CLIP y
no por proyecto porque el nombre canonico sale de la ruta del media, no del nombre del `.hrox`.

### Proyecto color managed — por track

Recorre `hiero.ui.activeSequence().videoTracks()` y clasifica cada track por su nombre:

| Track | Token que le toca |
|---|---|
| el nombre TERMINA en `plate` (`aPlate`, `bPlate`, `fgPlate`, `bgPlate`, …) | `plates` |
| el nombre esta en `TASK_EXR_TRACKS` (hoy `_comp_`, `_roto_`, `_cleanup_`, `_cg_`) | `exr_publish` |
| cualquier otro (`EditRef`, `EditRefClean`, …) | **no se toca** |

🔴 **La lista de tracks de publish NO se duplica aca**: se importa `TASK_EXR_TRACKS` de
`LGA_NKS_Shared/LGA_NKS_GetClip.py`, que es donde el repo la declara y donde dice su propio
comentario que hay que sumar una task nueva. La convencion completa de nombres de track esta en
[Docu_Logica_Nombres_Tracks.md](Docu_Logica_Nombres_Tracks.md).

🔴 **El colorspace vive en el `Clip` del bin, no en el `TrackItem`.** Por eso se agrupan TODOS los
clips por regla ANTES de aplicar nada: un mismo clip que aparece bajo dos reglas distintas —en un
track de plate y en uno de publish— es un **conflicto**, no se toca y se reporta. Aplicando sobre la
marcha, ese clip quedaria con el token del track que se encontro ultimo, o sea que el resultado
dependeria del orden de iteracion. La identidad del clip se compara por `clip.guid()` y no por
`id()`, porque `trackItem.source()` puede devolver un wrapper de Python nuevo para el mismo Clip
nativo en cada llamada (mismo motivo por el que `LGA_NKS_ApplyAMF.py` tiene su propio helper).

Un clip que ya esta en el espacio que le corresponde se saltea sin reescribir.

### El token no se compara como string: se resuelve

`resolve_ocio_name(token, clip.getAvailableOcioColourTransforms())` es un porte de
`match_colorspace_option()` de `LGA_ToolPack-B/py/LGA_ApplyAMF.py`, donde el problema ya estaba
resuelto. Hace **dos pasadas**: primero contra los espacios nombrados directo y recien despues
contra la lista entera. El motivo es que los ROLES del config OCIO aparecen con formato
`scene_linear (ACES - ACEScg)` y son una indireccion: pidiendo ACES2065-1 matchean tanto
`ACES - ACES2065-1` como `default (ACES - ACES2065-1)`, y cual gana depende del orden de la lista.
La segunda pasada no es un adorno: en `aces_1.2` hay 34 colorspaces con parentesis en su propio
nombre (del tipo `Input - ARRI - V3 LogC (EI160) - Wide Gamut`), y descartarlos de una dejaria sin
resolver a quien pida uno de esos. Dentro de cada pasada va de igualdad, a sufijo, a contencion.

Si el token no resuelve contra el config activo, el clip **no se toca** y se reporta como *sin
transform disponible*.

## Quien dispara la correccion

Hay **dos** disparadores, y los dos usan la MISMA funcion, `run_if_color_managed()`:

| Disparador | Donde | Quien abre el grupo de undo |
|---|---|---|
| Boton `Fix Colorspaces` del Edit Panel | `LGA_NKS_Edit_Panel.py::fix_colorspaces()` -> `main()` | el panel, con `beginUndo("Fix Colorspaces")` |
| Al terminar un **Flow Pull** | `LGA_NKS_Flow_Pull.py::fix_colorspaces_si_proyecto_managed()` | el Flow Panel, con `beginUndo("Run External Script")` |

🔴 **`run_if_color_managed()` NO abre grupo de undo. Lo abre siempre el llamador**, que es la
convencion del repo ("El undo lo maneja el propio script, para no anidar bloques",
`LGA_NKS_Edit_Panel.py`). Los dos llamadores ya vienen dentro de uno, y el del pull es facil de
pasar por alto: no esta en `LGA_NKS_Flow_Pull.py` sino en `LGA_NKS_Flow_Panel.py`, en
`run_FPT_pull()` y `run_FPT_pull_with_deselect()`, que envuelven `FPT_Hiero()`. Buscar `beginUndo`
en el archivo del pull no lo encuentra. Anidar dos `beginUndo` fusiona los macros y el Ctrl+Z deja
de comportarse como uno espera. Con esto, un Ctrl+Z despues de un Pull deshace la operacion
completa -versiones y colorspaces-, que es lo que el usuario hizo.

### Por que el Pull tiene que dispararla

El Pull cambia los clips a su version mas alta
(`HieroOperations.change_to_highest_version`), y **en Hiero una `Version` distinta es otro `Clip`,
con su propio color transform**. O sea que cada bump devuelve el clip al espacio que traiga el
archivo y deshace la correccion que ya se habia hecho. Sin este disparo habria que acordarse de
apretar el boton despues de cada pull, y el timeline quedaria inconsistente justo despues de la
operacion que mas versiones cambia.

### Lo que el Pull NO hace

`run_if_color_managed()` corre **solo** el camino managed. Si el proyecto no esta color managed no
hace nada, y en particular **no cae al barrido viejo de rec709**: eso lo decide `main()`, no el
pull. Un barrido sobre todos los clips del bin de todos los proyectos abiertos, disparado como
efecto secundario de un pull, seria una sorpresa desagradable.

Ademas, **solo corre si el Pull cambio algo** (`changes_exist`). Ese flag se prende cuando el Pull
encuentra una diferencia contra Flow, que es la condicion previa a un bump de version: sin cambios
no hay version nueva, y sin version nueva no hay colorspace que reparar. Barrer el timeline entero
en cada pull que no toca nada es costo puro sobre la operacion mas frecuente del panel.

La llamada corre en el hilo principal, que es donde ya corre `update_table()` -toca la API de
Hiero y no puede salir de ahi-, con import diferido y envuelta en su propio `try/except`: si algo
falla, se loguea y el Pull sigue igual. Un fallo de la correccion no puede voltear el Pull. El
volcado del log va en un `finally` y usa `volcar_log()`, que es publica justamente porque la llama
otro modulo.

## Contrato de ejecucion: por que el modulo no hace nada al importarse

`LGA_NKS_FixColorspaces.py` **no ejecuta nada al importarse** y expone `main()`. La version anterior
hacia lo contrario: disparaba el trabajo por side-effect, con la llamada suelta en la ultima linea.

Importa porque `LGA_NKS_Edit_Panel.py::execute_external_script()` carga el script con `exec_module()`
y **despues** llama a `module.main()` si existe, y devuelve `True` aunque no encuentre ninguna
funcion. O sea que hay dos formas de romperlo en silencio:

- dejar la llamada suelta **y** agregar `main()` -> el trabajo corre **dos veces**;
- sacar la llamada suelta **sin** agregar `main()` -> el boton **reporta exito sin hacer nada**.

Por el mismo contrato, los imports de `hiero.core` / `hiero.ui` —y el de `TASK_EXR_TRACKS`, que
importa `hiero.core` por transitividad— estan **diferidos dentro de las funciones que los usan**: el
modulo se puede importar en un proceso sin Nuke sin explotar y sin hacer nada, que es lo que permite
testearlo.

## El camino managed atrapa sus propias excepciones, y no cae al viejo

`main()` envuelve la corrida managed en su propio `try/except`. Sin eso, cualquier excepcion no
contemplada se propaga hasta `execute_external_script()`, que la **traga** y devuelve `False`, y
`fix_colorspaces()` solo lo manda a un log de archivo: el usuario aprieta el boton, no pasa nada y
nadie le avisa.

Ante el error **no se cae al camino viejo**, aunque sea lo intuitivo: correr el barrido de rec709
sobre un proyecto managed es justo lo que el filtro del camino viejo existe para evitar. Fallar
ruidoso es mejor que arreglar mal.

## Como agregar un espacio de color nuevo

Sumar la entrada `token -> nombre a buscar` al mapa de tokens de
`LGA_NKS_ColorManagement_Config.py`, y el item correspondiente al combo del lado de PipeSync.
Ninguna capa valida los tokens contra una lista blanca, asi que un proyecto guardado con un token
que este repo todavia no conoce no se rompe: el valor sobrevive y simplemente no resuelve hasta que
el mapa lo incluya.

## Referencias tecnicas

- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ColorManagement_Config.py` —
  `load_project_color_management()`, `get_color_management()`, `is_color_managed()`,
  `refresh_cache()`, `resolve_ocio_name()`.
- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py` — `main()`,
  `corregir_clips_con_colorspace_rec709()` y `buscar_y_cambiar_clips_rec709_en_todos()` (camino
  viejo, con el filtro de proyectos managed), `_project_name_de_clip()`,
  `corregir_clips_con_color_management()`, `_clasificar_track()`, `_clips_por_regla()`,
  `_clip_key()`, `_resolve_active_project_name()`, `_get_task_exr_tracks()`.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_GetClip.py` — `TASK_EXR_TRACKS`.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py` — `get_pipesync_db_path()`.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py` —
  `extract_project_name_from_path()`, `extract_project_name()`, `clean_base_name()`.
- `LGA_HieroTools/LGA_NKS_Edit_Panel.py` — `fix_colorspaces()`, `execute_external_script()`.
- `LGA_HieroTools/LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py` — `run_if_color_managed()`, el punto de entrada que comparten el boton y el Pull.
- `LGA_HieroTools/LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py` — `fix_colorspaces_si_proyecto_managed()`, `GUI_Table.update_table()`, `HieroOperations.change_to_highest_version()`.
- `LGA_HieroTools/LGA_NKS_Shared/tests/test_color_management_config.py` — banco de pruebas sin Nuke.
- `LGA_HieroTools/docs/Docu_Logica_Nombres_Tracks.md` — la convencion de nombres de track.
