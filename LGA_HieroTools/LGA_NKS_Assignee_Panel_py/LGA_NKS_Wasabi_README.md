> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA NKS Wasabi - Gestión Automática de Políticas IAM

Este módulo automatiza la creación y gestión de políticas de acceso IAM en Wasabi basándose en los clips seleccionados en Hiero.

## Scripts Principales

### `LGA_NKS_Wasabi_PolicyAssign.py`
**Implementación histórica de asignación directa.** Se conserva para uso manual y
diagnóstico, pero el Assignee Panel ya no la invoca. Tanto el click normal como
Shift+Click pasan por el motor canónico instalado de PipeSync para evitar dos
escritores con políticas diferentes.

**Funcionalidad:**
- Obtiene rutas de clips seleccionados en el timeline de Hiero
- Parsea las rutas para extraer bucket, carpeta y subcarpeta
- **Valida y repara policies corruptas** antes de modificarlas
- Detecta si la política ya existe y la actualiza sin duplicar permisos
- Crea nueva política si no existe
- Asigna la política al usuario especificado
- Maneja casos donde la policy existente tiene statements inválidos

**Configuración:**
- Recibe el usuario como parámetro en `main(username=None)`
- Por defecto usa "TestPoli" si no se especifica usuario
- Nombre de política: `{username}_policy`
- Utiliza credenciales seguras desde PipeSync (SecureConfig_Reader)

**Funciones principales:**
- `merge_policy_statements()`: Combina policies existentes con nuevos permisos
- `create_and_manage_policy()`: Gestiona la creación/actualización de policies

### `LGA_NKS_Wasabi_PolicyUnassign.py`
**Script de gestión** que lee policies existentes y permite eliminar shots específicos de forma visual.

**Funcionalidad:**
- Lee la policy existente del usuario especificado
- **Valida y repara policies corruptas** antes y después de modificarlas
- Extrae automáticamente los nombres de shots desde los recursos S3
- Muestra una ventana con lista scrolleable de shots asignados
- Permite eliminar shots individuales con botón "✕" 
- Actualiza la policy en tiempo real eliminando permisos específicos
- Gestiona automáticamente las versiones de policies (límite de 5)
- **Previene la creación de policies inválidas** al eliminar todos los shots

**Configuración:**
- Recibe el usuario como parámetro en `main(username=None)`
- Por defecto usa "TestPoli" si no se especifica usuario
- Lee política: `{username}_policy`
- Utiliza credenciales seguras desde PipeSync (SecureConfig_Reader)

**Funciones principales:**
- `remove_shot_from_policy()`: Elimina un shot específico de la policy

**Uso desde Panel:**
1. Hacer **Ctrl+Shift+Click** en el botón del usuario deseado en el panel LGA_NKS_Flow_Assignee_Panel
2. Se abrirá una ventana mostrando todos los shots asignados al usuario
3. Hacer click en "✕" junto a cualquier shot para eliminarlo de la policy
4. La policy se actualiza automáticamente sin necesidad de reiniciar

**Uso desde el panel:**
1. El click normal asigna primero en Flow y espeja `pipesync.db` y
   `pipesync_stats.db`.
2. Si stats quedó confirmado, ejecuta
   `wasabi_policy_sync.py --apply --grant-only --user <Flow name>`.
3. Shift+Click llama al mismo wrapper canónico sin pasar por el escritor histórico.
4. En Client la guarda runtime devuelve un no-op y no inicia Wasabi.

**Uso directo:**
- `module.main(username)`: Llamada programática con usuario específico

### `LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`
**Script de limpieza global** que cruza PipeSync DB con policies IAM de Wasabi para limpiar shots terminados.

**Funcionalidad:**
- Lee `pipesync.db` y toma shots en estados `approved` / `delivery_checked` (aceptando aliases internos `apr` / `check`)
- Escanea policies locales de Wasabi (`*_policy`) y detecta coincidencias por shot
- Muestra una ventana con filas:
  - `Nombre de policy | Nombre de shot | Estado del shot`
- Todas las filas se cargan con checkbox activo por defecto
- Botón **Limpiar policies**: elimina prefijos y recursos S3 correspondientes a los shots seleccionados
- Refresca automáticamente el escaneo después de limpiar

**Uso desde Panel:**
1. Hacer **Shift+Click** en el botón **Clear Assignees** del panel `LGA_NKS_Flow_Assignee_Panel`
2. Esperar el escaneo de DB + Wasabi
3. Revisar/ajustar checkboxes y presionar **Limpiar policies**

**Detalle técnico:**
- Reutiliza validación y versionado de policies desde `wasabi_policy_utils.py`
- Crea una nueva versión de policy por policy modificada (seteada como default)

**Ejemplo de procesamiento:**
```
Ruta: T:\VFX-PROJA\010\PROJA_010_020\_input\archivo.exr
Resultado: Acceso al bucket configurado para PROJA, carpeta '010/PROJA_010_020'
```

