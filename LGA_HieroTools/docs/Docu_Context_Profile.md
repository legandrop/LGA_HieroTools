# LGA_HieroTools - Studio/Client Context

## Objetivo

Permitir que las tools de Hiero trabajen en modo `studio` o `client` sin cambiar
código.

## Cómo se decide el modo

El modo es **studio salvo que algo diga lo contrario**. Una instalación de
estudio no lleva ningún archivo de contexto: que no haya nada es studio.
`LGA_NKS_ContextProfile` mira, en este orden:

1. `LGA_HIEROTOOLS_CONTEXT_INI`, si la variable apunta a un archivo.
2. El INI suelto `~/.nuke/Python/Startup/LGA_HieroTools_context.ini`. **No lo
   instala nadie**: lo escribe el switch Studio/Client del Projects Panel, que
   existe para un solo usuario. Es el cambio local, y por eso gana.
3. El INI de adentro de la carpeta del pack,
   `~/.nuke/Python/Startup/LGA_HieroTools/LGA_HieroTools_context.ini`. Es la
   marca del build: solo viaja en el paquete client.
4. Nada de lo anterior: `studio`.

Formato, en los dos archivos:

```ini
[Context]
mode=client
```

**Por qué la marca va adentro del pack y no suelta.** Hasta v3.97 las dos
variantes instalaban el INI suelto en `Python/Startup`, como un tercer item
visible, y el instalador y la guía lo nombraban. Al usuario no le sirve de nada
saber que existe un contexto: el único que cambia de uno a otro es quien tiene
el switch. Adentro del pack es un archivo más entre cientos, nadie lo instala a
mano y nada lo menciona.

**El switch nunca escribe sobre la marca del build.** Usa
`get_override_ini_path()`, que da siempre la ruta del INI suelto. Antes escribía
en "el primer INI que exista", y en un paquete client ese es el de adentro del
pack.

## Qué cambia por contexto

- Lectura de `config.secure` y `.key` desde:
  - `%APPDATA%/LGA/PipeSync` (studio)
  - `%APPDATA%/LGA/PipeSyncClient` (client)
- Resolución de `pipesync.db` mediante helper compartido
  (`LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`) sin hardcodes fijos por script.
- Fallback de escaneo base en panel de proyectos:
  - `T:\` en studio
  - `N:\` en client (si no hay `AltTPath`)
- Scope de tasks en herramientas de edición:
  - `studio`: `comp`, `roto`, `cleanup`
  - `client`: solo `comp` (aplica a Create v000 y su flujo post-import desde Import Shot)

## Módulos clave

- `LGA_NKS_Shared/LGA_NKS_ContextProfile.py`
- `LGA_NKS_Shared/SecureConfig_Reader.py`
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPaths.py`
- `LGA_NKS_Shared/LGA_NKS_PipeSyncPreflight.py`

## Documentación complementaria

- `LGA_HieroTools/docs/Doc_HieroTools_Studio_Client_Context.md`
  (lista de archivos adaptados, pendientes y reglas de operación Pull/Push).
