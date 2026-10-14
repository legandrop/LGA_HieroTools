> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Especificación de Compatibilidad de Nomenclatura - LGA_NKS_Flow (Hiero/Nuke Studio)

## Introducción

Este documento describe la evolución del sistema de nomenclatura utilizado en la empresa y los cambios necesarios para hacer que los scripts de **LGA_NKS_Flow** (Hiero/Nuke Studio) sean compatibles con ambos sistemas de naming.

**Nota:** Este proyecto está basado en la experiencia previa del proyecto de Nuke (LGA_ToolPack), donde se implementó exitosamente la compatibilidad de nomenclatura. Ver sección "Referencia: Proyecto Nuke" al final del documento.

**Actualización:** El formato de series (`PROYECTO_TEMP_EP_SEQ_SHOT`) ya no se detecta: no se usa más. Ver "Sistema de Nomenclatura para Series" y "Técnica de Detección Implementada".

## Sistema de Nomenclatura Actual (Con Campos de Descripción)

### Estructura del Shotname
El sistema actual utiliza una estructura de 5 componentes principales separados por guiones bajos:

```
PROYECTO_SEQ_SHOT_DESC1_DESC2
```

**Ejemplo:**
```
PROJA_000_140_Chroma_Auto
```

### Estructura Completa de Archivos
```
PROYECTO_SEQ_SHOT_DESC1_DESC2_TASK_vVERSION.EXT
```

**Ejemplos:**
- Script: `PROJA_000_140_Chroma_Auto_comp_v19.nk`
- Video: `PROJA_000_140_Chroma_Auto_comp_v18.mov`
- Secuencia: `PROJA_000_140_Chroma_Auto_comp_v19_1001.exr`

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJA` |
| SEQ | 2 | Número de secuencia (3 dígitos) | `000` |
| SHOT | 3 | Número de shot (3-4 dígitos) | `140` |
| DESC1 | 4 | Primera descripción | `Chroma` |
| DESC2 | 5 | Segunda descripción | `Auto` |
| TASK | 6 | Nombre de la tarea | `comp` |
| VERSION | 7 | Número de versión | `v19` |

### Uso en Flow/ShotGrid
- **Shot Code:** `SEQ_SHOT` (ej: `000_140`)
- **Task:** `DESC1_DESC2_TASK` (ej: `Chroma_Auto_comp`)

## Sistema de Nomenclatura Simplificado (Sin Campos de Descripción)

### Estructura del Shotname
El sistema simplificado elimina los campos de descripción:

```
PROYECTO_SEQ_SHOT
```

**Ejemplo:**
```
PROJA_000_140
```

### Estructura Completa de Archivos
```
PROYECTO_SEQ_SHOT_TASK_vVERSION.EXT
```

**Ejemplos:**
- Script: `PROJA_000_140_comp_v19.nk`
- Video: `PROJA_000_140_comp_v18.mov`
- Secuencia: `PROJA_000_140_comp_v19_1001.exr`

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJA` |
| SEQ | 2 | Número de secuencia (3 dígitos) | `000` |
| SHOT | 3 | Número de shot (3-4 dígitos) | `140` |
| TASK | 4 | Nombre de la tarea | `comp` |
| VERSION | 5 | Número de versión | `v19` |

### Uso en Flow/ShotGrid
- **Shot Code:** `SEQ_SHOT` (ej: `000_140`)
- **Task:** `TASK` (ej: `comp`)

## Sistema de Nomenclatura para Series (ya no se detecta)

Existió un formato con un bloque de temporada/episodio antes de la secuencia
(`PROYECTO_TEMP_EP_SEQ_SHOT`, ej. `PROJB_101_060_010`). Se reconocía porque
los tres bloques siguientes al proyecto empezaban con dígito, y entonces la
base del shot pasaba a ser de 4 bloques.

**Desde NamingUtils v1.22 esa detección no existe.** Ya no se usan series, y
la regla rompía un caso real: un shot con descripción cuyo primer bloque es
numérico, como `PROJA_000_115_010_Desc` (`SEQ=000`, `SHOT=115`,
`DESC1=010`, `DESC2=Desc`). Se leía como serie con base de 4 y una sola
descripción de dos bloques (`Desc_comp`), así que el shot code se llevaba la
task y el Pull no encontraba ningún shot en la DB.

Un shot viejo de serie se sigue resolviendo bien cuando el archivo termina en
una task con track o en un plate (por el ancla, ver más abajo). Lo que se
pierde es el caso sin ancla: un archivo de serie sin task o con una disciplina
CG al final.

