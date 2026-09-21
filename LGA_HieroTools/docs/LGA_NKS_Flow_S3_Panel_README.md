> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Flow | S3 Panel (`LGA_NKS_Coordination_Panel`)

## Descripción
Flow | S3 separa en un solo dock dos etapas contiguas del trabajo de producción:
las primeras seis acciones operan sobre Flow Production Tracking y las cinco
restantes preparan o transfieren datos mediante FileManagerS3/Wasabi S3. El
nombre visible describe esa frontera; el módulo, la clase y el `objectName`
históricos no cambian para conservar compatibilidad con layouts guardados.

La carpeta privada del panel es `LGA_NKS_Flow_S3_Panel_py/`. El nombre viejo
`LGA_NKS_Coordination_Panel_py/` ya no existe y no debe usarse en rutas nuevas.

## Funcionalidades Principales

### 1. Create Shot
- **Función**: Crea shots automáticamente en Flow Production Tracking basándose en los clips seleccionados
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CreateShot.py`
- **Comportamiento**: Analiza los clips seleccionados, extrae información del shotname y crea los shots correspondientes en Flow si no existen
- **Pre-chequeo v1.33**: Antes de mostrar la UI verifica si ya existen; si hay múltiples y alguno existe se cancela mostrando la lista, si es un único shot existente lanza Modify Shot automáticamente
- **Acceso Client v1.54**: `SUP` es interno y se omite del nombre del Shot en Flow (`PROJA_010_020_SUP_comp` crea `PROJA_010_020` + Task `comp`). No recibe Group ni altas en `Project.users`, pero cada Task habilitada se asigna a Lega. Un vendor externo conserva su código y se valida completo antes de escribir; el Shot nace con `sg_vendor_groups`, sus Tasks con `task_assignees` y `Project.users` suma los usuarios prevalidos sin quitar miembros existentes. Una colisión `SUP`/`vendors[]`, un Group incompleto o un token inequívoco desconocido abortan sin crear un shot largo.
- **Resultado**: las etapas se clasifican como `complete`, `partial` o `failed`; una Task, membresía o carga secundaria fallida no se anuncia como éxito total y no se hace rollback destructivo.

### 2. Modify Shot
- **Función**: Modifica un shot ya existente en Flow (agregar o quitar tasks, actualizar descripciones) sin tocar estados actuales
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ModifyShot.py`
- **Restricción**: Solo admite un clip seleccionado a la vez
- **Comportamiento**: Lee la configuración real del shot en Flow, precarga la misma UI compacta y aplica únicamente las diferencias solicitadas

### 3. Check Shots Exist
- **Función**: Chequea si los shots de los tracks de task del contexto existen en Flow
- **Alcance**: Studio recorre `_comp_`; Client recorre `_comp_` y todos los tracks `_cg_`
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`

### 4. Thumbnail
- **Click normal**: Genera un snapshot del viewer, abre la comparación contra el thumbnail actual y, al confirmar, lo reemplaza en Flow en un hilo de fondo
- **Shift+Click**: Guarda el snapshot localmente en `N:/<proyecto>/Thumbs`
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_Thumbs.py` y, para el reemplazo en Flow, `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_UpdateThumb.py`
- **Presentación**: Es el cuarto botón y comparte color con Create Shot, Modify Shot y Check Shots Exist porque las cuatro acciones pertenecen al mismo flujo de gestión del shot

### 5. Shot Priority
- **Función**: Cambia la prioridad del shot (alta ↔ normal)
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShotPriority.py`
- **Presentación**: Gradiente verde/rojo. El anclaje verde lo mantiene dentro del bloque Flow; el rojo comunica prioridad.

### 6. Reveal in Flow
- **Shortcut**: `Ctrl+Shift+F` (abre el Shot completo)
- **Función Click normal**: Abre la task preferida del contexto en el navegador predeterminado: Comp, o CG en Client si no existe Comp
- **Función Shift+Click/Shortcut**: Abre el Shot completo en el navegador predeterminado (sin la task específica)
- **Tooltip**: Se muestra el shortcut y funcionalidad de Shift+Click al hacer hover sobre el botón
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
- **Comportamiento**: Click normal busca el shot y la task preferida correspondiente al clip seleccionado. Shift+Click o Ctrl+Shift+F abre directamente la URL del shot completo sin especificar una task.
- **Presentación**: Gradiente verde/gris. Cierra el bloque Flow conservando el gris histórico de Reveal in Flow.

### Herramienta retirada: .Psync
- **Estado**: Fuera de uso y oculta en la interfaz. No forma parte del listado de botones visibles.
- **Motivo de conservarla**: El script queda como referencia histórica por si fuera necesario inspeccionar el formato de intercambio anterior; no debe interpretarse como un flujo activo.
- **Script conservado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`

### 7. FileManagerS3
- **Función**: Abre la carpeta del shot en FileManagerS3
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`

### 8. Download Shot
- **Función**: Descarga el shot desde Wasabi S3
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Download.py`

### 9. Upload Shot
- **Función**: Sube el shot a Wasabi S3
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Upload.py`

### 10. Download Clip
- **Click normal**: Descarga la última versión disponible del clip
- **Shift+Click**: Descarga exactamente la versión seleccionada
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_DownloadClip.py`

