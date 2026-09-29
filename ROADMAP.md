# Roadmap

Pendientes conocidos. No es un changelog: aca va lo que falta hacer, no lo que
ya se hizo. Al completar un item se borra de aca y se registra en el changelog.

---

## UI

### Rutas coloreadas: anclar el color en el shotname

Regla (ver `Docu_UI_Style.md` de LGA_ToolPack y el AGENTS.md de cada repo):
cuando en una ruta se puede detectar un nombre de shot, todo hasta el shot
INCLUIDO va en un solo color (el de parte comun, `PATH_COMMON`) y la paleta
por nivel arranca en el segmento SIGUIENTE al shot. Colorear por nivel desde
la raiz queda solo para rutas sin shot detectable.

Hay que rechequear y arreglar:

- `colorize_path()` ya quedo anclado al shotname en las cuatro copias del
  modulo de estilo (v1.22). Falta `colorize_path_pair()`, que tras la
  parte comun del par sigue coloreando por nivel sin mirar el shot.
- Todas las ventanas del repo que muestren rutas, revisarlas contra la regla.

Donde mirar ejemplos de como detectar el shot en una ruta:

- HieroTools `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`:
  `extract_shot_code_from_path()` e `is_shot_folder_name()` (naming
  PROYECTO_SEQ_SHOT_VENDOR validado contra la DB de PipeSync).
- HieroTools `LGA_NKS_Edit_Panel_py/LGA_NKS_ApplyAMF.py`:
  `resolve_shot_dir()` — fallback estructural: subir directorios hasta el que
  contenga `_input`.

---

## Remote Nav (saltar a un shot desde PipeSync)

### Varios NKS abiertos: rango de puertos

Hoy `LGA_NKS_RemoteNav` escucha en un puerto fijo (`127.0.0.1:54327`) y con
varios NKS abiertos contesta el primero que lo tomo, aunque no tenga el
proyecto del shot. Se acepto el limite en la v1. La alternativa: cada NKS toma
un puerto libre de un rango (por ejemplo 54327-54336), contesta un `ping` con
los proyectos que tiene abiertos, y el cliente (`NukeStudioNavigator` de
PipeSync) elige a quien mandarle `goto_shot`. Detalle del contrato actual en
`LGA_HieroTools/docs/Docu_RemoteNav.md`.

### El Flow Pull podria usar el foco de clip compartido

`LGA_NKS_Flow_Pull.navigate_to_pull_result()` y
`LGA_NKS_ShotNavigation._focus_clip()` hacen lo mismo (seleccion, In/Out desde
EditRef, playhead, Zoom to Fit) con dos copias del codigo. No se unificaron en
la v1 para no tocar el Pull sin poder probarlo contra Flow en la misma pasada.
Unificarlo es hacer que el Pull llame a `_focus_clip()` (publicandolo) y
probar un click en una fila del Pull, con y sin EditRef.