## Sistema de Nomenclatura con Vendor Code

### Estructura del Shotname
Cuando el estudio trabaja como vendor de un proyecto, el shotname lleva el codigo
del vendor **al final del bloque base**, despues de secuencia y shot:

```
PROYECTO_SEQ_SHOT_VENDOR
```

**Ejemplo:**
```
PROJA_1013_0800_VEN
```

Se combina con las demas variantes: puede haber descripcion
(`PROYECTO_SEQ_SHOT_VENDOR_DESC1_DESC2`) y puede aplicarse sobre la base de
serie (`PROYECTO_TEMP_EP_SEQ_SHOT_VENDOR`).

### Campos y su Significado

| Campo | Posición | Descripción | Ejemplo |
|-------|----------|-------------|---------|
| PROYECTO | 1 | Código del proyecto | `PROJA` |
| SEQ | 2 | Número de secuencia | `1013` |
| SHOT | 3 | Número de shot | `0800` |
| VENDOR | 4 | Código del vendor | `VEN` |
| TASK | 5 | Nombre de la tarea | `comp` |
| VERSION | 6 | Número de versión | `v001` |

### Por que el vendor NO se detecta por estructura

Los vendor codes validos se leen de la **DB de PipeSync**, no se adivinan. La
fuente de verdad es Flow: los codigos se cargan en el Projects tab de PipeSync,
viajan en el envelope de Project Settings del proyecto y quedan en
`project_settings_cache.settings_json` de `pipesync_stats.db`, bajo la clave
`vendors`.

El motivo es que una regla estructural no alcanza. Estos dos nombres son
indistinguibles por forma:

```
PROJA_1013_0800_VEN     → VEN es un VENDOR (parte del shot name)
PROJA_1048_060_Compo    → Compo es una TASK (no es parte del shot name)
```

Los dos tienen un bloque alfabetico despues de dos bloques numericos. Solo la
lista de vendors del proyecto permite decidir cual es cual.

**Degradacion:** si PipeSync nunca sincronizo, la DB no existe o el proyecto no
tiene vendors cargados, el bloque no se reconoce como vendor. No hay fallback
estructural, a proposito. Desde v1.22 eso solo afecta al shot code cuando el
archivo NO termina en una task con track o un plate: con `_comp` el ancla
resuelve `PROJA_1013_0800_VEN` igual, aunque `extract_vendor_token()` siga
sin devolver el vendor (el acceso de vendor depende de la DB, no del ancla).

### Uso en Flow/ShotGrid (Vendor)
- **Shot Code:** incluye el bloque del vendor (ej: `PROJA_1013_0800_VEN`)
- **Task:** el bloque que sigue al vendor (ej: `comp`)

### Token interno SUP

`SUP` ocupa la misma posición que un vendor externo y también forma parte del
Shot Code en Hiero y Flow: `PROJA_1013_0800_SUP_comp` crea o encuentra el shot
`PROJA_1013_0800_SUP` y resuelve la task `comp`. No viene de `vendors[]`: vive
como `INTERNAL_VENDOR_TOKEN` en el helper central para que siga reconociéndose
sin depender de la sincronización de PipeSync.

Es interno solo para los permisos: no crea `sg_vendor_groups` ni altas en
`Project.users`; las Tasks habilitadas se asignan a Lega. Los vendors externos
siguen requiriendo la validación de PipeSync para distinguirlos de una task o
descripción.

### Formato historico (vendor adelante)
Existe tambien la variante `PROYECTO_VENDOR_SEQ_SHOT`, con el vendor pegado al
proyecto. Se sigue soportando por estructura (`_is_vendor_format`), sin
consultar la DB.

## Problemas Identificados en los Scripts de Hiero

### 1. LGA_NKS_Flow_CreateShot.py (Problema CRÍTICO)
**Problema:** Parsing rígido que asume 5 campos para el shot_code
```python
shot_code = "_".join(parts[:5])  # Siempre toma primeros 5 campos
```

**Impacto:**
- Con descripción: `['PROJA', '000', '140', 'Chroma', 'Auto']` → `PROJA_000_140_Chroma_Auto` ✓
- Sin descripción: `['PROJA', '000', '140', 'comp', 'v19']` → `PROJA_000_140_comp_v19` ❌

### 2. LGA_NKS_Flow_Pull.py (Problema CRÍTICO)
**Problema:** Extracción de shot_code asume siempre 5 campos
```python
shot_code = "_".join(parts[:5])
```