### 11. Download AMF
- **Función**: Descarga la carpeta `_input/Look_Files` del shot del clip seleccionado desde Wasabi S3 (los `.amf`/`.cdl`/`.clf` necesarios para ver bien los renders de comp)
- **Script utilizado**: `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_DownloadAmf.py`
- **Comportamiento**: No chequea si la carpeta existe localmente; siempre dispara la descarga vía FileManagerS3 CLI sobre `<shot>/_input/Look_Files`

## Compatibilidad de Nomenclatura

El panel es compatible con ambos sistemas de nomenclatura utilizados en la empresa:

### Formato con Descripción (5 bloques)
```
PROYECTO_SEQ_SHOT_DESC1_DESC2_TASK_vVERSION
Ejemplo: PROJA_000_140_Chroma_Auto_comp_v19
```

### Formato Simplificado (3 bloques)
```
PROYECTO_SEQ_SHOT_TASK_vVERSION
Ejemplo: PROJB_080_010_comp_v007
```

El sistema detecta automáticamente el formato utilizado sin necesidad de configuración previa.

## Estructura del Panel

La lectura visual es intencional:

- **Flow:** cuatro botones verdes, Shot Priority verde/rojo y Reveal in Flow verde/gris.
- **S3:** los cinco botones siguientes comparten el gradiente violeta.
- El color refuerza el grupo, pero cada acción conserva un label explícito; no se depende solo del color.

### Botones Disponibles
1. **Create Shot** - Crea shots automáticamente en Flow
2. **Modify Shot** - Modifica un shot existente en Flow
3. **Check Shots Exist** - Chequea los tracks de task del contexto (Comp; también CG en Client)
4. **Thumbnail** - Reemplaza el thumbnail en Flow; con Shift guarda el snapshot local
5. **Shot Priority** - Cambia la prioridad del shot (alta ↔ normal)
6. **Reveal in Flow** - `Ctrl+Shift+F` - Abre la task preferida o el Shot en Flow
7. **FileManagerS3** - Abre carpeta del shot en FileManagerS3
8. **Download Shot** - Descarga el shot desde Wasabi S3
9. **Upload Shot** - Sube el shot a Wasabi S3
10. **Download Clip** - Descarga la última versión; con Shift descarga el clip seleccionado
11. **Download AMF** - Descarga la carpeta `_input/Look_Files` del shot del clip seleccionado

## Requisitos

- Hiero/Nuke Studio con acceso a Flow Production Tracking
- Credenciales configuradas en `SecureConfig_Reader.py`
- Clips con nombres de archivo que sigan el formato de nomenclatura estándar

## Uso

1. Seleccionar uno o más clips en el timeline de Hiero
2. Hacer clic en el botón deseado del panel
3. El script correspondiente se ejecutará automáticamente

## Notas Técnicas

- El panel utiliza funciones compartidas de `LGA_NKS_Flow_NamingUtils.py` para el parsing de nombres
- La detección de formato es automática y transparente para el usuario
- Los scripts llamados manejan sus propias interfaces de usuario (ventanas de estado, errores, etc.)
- Cada script conserva su propio contrato de ejecución. Las consultas remotas y
  transferencias que pueden demorar usan workers; la lectura o modificación de
  widgets y timeline vuelve al hilo principal.
- Compatible con caracteres Unicode (nombres con acentos, etc.)

## Scripts Relacionados

- `LGA_HieroTools/LGA_NKS_Coordination_Panel.py` - `FlowProdPanel.__init__()` define identidad visible, orden y categoría visual; `FlowProdPanel.create_buttons()` construye el layout; `create_thumbnail_for_selected_clip()` y `update_thumbnail_in_flow_for_selected_clip()` resuelven los dos gestos de Thumbnail. El nombre de módulo y `com.lega.FlowProdPanel` se conservan por compatibilidad.
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_StyleUtils.py` - `GRADIENT_COLORS` contiene los gradientes semánticos; `create_gradient_style()` compone estados normal, hover y pressed.
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShowInFlow.py` - Funcionalidad de Reveal in Flow
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_Thumbs.py` - `main()` guarda el snapshot local; `zoom_to_fill_simple()` y `crop_to_aspect_ratio()` preparan la imagen
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_UpdateThumb.py` - `update_thumbnail_in_flow()` inicia el reemplazo; `ThumbReplaceDialog` presenta la comparación; `UploadThumbWorker` sube sin bloquear la UI
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CreateShot.py` - Funcionalidad de Create Shot
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ModifyShot.py` - Funcionalidad de Modify Shot
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py` - Funcionalidad de Check Shots Exist
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_ShotPriority.py` - Funcionalidad de Shot Priority
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_PipeSync_CreatePsync.py` - Generación de archivos `.psync` portables
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_PipeSync_OpenPath.py` - Funcionalidad de PipeSync (Open)
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py` - Funcionalidad de FileManagerS3 (Open)
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Download.py` - Funcionalidad de Download Shot
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_Upload.py` - Funcionalidad de Upload Shot
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_DownloadClip.py` - Funcionalidad de Download Clip
- `LGA_HieroTools/LGA_NKS_Flow_S3_Panel_py/LGA_NKS_FileManagerS3_DownloadAmf.py` - Funcionalidad de Download AMF (carpeta `_input/Look_Files`)
- `LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py` - Utilidades compartidas de nomenclatura (usado por los scripts de producción)
