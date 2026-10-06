# Create NK v000

Crea el comp v000 desde un template del proyecto. El aPlate es obligatorio.
El escaneo y la escritura corren en workers; los diálogos, en el hilo principal.

Si faltan secuencias EXR denoised para los plates del shot que tienen slots
en el template (a–f), aparece una sola confirmación con todos los faltantes.
El cartel destaca `Missing denoised`, los Reads afectados y `original template
paths` para identificar el problema y la consecuencia de continuar de un vistazo.
`Cancel` termina sin escribir. `Continue` permite elegir el rango y crear el
script conservando los tríos Read/Anchor/Stamp y las rutas originales de esos
denoised, incluso el nombre del shot de origen y los placeholders del template.
Los rangos de esos Reads también se conservan. El aviso final identifica cuáles
quedaron pendientes; sus rutas se deben corregir cuando estén los renders.

Los denoised encontrados se actualizan normalmente. Los slots de plates que
el shot no tiene se eliminan junto con sus denoised. Las columnas extra con
medios existentes se clonan como antes. La conservación no inventa rutas ni
renders para columnas que el template no contempla.

Si el destino existe, se solicita además autorización para sobrescribirlo y se
guarda la copia `.nk~`. Esta confirmación es independiente de los denoised.

## Nombre del shot y vendor

El shot es el nombre de su **carpeta**: `PROJA_503_010`, o `PROJB_1013_0800_VEN`
en los proyectos que llevan vendor al final. El vendor es opcional y no se
consulta la lista de vendors de PipeSync: con la carpeta alcanza, y así la tool
no depende de que el vendor esté cargado.

Lo que sí importa es **dónde** se lee el nombre. El cuarto bloque solo se puede
decidir por estructura cuando el nombre está completo y delimitado (la carpeta,
un segmento entre barras). Suelto en el texto no: `PROJA_010_020_comp` y
`PROJB_010_020_VEN` tienen la misma forma. Por eso el shot de origen del
template se busca como carpeta en sus rutas (`.../<seq>/<shot>/...`), tomando la
más repetida y descartando el shot del nombre del template (`PROJA_000_000`).
Hasta la v1.14 se buscaba como token suelto de cuatro bloques, y en un proyecto
sin vendor eso devolvía `PROJA_089_010_aPla`: el shot más el arranque de
`_aPlate`.

Si el template no tiene ninguna ruta con la carpeta del shot, se buscan nombres
sueltos con la misma cantidad de bloques que el shot destino.

## Qué tiene que traer el template

Un **slot** es un trío Read → Anchor → Stamp cuyo Read lleva el nombre del slot
en su **label**: `aPlate` … `fPlate`, `aDenoised` … `fDenoised`, `cbPlate`,
`rfPlate`, `ccPlate`, `lgPlate`. La tool reconoce el slot por el label, no por
el nombre del archivo: un Read sin label no existe para ella.

El único slot obligatorio es `aPlate`. El template trae los demás si quiere:
un proyecto de un solo plate puede tener solo `aPlate` y `aDenoised`. Hasta la
v1.15 se exigían los 16 y la corrida abortaba con la lista de los que faltaban.

- **El Read de un slot puede estar vacío.** Alcanza con el label. Nuke no
  escribe los knobs que quedaron en su default, así que un Read recién creado
  se guarda sin `file` ni rango; la tool los agrega. Hasta la v1.15 solo
  reemplazaba knobs existentes: el Read quedaba vacío y el log decía `SET`
  igual. El log ahora marca `[el Read venia sin file]`.
- **Un plate del shot sin slot en el template se clona** del último slot de
  letra que sirva de molde (`f`, `e`, … `b`), plate desde plate y denoised
  desde denoised. Con un solo slot `b` de cada tipo alcanza para clonar todos
  los demás.
- **El slot `a` nunca sirve de molde.** Su trío lleva líneas `set`/`push` y su
  Stamp está cableado al resto del comp, fuera de la columna de input: una
  copia quedaría colgando en el medio del graph. Si el shot trae un plate que
  el template no contempla y no hay otro slot del que copiar, ese plate no se
  agrega y el cartel final lo avisa por nombre.
- **Las columnas se ubican según el propio template.** La primera va en la x
  del Read `aPlate`, el paso es la distancia `aPlate` → `aDenoised`
  (`COLUMN_STEP` si no hay `aDenoised`) y el backdrop `input` conserva el
  margen que tenía a la derecha de su último slot. Hasta la v1.15 eran
  coordenadas fijas medidas sobre un template: en otro armado en otra zona
  del node graph, los plates caían fuera de su backdrop.
