> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_MatchVerToEXR

Herramienta para sincronizar versiones entre tracks `_comp_` y `_compRev_` en Hiero/Nuke Studio.

## Descripción

Busca la versión actual de los clips del track `_comp_` (configurado en `TRACK_comp_EXR`) e intenta subir la versión de los clips correspondientes del track `_compRev_` (configurado en `TRACK_comp_REV`) a la misma versión. Solo procesa clips que contengan "_comp_" en su nombre.

**Tracks utilizados:**
- **Track `_comp_` (`TRACK_comp_EXR`)**: Contiene los archivos EXR con el render de COMP
- **Track `_compRev_` (`TRACK_comp_REV`)**: Contiene los archivos MOV o MXF con el render de COMP

## Archivos principales

- **Script principal:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel_py\LGA_NKS_MatchVerToEXR.py`
- **Panel de control:** `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Review_Panel.py`

## Acceso

**Botón del panel:** "Match Rev Ver" en Review Panel
- **Click normal:** Procesa clips usando método híbrido (prioriza selecciones múltiples, luego playhead, luego fallback a selección)
- **Shift + Click:** Fuerza procesamiento de todos los clips independientemente de la selección

## Funcionamiento

### Requisitos
- Secuencia activa con tracks:
  - `_comp_` (configurado en `TRACK_comp_EXR`): Track que contiene los archivos EXR con el render de COMP
  - `_compRev_` (configurado en `TRACK_comp_REV`): Track que contiene los archivos MOV o MXF con el render de COMP
- Clips con "_comp_" en el nombre del archivo

### Proceso
1. Analiza versiones de clips del track `_comp_` (usando método híbrido: selecciones múltiples > playhead > selección)
2. Busca clips correspondientes en el track `_compRev_` por nombre base
3. Actualiza clips del track `_compRev_` a la versión más alta disponible
4. Si la versión del track `_comp_` no está disponible, agrega tag rojo "Version Mismatch"
5. Muestra ventana con resultados del proceso

### Estados de resultado
- **Updated:** Clip del track `_compRev_` actualizado exitosamente
- **Already Matched:** Las versiones ya coincidían
- **Version Not Available:** La versión del track `_comp_` no existe para el clip del track `_compRev_`

## Funciones principales

### `match_exr_to_rev(force_all_clips=False)`
Función principal que inicializa la GUI y ejecuta el proceso.

### `HieroOperations.process_tracks()`
Lógica principal que:
- Detecta tracks `_comp_` y `_compRev_` usando variables centralizadas (`TRACK_comp_EXR` y `TRACK_comp_REV`)
- Procesa clips usando método híbrido (selecciones múltiples > playhead > selección) o todos si `force_all_clips=True`
- Actualiza versiones y agrega tags según resultado

### `VersionMatcherGUI`
Interfaz que muestra resultados en tabla con:
- Nombre del shot
- Versión del track `_comp_`
- Versión anterior del track `_compRev_`
- Estado del proceso

## Notas técnicas

- Utiliza expresiones regulares para extraer números de versión
- Maneja archivos EXR con secuencias (%04d) y archivos de video
- Implementa sistema de undo para reversión de cambios
- Compatible con selección múltiple y procesamiento masivo
- Usa módulo centralizado `LGA_NKS_GetClip` para obtener clips (método híbrido)
- Los nombres de tracks son configurables mediante variables centralizadas en `LGA_NKS_GetClip.py`:
  - `TRACK_comp_EXR = "_comp_"` (track que contiene los EXR con el render de COMP)
  - `TRACK_comp_REV = "_compRev_"` (track que contiene los MOV o MXF con el render de COMP)