**Impacto:**
- Genera shot codes incorrectos para formato simplificado
- Afecta la búsqueda de shots en Flow/ShotGrid

### 3. LGA_NKS_Flow_Thumbs.py y LGA_NKS_Flow_CreateShot_Thumbs.py (Problema CRÍTICO)
**Problema:** Función `get_shot_name_from_selected_clip()` asume 5 campos
```python
if len(parts) >= 5:
    shot_code = "_".join(parts[:5])
```

**Impacto:**
- No funciona correctamente con formato simplificado
- Puede generar nombres incorrectos para thumbnails

## Técnica de Detección Implementada

### 🎯 **Detección Inteligente por Bloques Base**

**Principio:** Primero se mira el último bloque antes de la versión. Si se lo
reconoce, el shot es todo lo anterior. Solo si no se lo reconoce se cuentan
bloques. Todo vive en `_analyze_shotname()`.

**Lógica:**
```
1. ANCLA
Si el último bloque es una task con track (comp, roto, cleanup, cg, de
LGA_NKS_TaskScope), un alias (compo) o un plate (aPlate, bPlate...: ^[a-z]plate$),
y quedan al menos 3 bloques antes:
    → task = ese bloque, shot = todo lo anterior

2. CONTEO (último bloque no reconocido: disciplinas CG en client, archivos sin task)
Base = 3 bloques (PROYECTO_SEQ_SHOT), o 4 con el vendor adelante (PROYECTO_VENDOR_SEQ_SHOT)
Si el bloque que sigue a la base es un vendor code conocido (DB de PipeSync) o SUP:
    → La base crece 1 (PROYECTO_SEQ_SHOT_VENDOR)
Si quedan al menos 2 bloques más:
    → Son DESC1_DESC2 y forman parte del shot
El bloque siguiente, si existe, es la task
```

El ancla no depende de cuántos bloques tiene la descripción ni de que el vendor
esté cargado en la DB. El conteo sí: supone descripciones de dos bloques y
necesita la DB para reconocer un vendor.

**Casos de Uso:**
- `PROJA_000_140_comp_v19.exr` → **ancla** → Shot Code: `PROJA_000_140`
- `PROJA_1013_0800_VEN_comp_v001.exr` → **ancla** → Shot Code: `PROJA_1013_0800_VEN`
- `PROJA_1013_0800_SUP_comp_v001.exr` → **ancla** → Shot Code: `PROJA_1013_0800_SUP`
- `PROJA_000_140_Chroma_Auto_comp_v19.exr` → **ancla** → Shot Code: `PROJA_000_140_Chroma_Auto`
- `PROJA_000_140_Chroma_comp_v19.exr` → **ancla** (descripción de un bloque) → Shot Code: `PROJA_000_140_Chroma`
- `PROJA_000_115_010_Desc_comp_v001.exr` → **ancla** → Shot Code: `PROJA_000_115_010_Desc`
- `PROJA_000_140_aPlate_v01_1001.exr` → **ancla** (plate) → Shot Code: `PROJA_000_140`
- `PROJA_000_140_Chroma_Auto_layout_v001.exr` → **conteo** → Shot Code: `PROJA_000_140_Chroma_Auto`, task `layout`
- `PROJA_1013_0800_VEN_layout_v001.exr` → **conteo** → con VEN en la DB: `PROJA_1013_0800_VEN`; sin VEN en la DB: `PROJA_1013_0800_VEN_layout` y sin task

Medido contra los 513 shots de la DB local con 8 sufijos (comp, roto, cleanup,
Compo, aPlate, lighting, layout y sin task): el parser anterior acertaba 4000
de 4104 nombres y este acierta 4101. Los 3 que fallan son el único shot de
serie, sin ancla.

## Estrategia de Solución

### ✅ **IMPLEMENTAR:** Módulo Compartido con Funciones Centralizadas

**Estrategia:** Crear un módulo compartido `LGA_NKS_Flow_NamingUtils.py` con funciones reutilizables que todos los scripts de Hiero pueden usar.

**Ventajas:**
- ✅ Código centralizado y mantenible
- ✅ Consistencia entre todos los scripts
- ✅ Fácil de actualizar y testear
- ✅ Reutilizable en futuros scripts

## Archivos que Requieren Modificación

### Archivos Críticos (Deben modificarse)