### `verify_policy_assign.py`
**Script de verificación** que confirma que las políticas se crearon correctamente.

**Funcionalidad:**
- Verifica que la política existe en Wasabi
- Compara el contenido actual vs. el esperado
- Valida que la política está asignada al usuario
- Muestra información detallada de permisos y versiones

**Uso:**
```bash
python verify_policy_assign.py
```

**Verificaciones realizadas:**
- Existencia de la política
- Permisos básicos de S3 (ListAllMyBuckets, GetBucketLocation)
- Permisos específicos de bucket y carpetas
- Asignación correcta al usuario

## Integración con Panel de Assignees

### Resultado y procesamiento en hilos
El panel ejecuta el wrapper canónico en un `QRunnable`, fuera del hilo de UI. El
resultado distingue éxito, no-op y fallo parcial. Un fallo de stats bloquea el
grant; un fallo de `pipesync.db` con stats correcto permite el grant pero mantiene
el resultado parcial. El contexto Studio/Client queda fijado desde el inicio de la
operación.

### Configuración de Usuarios
Los usuarios salen de `pipesync_stats.db`, tabla `flow_users`, sincronizada desde
Flow por PipeSync. No existe fallback JSON local. Los perfiles con
`skip_wasabi_policy` o sin `wasabi_user` producen un no-op exitoso.

**Clases de la implementación histórica:**
- `WasabiStatusWindow` - Ventana de estado con formato HTML y botón Close
- `WasabiWorker` - Procesamiento en hilo separado (QRunnable)
- `WasabiWorkerSignals` - Señales para comunicación entre hilos
- `get_user_info_from_config()` - Obtiene nombre y color del usuario desde JSON
- `main(username)` - Función principal que maneja toda la interfaz y procesamiento

### `wasabi_policy_utils.py`
**Módulo de utilidades** con funciones auxiliares para la gestión de políticas IAM.

**Funciones principales:**
- `validate_and_repair_policy()`: Valida y repara policies corruptas o inválidas
- `create_minimal_policy()`: Crea una policy mínima válida con permisos básicos
- `get_existing_policy_document()`: Obtiene el documento de policy existente
- `manage_policy_versions()`: Gestiona las versiones de policies (límite de 5)
- `read_user_policy_shots()`: Lee y extrae shots de una policy existente
- `remove_shot_from_policy()`: Elimina un shot específico de la policy

**Validación y Reparación:**
- Detecta statements inválidos o corruptos
- Elimina statements de `s3:*` sin recursos válidos
- Limpia prefixes vacíos en statements de `s3:ListBucket`
- Asegura que siempre existan permisos básicos (`s3:ListAllMyBuckets`)
- Convierte policies corruptas en policies mínimas válidas cuando es necesario

## Dependencias

El módulo incluye todas las dependencias de boto3 en subcarpetas locales:
- `boto3/` - Cliente AWS/Wasabi
- `botocore/` - Core de boto3
- `dateutil/`, `jmespath/`, `urllib3/`, `s3transfer/`, `six.py` - Dependencias auxiliares

## Configuración de Credenciales

Las credenciales de Wasabi se obtienen automáticamente desde la configuración segura de PipeSync usando `SecureConfig_Reader.py`. Ya no es necesario configurar variables de entorno.

Las credenciales se leen desde:
- **Windows**: `%APPDATA%\LGA\PipeSync\config.secure`
- **macOS**: `~/Library/Application Support/LGA/PipeSync/config.secure`
- **Linux**: `~/.config/LGA/PipeSync/config.secure`

El panel no lee ni transporta las credenciales IAM: resuelve por ruta absoluta el
runtime instalado y delega el grant al motor de PipeSync.

## Endpoints Utilizados

- **IAM**: `https://iam.wasabisys.com`
- **S3**: `https://s3.wasabisys.com`
- **Región**: `us-east-1`

## Estructura de Política Generada

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::bucket-name",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["", "carpeta/", "carpeta/subcarpeta/*"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::bucket-name/carpeta/subcarpeta",
        "arn:aws:s3:::bucket-name/carpeta/subcarpeta/*"
      ]
    }
  ]
}
```

## Referencias técnicas

- `LGA_NKS_Assignee_Panel.py`: `CanonicalGrantWorker` y
  `create_wasabi_policy_for_user()` implementan Shift+Click no bloqueante.
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py`:
  `AssignSelectedTasksWorker.run()` ordena Flow, mirrors y grant.
- `LGA_NKS_Shared/LGA_NKS_AssignmentSaga.py`:
  `run_post_flow_saga()`, `mirror_stats_assignees()` y
  `run_canonical_wasabi_grant()`.
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`:
  `get_pipesync_runtime_paths()` resuelve binario y script sin depender de PATH.
