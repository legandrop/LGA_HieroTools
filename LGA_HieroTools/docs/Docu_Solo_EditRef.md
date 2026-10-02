# TL | Solo EditRef

Botón del panel **Viewer | TL**, shortcut `Alt+Shift+D`. Script:
`LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Solo_EditRef.py`.

## Por qué existe

Para revisar el corte contra la referencia editorial había que apagar a mano
todos los tracks de video menos EditRef y después volver a prenderlos de a uno.
El botón hace las dos cosas con el mismo gesto.

## Cómo decide

No guarda estado entre toques: mira la secuencia cada vez.

- **Prende todo** si ningún otro track de video prendido tiene un clip o un soft
  effect bajo el playhead **y** hay al menos un track apagado.
- **Si no, deja EditRef solo:** apaga todos los tracks de video salvo
  `EditRef`/`EditRefClean` y `BurnIn`, y prende EditRef si estaba apagado.

La segunda condición evita un toque vacío: con todo prendido y sólo EditRef bajo
el playhead, "prender todo" no cambiaría nada; en ese caso el toque apaga el resto.

## Decisiones

- **Nivel track, no clip.** El enable de cada clip (el que tocan `ON/OFF _comp_`
  y `ON/OFF _roto_`) queda como estaba. Por eso un `_comp_` con el clip apagado
  pero el track prendido cuenta como "visible" para decidir.
- **Puede haber más de un track `EditRef`.** Se midió en una secuencia real con
  dos tracks del mismo nombre; se dejan prendidos todos los que se llamen
  `EditRef` o `EditRefClean` (sin distinguir mayúsculas).
- **BurnIn no se toca nunca**, ni para apagar ni para prender: se respeta como lo
  tenga el usuario.
- **Audio no se toca.** Sólo `videoTracks()`.
- **"Prender todo" no restaura el estado anterior.** Si antes del primer toque
  había un track apagado a propósito, el segundo toque lo prende.
- **Undo:** el cambio va entre `project.beginUndo("Solo EditRef")` y `endUndo()`.
  Medido en NKS 16: `setEnabled` de track entra al Undo y un Ctrl+Z vuelve todos
  los tracks de una vez.

## Shortcut

`Alt+Shift+D` se eligió después de listar en vivo todos los shortcuts de la
sesión (Hiero, Nuke y el pack): sigue la familia de la D (`D` disable nativo,
`Shift+D` comp, `Ctrl+Shift+D` roto) y estaba libre. Como todos los del panel,
es el shortcut del botón: sólo responde si el panel está visible.

Log de cada corrida: `LGA_HieroTools/logs/DebugPy_LGA_NKS_Solo_EditRef.log`.