1. **LGA_NKS_Flow_CreateShot.py** ✅ COMPLETADO
   - ✅ **Creado** módulo compartido `LGA_NKS_Flow_NamingUtils.py`
   - ✅ **Actualizado** para usar funciones compartidas
   - ✅ Detección automática de formato en `get_shot_name_from_selected_clip()`
   - ✅ Actualizado `HieroOperations.get_selected_clips_info()`

2. **LGA_NKS_Flow_Pull.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code en `process_selected_clips()`
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()`
   - ✅ **Actualizado** extracción de `project_name` y `task_name` usando funciones compartidas
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

3. **LGA_NKS_Flow_Thumbs.py** ✅ COMPLETADO
   - ✅ **Actualizado** función `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - ✅ **Actualizado** función `get_project_name_from_clip()` para usar `extract_project_name()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

4. **LGA_NKS_Flow_CreateShot_Thumbs.py** ✅ COMPLETADO
   - ✅ **Actualizado** función `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

5. **LGA_NKS_Flow_Shot_info.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code y project_name en `process_selected_clips()`
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()`
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

6. **LGA_NKS_Flow_Push.py** ✅ COMPLETADO
   - ✅ **Actualizado** extracción de shot_code, project_name y task_name en `update_local_database()`
   - ✅ Usa funciones compartidas para detección automática de formato
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

7. **LGA_NKS_Flow_Push_connector.py** ✅ COMPLETADO
   - ✅ **Actualizado** `execute_full_push_operation()` para usar funciones compartidas
   - ✅ **Actualizado** `check_version()` para usar funciones compartidas
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

8. **LGA_NKS_Flow_Panel.py** ✅ COMPLETADO
   - ✅ **Actualizado** `parse_exr_name()` para usar `clean_base_name()` y validación flexible
   - ✅ Compatible con ambos formatos de nomenclatura
   - ✅ Compatibilidad 100% hacia atrás con formato con descripción

9. **Otros scripts de LGA_NKS_Flow** (Pendiente revisión)
   - Revisar si necesitan actualización para compatibilidad

## Criterios de Éxito

1. **Compatibilidad hacia atrás:** Los scripts funcionan exactamente igual con el sistema actual (con descripción)
2. **Detección automática:** Cada script detecta automáticamente si hay descripción o no SIN configuración previa
3. **Código centralizado:** Todas las funciones de naming están en un módulo compartido
4. **Shot codes correctos:** Se generan códigos de shot correctos para Flow en ambos formatos
5. **Ancla en task o plate:** si el último bloque es una task con track o un plate, el shot es todo lo anterior (las series ya no se detectan)
6. **Sin errores:** No se producen errores independientemente del formato del nombre
7. **Transparente para el usuario:** El usuario no necesita configurar nada, todo funciona automáticamente

## Estado del Proyecto

### ✅ Fase 1: Creación del Módulo Compartido - COMPLETADA
1. ✅ **Creado** `LGA_NKS_Flow_NamingUtils.py`
   - Función `detect_shotname_format()` - Detecta formato por bloques base y serie
   - Función `extract_shot_code()` - Extrae shot_code automáticamente
   - Función `extract_project_name()` - Extrae nombre del proyecto
   - Función `clean_base_name()` - Limpia nombres de archivo
   - Función `extract_task_name()` - Extrae nombre de la tarea

### ✅ Fase 2: LGA_NKS_Flow_CreateShot.py - COMPLETADA
2. ✅ **Actualizado** `LGA_NKS_Flow_CreateShot.py` v1.1
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Implementada detección automática en `get_shot_name_from_selected_clip()`
   - Actualizado `HieroOperations.get_selected_clips_info()` para usar funciones compartidas
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 3: LGA_NKS_Flow_Pull.py - COMPLETADA
3. ✅ **Actualizado** `LGA_NKS_Flow_Pull.py` v3.28
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()`
   - Actualizado extracción de `shot_code`, `project_name` y `task_name` en `process_selected_clips()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 4: LGA_NKS_Flow_Shot_info.py - COMPLETADA
4. ✅ **Actualizado** `LGA_NKS_Flow_Shot_info.py` v1.83
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()`
   - Actualizado extracción de `shot_code` y `project_name` en `process_selected_clips()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 5: Scripts de Thumbs - COMPLETADA
5. ✅ **Actualizado** `LGA_NKS_Flow_Thumbs.py` v1.01
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - Actualizado `get_project_name_from_clip()` para usar `extract_project_name()` y `clean_base_name()`
   - Compatibilidad 100% hacia atrás con formato con descripción

6. ✅ **Actualizado** `LGA_NKS_Flow_CreateShot_Thumbs.py` v1.01
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `get_shot_name_from_selected_clip()` para usar `extract_shot_code()`
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 6: LGA_NKS_Flow_Push.py y Archivos Relacionados - COMPLETADA
7. ✅ **Actualizado** `LGA_NKS_Flow_Push.py` v3.81
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `Worker.update_local_database()` para usar `extract_shot_code()`, `extract_project_name()` y `extract_task_name()`
   - Compatibilidad 100% hacia atrás con formato con descripción

8. ✅ **Actualizado** `LGA_NKS_Flow_Push_connector.py`
   - Importadas funciones de `LGA_NKS_Flow_NamingUtils.py` con fallback completo del sistema dual
   - Actualizado `execute_full_push_operation()` para usar funciones compartidas
   - Actualizado `check_version()` para usar funciones compartidas
   - Compatibilidad 100% hacia atrás con formato con descripción

9. ✅ **Actualizado** `LGA_NKS_Flow_Panel.py` v2.46
   - Importada función `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
   - Actualizado `parse_exr_name()` para usar `clean_base_name()` y validación flexible
   - Compatible con ambos formatos de nomenclatura
   - Compatibilidad 100% hacia atrás con formato con descripción

