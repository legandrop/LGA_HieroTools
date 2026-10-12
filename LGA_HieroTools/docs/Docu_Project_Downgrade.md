# Project Downgrade: proyectos de 17 para NKS/Hiero 16.0

Existe porque un timeline con clips y efectos compartidos puede quedar inaccesible
para todo el equipo cuando se guarda desde una version nueva del host. Foundry
introdujo el formato hrox 12 en 16.1; NKS/Hiero 16.0 admite hasta el 11 y rechaza
el proyecto antes de cargarlo. El numero del formato es independiente de la version
del programa. Cambiar solamente el atributo `release` no resuelve el problema.

`LGA_NKS_Project_Downgrade.py` v1.00 crea otra copia con formato 11. Conserva
todos los bytes del proyecto salvo el valor de `hieroXML/@version`, sin
reconstruir bins, versiones, cortes, media, efectos, presets ni CDATA. El destino
por defecto es `<nombre>_NKS16.hrox`, junto al original, para conservar tambien
la base de las rutas relativas. Si se elige otra carpeta, comprobar esas rutas.
Nunca sobrescribe el original ni un destino existente. Tampoco abre el host.

## Uso

En Windows, desde cmd, con el runtime que ya trae este pack:

```bat
"%USERPROFILE%\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Shared\OIIO_Win\bin\python\python.exe" "%USERPROFILE%\.nuke\Python\Startup\LGA_HieroTools\LGA_NKS_Project_Downgrade.py" "T:\VFX-PROJA\PROJA_SUP_v001.hrox"
```

Tambien puede importarse desde el Script Editor de NKS/Hiero 16 o 17. Para no
bloquear la UI durante IO, ejecutar la conversion en un hilo sin acceder a Qt/Hiero:

```python
import threading
from LGA_HieroTools.LGA_NKS_Project_Downgrade import convert_project
threading.Thread(
    target=convert_project,
    args=(r"T:\VFX-PROJA\PROJA_SUP_v001.hrox",),
    daemon=True,
).start()
```

Abrir `PROJA_SUP_v001_NKS16.hrox` desde NKS/Hiero 16.0. La herramienta es
independiente de los paneles: no agrega botones ni se ejecuta durante el startup.
El CLI sale con codigo 1 si falla y avisa la causa. Cada corrida escribe
`logs/DebugPy_LGA_NKS_Project_Downgrade.log`; consola de debug apagada por defecto.

## Annotations y limites

Las annotations nuevas de 16.1/17 no equivalen a las annotations de 16.0. Una
sonda con texto y comentario demostro que 16 abre un XML con ellas, pero las
elimina al guardar. Por eso la conversion **se detiene por defecto si encuentra
objetos XML `Annotation`**, incluso si solo contienen un comentario.

Si se acepta perderlas en la copia, agregar `--drop-annotations` al CLI, o
`drop_annotations=True` a la funcion. El descarte elimina solamente esos nodos
por offsets de bytes; no reserializa el resto del XML. El original sigue
conservando las annotations. No hay traduccion de dibujos/comentarios a objetos
de la API antigua. Las menciones a annotations dentro de presets o CDATA no
activan el bloqueo, y las annotations antiguas como efectos no se eliminan.

Se aceptan proyectos completos de formato 12, guardados con 16.1 o 17.0.
La comprobacion en el host se hizo con 17.0v4; 16.1 se admite por compartir
el formato 12, pero no se probo en una instalacion 16.1.
Formatos anteriores, posteriores, XML incompleto y releases desconocidos se
rechazan. Esto no convierte nodos, plugins, codecs o funciones exclusivas de
17: deben existir tambien en 16. Comprobar el resultado antes de continuar
trabajando; conservar el original permite recuperar cualquier funcion nueva.

## Verificacion medida

Prueba en NKS 17.0v4 y 16.0v4, mediante dev-links con puertos separados:

- Proyecto real de formato 12: apertura directa en 16 rechazada.
- Copia con formato 11: apertura, guardado y reapertura correctos en 16.
- Inventarios identicos: 3 secuencias, 26 pistas (24 video y 2 audio), 155
  items, 15 efectos del timeline, 333 entradas de bins y 346 versiones.
- Se compararon GUIDs, nombres, archivos fuente, rangos source/timeline,
  velocidad, estados enabled, tags, enlaces, clases y knobs de efectos,
  versiones de bins y versiones activas. El JSON ordenado tuvo SHA-256
  identico antes de convertir, despues de abrir y despues de guardar/reabrir.
- El archivo del conversor tambien se abrio en 16 con el mismo inventario.
- Fixture nuevo con annotation de texto/comentario: rechazo por defecto;
  copia con descarte explicito abre en 16. Seis tests automatizados cubren
  conservacion de bytes, originales/destinos, formato invalido, annotations,
  CDATA y errores de escritura. No se comprobo cada efecto exclusivo de 17.

La sonda reutilizable es `+Building_Blocks/explore_hrox_downgrade.py`; su
inventario es de solo lectura. Las muestras de clientes y resultados completos
son privados y no se publican. El launcher local de 16 usa el puerto 54329;
17 conserva 54326. Los dev-links solo se habilitan por lanzamiento.

## Fuentes

- [Foundry: Saving and Loading Projects](https://learn.foundry.com/nuke/content/timeline_environment/conforming/saving_loading.html), incompatibilidad de 16.1/17 con 16.0.
- [Foundry: Nuke 17.0v1 Release Notes](https://learn.foundry.com/nuke/17.0/content/release_notes/17.0/nuke_17.0v1_releasenotes.html), nuevas annotations y cambio de API.
- `hiero/core/hrox_convert.py` instalado con el host: version de formato
  independiente del release. Su conversor antiguo no hace este downgrade.
