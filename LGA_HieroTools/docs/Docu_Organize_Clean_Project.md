# Organize Project y Clean Project

Estas dos acciones viven en la barra lateral derecha del **Projects Panel** porque operan sobre el proyecto activo completo, no sobre una seleccion ni sobre una edicion puntual del timeline. Separarlas de Refresh, Settings y Reimport con un divisor permite conservar la barra compacta sin mezclar controles del panel con operaciones destructivas o estructurales del proyecto.

## Interfaz

- **Organize Project** usa un icono de carpeta con flecha de entrada. Tooltip: `Organiza los clips en bins basándose en su ruta de archivo`.
- **Clean Project** usa el icono de papelera compartido por el pack. Tooltip: `Elimina clips no usados del proyecto`.
- Ambos son botones directos de icono, de 20 x 20 px, con la misma huella y estados normal/hover que la barra existente.
- Los tooltips se declaran como constantes en `LGA_NKS_UIManager.py`; no quedan hardcodeados en cada widget, para facilitar la futura migracion bilingue.

`ProjectsPanel._run_project_tool()` carga el script desde `LGA_NKS_Projects_Panel_py`, exige un `main()` invocable, registra el resultado en el log del panel y muestra un aviso si el archivo no existe o la ejecucion falla.

## Organize Project

Reorganiza clips dentro del `clipsBin()` del primer proyecto abierto devuelto por `hiero.core.projects()`. La estructura destino se deriva del path del media:

```text
Clips
+-- F <parts[2]>
    +-- <parts[3]>
        +-- clip
```

Reglas y limites:

- Recorre recursivamente los bins existentes y omite cualquier bin llamado exactamente `Published`, junto con todo su contenido.
- Solo mueve `hiero.core.BinItem` cuyo `activeItem()` sea un `hiero.core.Clip`.
- Usa el primer `fileinfo()` y divide el path por `/`; paths con menos de cuatro partes no se organizan.
- Crea o reutiliza `F <parts[2]>/<parts[3]>`, no renombra clips ni cambia media, timeline, versiones, tags o metadata.
- Al final elimina bins vacios, salvo `Published`.
- Los clips ubicados directamente en la raiz de `clipsBin()` no entran al recorrido inicial.

La accion abre un undo `Reorganize Clips Based on Path` y deja su diagnostico en `logs/DebugPy_OrganizeProject.log`.

## Clean Project

Combina dos limpiezas del proyecto activo:

- elimina BinItems que considera sin uso en las secuencias;
- elimina versiones offline de clips que tienen multiples versiones.

Conserva la proteccion contra items que sean secuencias y presenta al usuario un resumen final. No elimina tags del proyecto, por eso los settings de LGA BurnIn guardados en `tagsBin()` sobreviven a esta accion.

La limpieza actual decide si un BinItem esta en uso comparando nombres. Esa limitacion esta documentada tambien en `Docu_Clips_Zombie.md`: si el nombre del BinItem y el de la fuente del timeline difieren, puede interpretar mal el uso. No cambiar esa logica sin medir primero en Nuke Studio, porque `activeItem()` sobre un BinItem huerfano puede cerrar el host.

## Referencias tecnicas

- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel.py`: `ProjectsPanel._run_project_tool()`, `ProjectsPanel.organize_project()`, `ProjectsPanel.clean_project()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_NKS_UIManager.py`: `UIManager.setup_ui()`, `UIManager._add_project_action_button()`, `UIManager.setup_connections()`, `UIManager.eventFilter()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_NKS_OrganizeProject.py`: `OrganizeProject`, `get_active_project()`, `main()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\LGA_NKS_CleanProject.py`: `cleanAllUnusedClips()`, `cleanOfflineVersions()`, `main()`.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\icons\trash.svg`: icono normal de Clean Project.
- `C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Projects_Panel_py\organize_project.svg`: icono normal de Organize Project, basado en Lucide Folder Input (licencia ISC incluida en el SVG).
