# Estándar de Headers Python - LGA Scripts

Documentación para estandarizar el formato de headers en todos los scripts Python del repositorio.

---

## Estructura General

```python
"""
____________________________________________________________________

  [NOMBRE_SCRIPT] v[X.XX] | Lega

  [Descripción del propósito del script]
  [Puede ocupar varias líneas si es necesario]

  v[X.XX]: [Cambio más reciente]
  v[X.XX]: [Cambio anterior]
  v[X.XX]: [Cambio anterior]
____________________________________________________________________
"""
```

---

## Reglas Detalladas

### 1. **Líneas de Separación (Guiones)**
- **Caracteres**: `_` (guión bajo)
- **Cantidad**: Exactamente **68 caracteres**
- **Ubicación**: Una al inicio y otra al final del header
- **Dentro de comillas**: Dentro de las comillas triples `"""`

```python
"""
____________________________________________________________________
```

### 2. **Línea en Blanco Después de Guiones Iniciales**
Siempre debe haber una línea en blanco entre los guiones superiores y el título.

### 3. **Línea de Título**
Formato: `  [NOMBRE] v[X.XX] | Lega`
- Dos espacios de indentación
- Nombre del script (puede incluir guiones como separadores)
- Versión en formato `v` + número
- Las versiones **SIEMPRE tienen dos dígitos después del punto** (v1.09, no v1.9)
- Separador ` | Lega`

### 4. **Línea en Blanco Después del Título**
Siempre hay una línea en blanco entre el título y la descripción o changelog.

### 5. **Sección de Descripción (Opcional)**
- Solo si el script tiene un propósito claramente definido
- Puede ocupar múltiples líneas
- Indentación: 2 espacios
- **NO inventar descripciones** si no están en el script original

### 6. **Línea en Blanco Antes del Changelog**
Si hay descripción, debe haber una línea en blanco antes de las versiones.

### 7. **Sección de Changelog (Versiones)**
- Formato: `  v[X.XX]: [Descripción del cambio]`
- Dos espacios de indentación
- **Las versiones SIEMPRE tienen dos dígitos después del punto** (v2.00, v1.09, nunca v2.0 o v1.9)
- **SIN líneas en blanco entre versiones**
- **Las versiones DEBEN estar en orden descendente** (de mayor a menor)
  - ✅ Correcto: v1.18, v1.16, v1.15, v1.10
  - ❌ Incorrecto: v1.16, v1.15, v1.10, v1.18 (desordenado o inverso)
  - Si encuentras un changelog desordenado, reorganiza las versiones antes de standarizar
- Si una versión ocupa múltiples líneas, las siguientes líneas se indentan más:

```python
  v2.49: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
         Optimizado espaciado del layout y dimensiones de botones para mejor UX
```

### 8. **Líneas de Separación Finales**
Los guiones de cierre están inmediatamente después del último cambio de versión, sin línea en blanco.

---

## Casos Especiales

### Caso A: Script CON descripción y changelog

```python
"""
____________________________________________________________________

  LGA_MyScript_Panel v2.15 | Lega

  Panel de herramientas para operaciones complejas del timeline.
  Soporta múltiples modos de selección y batch processing.

  v2.15: Agregado soporte para multi-selección con Shift+Click
  v2.14: Optimización de rendimiento en loops grandes
  v2.13: Fix de crash al procesar clips sin media
  v2.12: Interfaz mejorada con tooltips dinámicos
____________________________________________________________________
"""
```

### Caso B: Script SOLO con changelog (sin descripción)

```python
"""
____________________________________________________________________

  LGA_SimpleScript v1.09 | Lega

  v1.09: Actualizado para usar estilos dinámicos
  v1.08: Agregado sistema de logging
  v1.07: Fix en selección de clips
____________________________________________________________________
"""
```

### Caso C: Script CON descripción multi-línea