### ✅ Fase 7: Scripts de LGA_NKS_Edit - COMPLETADA
10. ✅ **Actualizado** `LGA_NKS_CompareEXR_to_aPlate.py` v1.14
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_clip_name()` para usar funciones centralizadas con detección automática de formato
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

11. ✅ **Actualizado** `LGA_NKS_CompareVerToEditref.py` v1.14
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_clip_name()` para usar funciones centralizadas con detección automática de formato
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

12. ✅ **Actualizado** `LGA_NKS_MatchVerToEXR.py` v0.5
    - Importadas funciones `extract_shot_code()` y `clean_base_name()` de `LGA_NKS_Flow_NamingUtils.py`
    - Actualizado `parse_exr_name()` para usar `clean_base_name()`
    - Actualizado extracción de `base_without_version` para usar `extract_shot_code()` en lugar de remover versión manualmente
    - Compatible con ambos sistemas de nomenclatura (5 bloques con descripción / 3 bloques simplificado)
    - Compatibilidad 100% hacia atrás con formato con descripción

### Fase 8: Revisión Final (Pendiente)
13. **Revisar** otros scripts que puedan necesitar actualización

### Fase 9: Testing y Validación (Pendiente)
14. **Probar** exhaustivamente con casos reales de ambos formatos
15. **Validar** funcionamiento correcto con proyectos existentes
16. **Crear** casos de prueba automatizados

## Implementación Técnica Específica

### LGA_NKS_Flow_NamingUtils.py (Módulo Compartido)
```python
# ✅ IMPLEMENTADO - Módulo compartido para scripts de Hiero

def detect_shotname_format(base_name):
    """Detecta formato basado en campo 5"""
    parts = base_name.split("_")
    if len(parts) >= 5:
        field_5 = parts[4]
        # Si campo 5 es versión -> formato simplificado
        return not (field_5.startswith('v') and field_5[1:].isdigit())
    return False  # Menos de 5 campos = simplificado

def extract_shot_code(base_name):
    """Extrae shot_code detectando formato automáticamente"""
    has_description = detect_shotname_format(base_name)
    parts = base_name.split("_")
    
    if has_description:
        return "_".join(parts[:5])  # PROYECTO_SEQ_SHOT_DESC1_DESC2
    else:
        return "_".join(parts[:3])  # PROYECTO_SEQ_SHOT

def clean_base_name(file_name):
    """Limpia el nombre de archivo removiendo extensiones y versiones"""
    base_name = re.sub(r"_%04d\.exr$", "", file_name)
    base_name = re.sub(r"_\d{4}\.exr$", "", base_name)
    base_name = re.sub(r"_v\d+$", "", base_name)
    base_name = os.path.splitext(base_name)[0]
    return base_name
```

### LGA_NKS_Flow_CreateShot.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)

# En HieroOperations.get_selected_clips_info():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Pull.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
    clean_base_name,
)

# En parse_exr_name():
base_name = clean_base_name(file_name)

# En process_selected_clips():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
task_name_extracted = extract_task_name(base_name)
if task_name_extracted:
    task_name = task_name_extracted.lower()
