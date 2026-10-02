# Captura del viewer: recorte de los bordes negros

## Qué hace y por qué

Review Pic (Flow Review Panel) y Viewer | Snapshot (ViewerTL Panel) capturan el viewer con
`hiero.ui.currentViewer().image()`. Esa imagen es **el viewer entero** a la resolución de pantalla, con
el negro que rodea al cuadro. Las dos tools le sacan solo ese negro, de cualquier lado, con
`crop_black_borders()` de `LGA_NKS_Shared/LGA_NKS_ViewerCrop.py`.

Hasta la v3.96 recortaban **centrado al aspect ratio de la secuencia**. Eso solo era correcto con la
imagen centrada y entera en el viewer. Con zoom o paneo cortaba imagen de un lado y dejaba negro del
otro. Ahora da lo mismo dónde esté la imagen: se queda todo lo que no es el fondo del viewer.

Las herramientas de thumbnail del Flow | S3 Panel (Thumbs, Update Thumb, Create Shot) siguen con su
recorte al aspect ratio: hacen zoom to fill antes de capturar y no tienen este problema.

## Cómo decide qué es borde

- Un borde es una **fila o columna entera** cuyos canales no pasan de `BLACK_THRESHOLD` (6 sobre 255).
  Se mira el canal más alto de cada pixel, no la luminancia, así que un azul muy oscuro no cuenta
  como negro.
- Se recorta desde los cuatro lados hacia adentro y se para en la primera fila o columna con
  contenido. Un negro **adentro** de la imagen no corta nada.
- Las columnas se evalúan solo dentro de la franja de filas con contenido.
- Si toda la captura es negra, se devuelve entera. Ante cualquier error, también: nunca levanta una
  excepción hacia la tool.
- La imagen se lee como bytes RGB888 y se recorre con slices de Python, sin bucle por pixel.

## Lo que se midió en NKS

Sonda `+Building_Blocks/explore_viewer_crop.py`, corrida por el dev-link sobre NKS 16.0v4 con una
secuencia 3840x2160:

- `viewer.image()` devuelve `Format_RGB32` del tamaño del viewer en pantalla (2243x833 en esa prueba),
  no el de la secuencia.
- **El fondo del viewer es negro puro**: los cuatro bordes dieron 0 en los tres canales. El umbral de
  6 queda solo como margen; con 0, 2, 6 o 12 el rectángulo fue el mismo.
- Imagen centrada y entera: recorte 1038x583, que es 16:9, sin negro. 32 ms en total.
- Imagen con zoom que llena el viewer salvo una franja a la derecha: recorte 1928x833, que saca solo
  esos 315 px de la derecha y deja los otros tres lados enteros. 15 ms.

## Logs y tests

- Cada recorte deja `LGA_HieroTools/logs/DebugPy_LGA_NKS_ViewerCrop.log` con el tamaño de la captura,
  el rectángulo y cuánto se sacó de cada lado.
- `LGA_NKS_Shared/tests/test_viewer_crop.py`, sin Hiero: negro en los cuatro lados, solo a la derecha,
  sin bordes, todo negro, contenido muy oscuro, fondo casi negro y negro dentro de la imagen.