```python
"""
____________________________________________________________________

  LGA_ComplexPanel v3.22 | Lega

  Panel integrado para gestión de proyectos con Flow.
  - Escanea proyectos automáticamente
  - Permite abrir secuencias cross-project
  - Sincroniza estados con Flow en tiempo real
  - Compatible con ambos sistemas de nomenclatura (PROY_SEQ_SHOT y extendido)

  v3.22: Migrado a sistema de logging centralizado
  v3.21: Fix en detección de rutas en diferentes OS
____________________________________________________________________
"""
```

---

## Validación Rápida

✅ Checklist antes de hacer commit:

- [ ] Guiones de 68 caracteres arriba y abajo
- [ ] Línea en blanco después de guiones iniciales
- [ ] Título con versión en formato `vX.XX` (dos dígitos)
- [ ] Línea en blanco después del título
- [ ] Descripción (si aplica) sin inventar contenido
- [ ] Línea en blanco antes del changelog
- [ ] Changelog sin líneas en blanco entre versiones
- [ ] **Versiones en orden descendente ESTRICTO** (v1.18, v1.16, v1.15, v1.10 – nunca desordenadas)
- [ ] Todas las versiones con dos dígitos (`v1.00`, `v1.99`, nunca `v1.0` o `v1.9`)
- [ ] Guiones de cierre sin línea en blanco antes

---

## Notas Importantes

1. **No inventar información**: Si no existe descripción en el script, no la inventes. Ve directo al changelog.

2. **Mantener versiones**: Respeta las versiones existentes. Solo agrega nueva versión si hay un cambio real.

3. **Dos dígitos en versión**: Siempre `v1.09`, nunca `v1.9`. Esto mantiene consistencia visual.
   - Aplica a la versión en el título (ej: `v2.15 | Lega`)
   - Aplica a TODAS las versiones en el changelog (ej: `v2.15:`, `v2.00:`, `v1.99:` – NUNCA `v2.0:` o `v1.9:`)

4. **Indentación**: Todos los niveles usan **2 espacios**, nunca tabs.

5. **Ordenamiento DESCENDENTE ESTRICTO**: El changelog SIEMPRE de versión más nueva (arriba) a más antigua (abajo).
   - No puede haber versiones desordenadas en el changelog
   - Si encuentras: v1.16, v1.15, v1.10, v1.18 → reorganiza a: v1.18, v1.16, v1.15, v1.10
   - Esto asegura que el cambio más reciente siempre está al principio

---

## Ejemplo Completo Anotado

```python
"""                                      # Apertura de docstring
____________________________________________________________________  # 68 guiones

  LGA_AutomationTool v1.23 | Lega       # Título (2 espacios indent)
                                         # Línea en blanco
  Herramienta de automatización para    # Descripción (2 espacios indent)
  tareas repetitivas en Hiero.           # Continúa descripción
  Soporta modo batch y selecciones.      # Continúa descripción
                                         # Línea en blanco
  v1.23: Agregado soporte para roto      # Changelog (2 espacios indent)
  v1.22: Fix en detección de versiones   # Sin línea en blanco
  v1.21: Mejora de performance en loops  # Sin línea en blanco
         con clips grandes               # Continuación indentada más
  v1.20: Soporte multi-task agregado     # Sin línea en blanco
____________________________________________________________________  # 68 guiones (sin línea en blanco antes)
"""                                      # Cierre de docstring
```

---

## Aplicación en el Repositorio

Todos los scripts LGA_NKS_*.py en la raíz deben seguir este formato:

- `LGA_NKS_Edit_Panel.py` ✅
- `LGA_NKS_Flow_Panel.py` ✅
- `LGA_NKS_Coordination_Panel.py` ✅
- `LGA_NKS_Assignee_Panel.py` ✅
- `LGA_NKS_Review_Panel.py` ✅
- `LGA_NKS_ViewerTL_Panel.py` ✅
- `LGA_NKS_Projects_Panel.py` ✅
- `LGA_NKS_ClipColor_Panel.py` ✅

---

**Última actualización**: 2026-05-02  
**Versión del estándar**: 1.0