else:
    # Fallback para casos edge
    ...
```

### LGA_NKS_Flow_Shot_info.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En parse_exr_name():
base_name = clean_base_name(file_name)

# En process_selected_clips():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Thumbs.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    clean_base_name,
)

# En get_project_name_from_clip():
base_name = clean_base_name(filename)
project_name = extract_project_name(base_name)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_CreateShot_Thumbs.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    clean_base_name,
)

# En get_shot_name_from_selected_clip():
base_name = clean_base_name(exr_name)
shot_code = extract_shot_code(base_name)
```

### LGA_NKS_Flow_Push.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
)

# En Worker.update_local_database():
project_name = extract_project_name(self.base_name)
shot_code = extract_shot_code(self.base_name)
task_name_extracted = extract_task_name(self.base_name)
if task_name_extracted:
    task_name = task_name_extracted.lower()
else:
    # Fallback para casos edge
    ...
```

### LGA_NKS_Flow_Push_connector.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas con fallback completo

from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_task_name,
)
# Si el import falla, usa fallback con lógica completa del sistema dual

# En execute_full_push_operation():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)  # Detecta formato automáticamente
task_name_extracted = extract_task_name(base_name)

# En check_version():
project_name = extract_project_name(base_name)
shot_code = extract_shot_code(base_name)  # Detecta formato automáticamente
```

### LGA_NKS_Flow_Panel.py
```python
# ✅ IMPLEMENTADO - Uso de funciones compartidas

from LGA_NKS_Flow_NamingUtils import clean_base_name

# En parse_exr_name():
base_name = clean_base_name(exr_name)
# Validación flexible compatible con ambos formatos
```

---

## Referencia: Proyecto Nuke (LGA_ToolPack)

Esta sección documenta el trabajo previo realizado en el proyecto de Nuke, que sirvió como base para este proyecto de Hiero.

### Problemas Identificados en Scripts de Nuke

1. **LGA_showInlFlow.py** - Parsing rígido que asume 5 campos
2. **LGA_Write_Presets.py** - Fórmulas TCL hardcodeadas
3. **LGA_Write_PathToText.py** - Cálculo de profundidad fijo

### Estado del Proyecto Nuke

#### ✅ Fase 1: Limpieza - COMPLETADA
- ✅ Eliminado `LGA_ToolPack_settings_ShotName.py`
- ✅ Eliminado botón "Configure Shot Naming" del menú

#### ✅ Fase 2A: LGA_showInlFlow.py - COMPLETADA
- ✅ Implementada detección inteligente por campo 5
- ✅ Generación correcta de shot_code para ambos formatos

#### ✅ Fase 2B: LGA_Write_Presets.py - COMPLETADA
- ✅ Implementado ajuste dinámico de fórmulas TCL
- ✅ Detección automática de formato
- ✅ Ajuste dinámico +2 bloques cuando se detecta formato con descripción

### Implementación Técnica Nuke

#### LGA_showInlFlow.py
```python
# ✅ IMPLEMENTADO - Detección inteligente por campo 5
parts = base_name.split("_")

is_simplified_format = False
if len(parts) >= 5:
    field_5 = parts[4]
    if field_5.startswith('v') and len(field_5) > 1 and field_5[1:].isdigit():
        is_simplified_format = True

if is_simplified_format:
    shot_code = "_".join(parts[:3])  # proyecto_seq_shot
else:
    shot_code = "_".join(parts[:5])  # proyecto_seq_shot_desc1_desc2
```

#### LGA_Write_Presets.py
```python
# ✅ IMPLEMENTADO - Detección y ajuste dinámico de fórmulas TCL

def detect_shotname_format():
    """Detecta formato basado en script actual de Nuke"""
    script_path = nuke.root().name()
    if not script_path or script_path == "Root":
        return False
    
    base_name = re.sub(r"\.nk$", "", os.path.basename(script_path))
    parts = base_name.split("_")
    
    if len(parts) >= 5:
        field_5 = parts[4]
        return not (field_5.startswith('v') and field_5[1:].isdigit())
    return False

def adjust_tcl_formulas(presets, has_description):
    """Ajusta fórmulas TCL dinámicamente"""
    if not has_description:
        return presets
    
    for preset in presets.values():
        if "file_pattern" in preset:
            preset["file_pattern"] = re.sub(
                r"\] 0 (\d+)\]", 
                lambda m: f"] 0 {int(m.group(1)) + 2}]", 
                preset["file_pattern"]
            )
    return presets
```
