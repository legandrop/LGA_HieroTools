> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios.

# LGA_NKS_NukeInit: sin avisos "Can't restore panel" al arrancar

## Por qué existe

Al arrancar, Nuke Studio imprime en la consola una línea por cada panel de
HieroTools:

    Can't restore panel ' com.lega.FPTPanel ' because it hasn't been registered.

No es un error real: los paneles terminan en su lugar igual. Pero son ocho
líneas de ruido en cada arranque, y un error de verdad queda tapado entre ellas.
El módulo existe solo para sacar ese ruido. No agrega ninguna herramienta ni
cambia el comportamiento de ningún panel.

## Por qué sale el aviso

Es un problema de orden de carga:

1. Nuke Studio rearma el workspace guardado. Por cada panel del layout llama a
   `nukescripts.restorePanel(id)`.
2. Recién después carga `Python/Startup`, que es donde HieroTools crea sus
   paneles. Medido: cuando corre `Python/Startup` la ventana principal ya está
   visible.

En el paso 1 los ids `com.lega.*` todavía no existen. `restorePanel` es esto, en
`plugins/nukescripts/panels.py` de Nuke:

    def restorePanel( id ):
      try:
        return __panels[id]()
      except:
        print("Can't restore panel '", id, "' because it hasn't been registered.")
        return None

En el paso 2 los paneles se ubican con `windowManager().addWindow()`, que no
depende de lo que haya pasado en el paso 1.

## Qué hace

Registra cada id `com.lega.*` con `nukescripts.registerPanel(id, comando)`, donde
el comando devuelve `None`. Es exactamente lo que `restorePanel` devuelve después
de imprimir el aviso, así que el rearmado del workspace recibe lo mismo que
antes y lo único que cambia es que no se imprime nada.

No se registran los paneles reales a propósito: crearlos en ese momento exigiría
cargar todo HieroTools antes de que exista la ventana, que es justo lo que el
arranque en `Python/Startup` evita.

Los ids no están escritos en el módulo: los lee de los
`setObjectName("com.lega.…")` de los `.py` de la raíz de `LGA_HieroTools/`. Un
panel nuevo queda cubierto sin tocar nada.

## Instalación

Es opcional y se activa con una línea en el `init.py` de la carpeta `.nuke`:

    nuke.pluginAddPath("./Python/Startup/LGA_HieroTools/LGA_NKS_NukeInit")

Tiene que ir ahí y no en `Python/Startup`: los `init.py` del plugin path de Nuke
corren antes del rearmado del workspace, y `Python/Startup` corre después.

- **El instalador de HieroTools no agrega la línea.** HieroTools no es un plugin
  de Nuke y su instalador no toca `init.py`. Quien instala desde el `.zip` no ve
  el `README.md` (no viaja en el `.zip`): la línea está explicada en la guía de
  instalación en PDF que sí viaja.
- **Los instaladores de los ToolPacks reescriben `init.py`**: juntan los
  `pluginAddPath` de las carpetas `LGA_*` y los reordenan. Esta línea no la
  mueven, porque su ruta empieza con `Python/`, pero pueden usarla de ancla para
  insertar el grupo justo arriba. Al hacerlo solo consideran **una** línea de
  comentario pegada encima. Si se le pone un comentario de dos líneas, el
  instalador lo parte y deja la primera suelta más arriba. Comentario de una
  sola línea, o ninguno.
- En cada máquina hay que agregar la línea por separado: `init.py` es de la
  carpeta `.nuke` de cada una, no del pack.

## Lo que hay que saber antes de tocarlo

- **`__file__` no siempre existe.** Nuke ejecuta los `init.py` desde C++. Por eso
  el módulo, si no tiene `__file__`, busca su propia carpeta en
  `nuke.pluginPath()`, que `pluginAddPath` ya dejó cargado.
- **Solo lee la raíz del pack.** Un panel `com.lega.*` declarado en una
  subcarpeta no se registra y su aviso vuelve, sin ningún error.
  `tests/test_nukeinit_panel_ids.py` falla si eso pasa.
- **Falla en silencio, a propósito.** Corre en el arranque de todo Nuke que use
  esa carpeta `.nuke` (también NukeX y los renders), así que cualquier excepción
  se traga: no puede impedir que Nuke abra. Si deja de funcionar, el síntoma es
  que los avisos vuelven a la consola.
- **Fuera de Nuke Studio / Hiero no hace nada visible.** Los ids quedan
  registrados y nadie los pide.

## Cómo verificar

Abrir Nuke Studio y mirar la consola: no tiene que quedar ninguna línea
`Can't restore panel ' com.lega.… '`. Los paneles tienen que aparecer en el mismo
lugar del workspace que antes.

## Referencias técnicas

- `LGA_HieroTools/LGA_NKS_NukeInit/init.py`
  - `hierotools_panel_ids(tools_dir)` lee los ids de los `.py` de la raíz.
  - `register_panel_placeholders()` registra cada id; corre al cargar el módulo.
  - `_this_dir()` resuelve la carpeta con o sin `__file__`.
- `LGA_HieroTools/tests/test_nukeinit_panel_ids.py`
